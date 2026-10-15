"""零代码转换：HAR → 用例、curl → 用例

- HAR：浏览器 DevTools「Save all as HAR」导出的文件一键转换
- curl：DevTools「Copy as cURL」复制的命令一键转换

转换时会自动：过滤静态资源与 CORS 预检请求、按（方法/地址/请求体）去重、
拆出 base_url、跳过无意义请求头（Content-Length / Host 等）、
JSON 请求体还原为 json、表单体还原为 data 字典。
注意：Cookie / Authorization 等敏感头会原样保留，请按需清理或改用登录流提取。
"""
import base64
import json
import shlex
from pathlib import Path
from urllib.parse import unquote_plus, urlsplit

import yaml

from .errors import ATFError

_STATIC_EXTENSIONS = (
    ".js", ".css", ".map", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".otf", ".mp4", ".webm", ".webp",
)
_SKIP_HEADERS = {"content-length", "host", "connection", "accept-encoding"}
_KEEP_RESOURCE_TYPES = ("xhr", "fetch")

_CURL_VALUE_FLAGS = {
    "-X", "--request", "-H", "--header", "-d", "--data", "--data-raw", "--data-binary",
    "--data-urlencode", "--json", "-u", "--user", "-A", "--user-agent", "-e", "--referer",
    "-b", "--cookie", "-o", "--output", "--url", "-m", "--max-time", "--connect-timeout",
    "--retry", "-x", "--proxy",
}
_CURL_BOOL_FLAGS = {
    "-s", "--silent", "-S", "--show-error", "-i", "--include", "-v", "--verbose",
    "-k", "--insecure", "-L", "--location", "-f", "--fail", "--compressed",
    "-#", "--progress-bar", "-G", "--get", "--http1.1", "--http2", "-4", "-6",
}


def detect_source(path) -> str:
    """识别文件类型：返回 har / openapi，用于 atf gen 自动分发"""
    p = Path(path)
    if not p.exists():
        raise ATFError(f"文件不存在：{p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ATFError(f"文件不是合法 JSON：{exc}") from None
    if isinstance(data, dict) and "log" in data:
        return "har"
    if isinstance(data, dict) and ("openapi" in data or "swagger" in data or "paths" in data):
        return "openapi"
    raise ATFError(f"无法识别文件类型（既不是 HAR 也不是 OpenAPI/Swagger）：{p.name}")


def generate_from_har(har_path, output_dir) -> Path:
    """把 HAR 文件转换为 YAML 用例，返回生成的文件路径"""
    path = Path(har_path)
    if not path.exists():
        raise ATFError(f"HAR 文件不存在：{path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ATFError(f"HAR 文件不是合法 JSON：{exc}") from None
    entries = ((data.get("log") or {}).get("entries")) or []
    if not isinstance(entries, list) or not entries:
        raise ATFError(f"HAR 文件中没有请求记录（log.entries 为空）：{path.name}")

    base_url = None
    steps, seen = [], set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        resource_type = str(entry.get("_resourceType") or "").lower()
        if resource_type and resource_type not in _KEEP_RESOURCE_TYPES:
            continue  # 非接口请求（脚本/样式/图片等）
        step = _har_step(entry.get("request") or {})
        if step is None:
            continue
        request = step["request"]
        fingerprint = (request["method"], request["url"],
                       _stable_repr(request.get("json")), _stable_repr(request.get("data")))
        if fingerprint in seen:
            continue  # 去重（轮询等重复请求）
        seen.add(fingerprint)
        url = request["url"]
        if base_url is None:
            base_url, request["url"] = _split_url(url)
        elif url.startswith(base_url):
            request["url"] = url[len(base_url):] or "/"
        steps.append(step)
    if not steps:
        raise ATFError(f"HAR 中没有可转换的接口请求（已过滤静态资源与预检请求）：{path.name}")
    config = {"name": f"从 HAR 生成的用例（来源：{path.name}）", "base_url": base_url}
    return _write_case(output_dir, "har_cases.yaml", config, steps)


def generate_from_curl(command: str, output_dir) -> Path:
    """把 curl 命令转换为 YAML 用例，返回生成的文件路径"""
    text = (command or "").strip()
    if not text:
        raise ATFError("curl 命令为空")
    if "\n" not in text and not text.startswith(("curl ", "curl.exe ")):
        candidate = Path(text)
        if candidate.exists():  # 传入的是命令文件路径
            text = candidate.read_text(encoding="utf-8").strip()
    try:
        tokens = shlex.split(text)
    except ValueError as exc:
        raise ATFError(f"curl 命令解析失败（引号是否不匹配？）：{exc}") from None
    tokens = [token for token in tokens if token not in ("^", "&&")]
    if tokens and Path(tokens[0]).name.lower() in ("curl", "curl.exe"):
        tokens = tokens[1:]
    if not tokens:
        raise ATFError("curl 命令为空")

    method, url = "", ""
    headers, bodies = [], []
    index = 0

    def take_value(flag: str) -> str:
        nonlocal index
        index += 1
        if index >= len(tokens):
            raise ATFError(f"curl 参数 {flag} 缺少取值")
        return tokens[index]

    while index < len(tokens):
        token = tokens[index]
        if token in ("-X", "--request"):
            method = take_value(token)
        elif token in ("-H", "--header"):
            headers.append(take_value(token))
        elif token in ("-d", "--data", "--data-raw", "--data-binary",
                       "--data-urlencode", "--json"):
            bodies.append(take_value(token))
        elif token in ("-u", "--user"):
            secret = take_value(token).encode("utf-8")
            headers.append("Authorization: Basic " + base64.b64encode(secret).decode("ascii"))
        elif token in ("-A", "--user-agent"):
            headers.append(f"User-Agent: {take_value(token)}")
        elif token in ("-e", "--referer"):
            headers.append(f"Referer: {take_value(token)}")
        elif token in ("-b", "--cookie"):
            headers.append(f"Cookie: {take_value(token)}")
        elif token == "--url":
            url = take_value(token)
        elif token in _CURL_VALUE_FLAGS:
            take_value(token)  # 其余带值参数：忽略
        elif token in _CURL_BOOL_FLAGS or token.startswith("-"):
            pass  # 无值参数 / 未识别参数：忽略
        elif not url:
            url = token
        index += 1

    if not url:
        raise ATFError("未能从 curl 命令中解析出 URL")
    request = {"method": (method or ("POST" if bodies else "GET")).upper(), "url": ""}
    header_map = _parse_headers(headers)
    if header_map:
        request["headers"] = header_map
    if bodies:
        single = len(bodies) == 1
        parsed = _try_json(bodies[0]) if single else None
        if isinstance(parsed, (dict, list)):
            request["json"] = parsed
        elif single and "=" in bodies[0] and "{" not in bodies[0]:
            request["data"] = _parse_form(bodies[0])
        else:
            request["data"] = "&".join(bodies)
    step = {"name": _step_name(request["method"], url),
            "request": request,
            "validate": [{"eq": ["status_code", 200]}]}
    base_url, request["url"] = _split_url(url)
    config = {"name": "从 curl 生成的用例", "base_url": base_url}
    return _write_case(output_dir, "curl_cases.yaml", config, [step])


def _har_step(request: dict):
    """把 HAR 请求记录转为步骤；不可转换时返回 None"""
    method = str(request.get("method") or "GET").upper()
    url = str(request.get("url") or "")
    if not url.startswith(("http://", "https://")) or method == "OPTIONS":
        return None
    path = urlsplit(url).path.lower()
    if any(path.endswith(ext) for ext in _STATIC_EXTENSIONS):
        return None
    req = {"method": method, "url": url}
    headers = {}
    for header in request.get("headers") or []:
        name = str(header.get("name") or "").strip()
        if not name or name.startswith(":") or name.lower() in _SKIP_HEADERS:
            continue
        headers[name] = str(header.get("value") or "")
    if headers:
        req["headers"] = headers
    post = request.get("postData") or {}
    body = post.get("text")
    if body:
        parsed = _try_json(body)
        if isinstance(parsed, (dict, list)):
            req["json"] = parsed
        else:
            req["data"] = body
    elif post.get("params"):
        req["data"] = {str(item.get("name")): str(item.get("value") or "")
                       for item in post["params"] if item.get("name")}
    return {"name": _step_name(method, url), "request": req,
            "validate": [{"eq": ["status_code", 200]}]}


def _try_json(text: str):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def _stable_repr(value) -> str:
    """把请求体转为可哈希、可比较的稳定字符串（用于去重）"""
    if value is None:
        return ""
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(value)


def _parse_headers(header_values: list) -> dict:
    headers = {}
    for item in header_values:
        name, sep, value = str(item).partition(":")
        if not sep:
            continue
        name = name.strip()
        if not name or name.startswith(":") or name.lower() in _SKIP_HEADERS:
            continue
        headers[name] = value.strip()
    return headers


def _parse_form(body: str) -> dict:
    result = {}
    for pair in body.split("&"):
        key, sep, value = pair.partition("=")
        if not sep or not key:
            continue
        result[unquote_plus(key)] = unquote_plus(value)
    return result


def _split_url(url: str):
    parts = urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    return base, url[len(base):] or "/"


def _step_name(method: str, url: str) -> str:
    parts = urlsplit(url)
    segments = [segment for segment in parts.path.split("/") if segment]
    tail = segments[-1] if segments else (parts.netloc or "/")
    return f"{method} /{tail}"[:60]


def _write_case(output_dir, filename: str, config: dict, steps: list) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / filename
    case = {"config": config, "teststeps": steps}
    target.write_text(yaml.safe_dump(case, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return target
