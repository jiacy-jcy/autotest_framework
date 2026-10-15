"""AI 用例生成：内置规则引擎离线可用；配置大模型后可自动补充边界用例"""
import copy
import json
import os
import re
from pathlib import Path

import httpx
import yaml

from .errors import ATFError

_HTTP_METHODS = ("get", "post", "put", "delete", "patch")
_TYPE_EXAMPLES = {"string": "demo", "integer": 1, "number": 1.0, "boolean": True}
_LOGIN_KEYWORDS = ("login", "signin", "sign-in", "token", "auth")
_ENUM_VARIANT_LIMIT = 3


def generate_from_openapi(spec_path, output_dir, use_llm=False):
    """从 OpenAPI/Swagger 文档生成 YAML 用例，返回生成的文件路径"""
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    auth_header = _auth_header(_security_schemes(spec))
    login_path, login_operation = (_find_login_operation(spec) if auth_header else (None, None))
    auto_login = bool(login_operation)

    steps = []
    for path, operations in (spec.get("paths") or {}).items():
        for method, operation in operations.items():
            if method.lower() not in _HTTP_METHODS or not isinstance(operation, dict):
                continue
            if auto_login and path == login_path and method.lower() == "post":
                continue  # 登录接口单独生成为前置步骤
            built = _build_step(path, method.upper(), operation)
            if auth_header and _is_secured(operation, spec):
                for step in built:
                    step["request"].setdefault("headers", {})[auth_header[0]] = auth_header[1]
            steps.extend(built)
    if not steps:
        raise ATFError(f"未在 {spec_path} 中找到任何接口定义（paths 为空）")

    hints = []
    if auto_login:
        login_step = _build_step(login_path, "POST", login_operation)[0]
        login_step["name"] = "登录获取令牌"
        login_step["extract"] = {"token": "$.data.token"}
        steps = [login_step] + steps
        hints.append("检测到安全方案：已自动生成登录步骤，并为受保护接口加上认证头。")
        hints.append("请核对登录步骤的请求体，并按实际响应调整 token 提取路径（默认 $.data.token）。")

    if use_llm:
        steps = _enhance_with_llm(steps)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "generated_cases.yaml"
    case = {"config": {"name": f"自动生成的用例（来源：{Path(spec_path).name}）"}, "teststeps": steps}
    body = yaml.safe_dump(case, allow_unicode=True, sort_keys=False)
    comments = "".join(f"# {hint}\n" for hint in hints)
    target.write_text(comments + body, encoding="utf-8")
    return target


def _build_step(path, method, operation) -> list:
    step = {
        "name": operation.get("summary") or f"{method} {path}",
        "request": {"method": method, "url": path},
        "validate": [{"eq": ["status_code", 200]}],
    }
    params = {p["name"]: _example_value(p.get("schema") or {})
              for p in operation.get("parameters") or []
              if p.get("in") == "query" and "name" in p}
    if params:
        step["request"]["params"] = params
    body = _example_body(operation)
    if body:
        step["request"]["json"] = body

    # 枚举参数自动参数化：为第一个带 enum 的查询参数按枚举值生成多个变体
    enum_param, enum_values = _first_enum_param(operation)
    if not enum_param or len(enum_values) < 2:
        return [step]
    variants = []
    for value in enum_values[:_ENUM_VARIANT_LIMIT]:
        clone = copy.deepcopy(step)
        clone["request"]["params"] = dict(params)
        clone["request"]["params"][enum_param] = value
        clone["name"] = f"{step['name']}（{enum_param}={value}）"
        variants.append(clone)
    return variants


def _first_enum_param(operation: dict) -> tuple:
    for param in operation.get("parameters") or []:
        if param.get("in") != "query" or "name" not in param:
            continue
        enum = (param.get("schema") or {}).get("enum")
        if isinstance(enum, list) and enum:
            return str(param["name"]), enum
    return None, []


def _security_schemes(spec: dict) -> dict:
    components = spec.get("components") or {}
    schemes = components.get("securitySchemes") or spec.get("securityDefinitions") or {}
    return schemes if isinstance(schemes, dict) else {}


def _auth_header(schemes: dict):
    """从安全方案推导认证头：返回 (头名称, 头模板)；无法自动推导时返回 None"""
    for scheme in schemes.values():
        if not isinstance(scheme, dict):
            continue
        kind = str(scheme.get("type") or "").lower()
        if kind == "http" and str(scheme.get("scheme") or "").lower() == "bearer":
            return "Authorization", "Bearer ${token}"
        if kind == "apiKey" and str(scheme.get("in") or "").lower() == "header" and scheme.get("name"):
            return str(scheme["name"]), "${token}"
    return None


def _find_login_operation(spec: dict) -> tuple:
    for path, operations in (spec.get("paths") or {}).items():
        if not any(word in str(path).lower() for word in _LOGIN_KEYWORDS):
            continue
        for method, operation in operations.items():
            if method.lower() == "post" and isinstance(operation, dict):
                return path, operation
    return None, None


def _is_secured(operation: dict, spec: dict) -> bool:
    security = operation.get("security", None)
    if security is None:
        security = spec.get("security")
    return bool(security)  # security: [] 表示显式无需认证


def _example_value(schema: dict):
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    return _TYPE_EXAMPLES.get(schema.get("type", "string"), "demo")


def _example_body(operation: dict):
    content = ((operation.get("requestBody") or {}).get("content") or {}).get("application/json") or {}
    properties = (content.get("schema") or {}).get("properties") or {}
    return {key: _example_value(value) for key, value in properties.items()} or None


def _enhance_with_llm(steps: list) -> list:
    """调用大模型（OpenAI 兼容接口）为每个接口补充边界/异常场景用例。

    通过环境变量配置：ATF_AI_BASE_URL / ATF_AI_API_KEY / ATF_AI_MODEL
    """
    base_url = os.environ.get("ATF_AI_BASE_URL", "https://api.openai.com/v1")
    api_key = os.environ.get("ATF_AI_API_KEY", "")
    model = os.environ.get("ATF_AI_MODEL", "gpt-4o-mini")
    if not api_key:
        print("提示：未配置环境变量 ATF_AI_API_KEY，已跳过 AI 增强，仅生成基础用例")
        return steps
    prompt = (
        "你是资深测试工程师。以下是接口自动化测试用例（YAML 格式），"
        "请为每个接口补充 2 条边界或异常场景的 teststeps（如参数为空、超长、非法类型），"
        "只返回补充部分的 YAML 列表，不要任何解释或代码块标记：\n\n"
        + yaml.safe_dump(steps, allow_unicode=True, sort_keys=False)
    )
    try:
        resp = httpx.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            timeout=60,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        extra = yaml.safe_load(_strip_code_fence(text))
        if isinstance(extra, list):
            return steps + [s for s in extra if isinstance(s, dict) and "request" in s]
    except (httpx.HTTPError, KeyError, yaml.YAMLError) as exc:
        print(f"提示：AI 增强失败（{exc}），已回退为基础用例")
    return steps


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n|\n?```$", "", text)
    return text
