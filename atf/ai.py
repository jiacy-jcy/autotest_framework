"""AI 用例生成：内置规则引擎离线可用；配置大模型后可自动补充边界用例"""
import json
import os
import re
from pathlib import Path

import httpx
import yaml

from .errors import ATFError

_HTTP_METHODS = ("get", "post", "put", "delete", "patch")
_TYPE_EXAMPLES = {"string": "demo", "integer": 1, "number": 1.0, "boolean": True}


def generate_from_openapi(spec_path, output_dir, use_llm=False):
    """从 OpenAPI/Swagger 文档生成 YAML 用例，返回生成的文件路径"""
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    steps = []
    for path, operations in (spec.get("paths") or {}).items():
        for method, operation in operations.items():
            if method.lower() in _HTTP_METHODS and isinstance(operation, dict):
                steps.append(_build_step(path, method.upper(), operation))
    if not steps:
        raise ATFError(f"未在 {spec_path} 中找到任何接口定义（paths 为空）")

    if use_llm:
        steps = _enhance_with_llm(steps)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "generated_cases.yaml"
    case = {"config": {"name": f"自动生成的用例（来源：{Path(spec_path).name}）"}, "teststeps": steps}
    target.write_text(yaml.safe_dump(case, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return target


def _build_step(path, method, operation) -> dict:
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
    return step


def _example_value(schema: dict):
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
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
