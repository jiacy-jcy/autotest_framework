"""从响应中提取变量：支持 JSON 路径、响应快捷字段与正则三种方式"""
import json
import re

import httpx

from .errors import ExtractError


def extract_value(response: httpx.Response, expression):
    """从响应中取值：

    - status_code    ：响应状态码
    - headers.xxx    ：响应头
    - $.a.b[0]       ：JSON 路径（要求响应体为 JSON）
    - re:正则        ：对响应文本做正则提取（有分组取第一个分组）
    - 其他字符串/非字符串：原样返回（便于与已提取的变量直接比较）
    """
    if not isinstance(expression, str):
        return expression
    if expression == "status_code":
        return response.status_code
    if expression.startswith("headers."):
        return response.headers.get(expression[len("headers."):], "")
    if expression.startswith("re:"):
        pattern = expression[3:]
        match = re.search(pattern, response.text)
        if not match:
            raise ExtractError(f"正则 {pattern!r} 未在响应文本中匹配到任何内容")
        return match.group(1) if match.groups() else match.group(0)
    if expression.startswith("$"):
        try:
            data = response.json()
        except json.JSONDecodeError:
            raise ExtractError(f"响应体不是合法 JSON，无法按路径 {expression} 提取") from None
        return get_by_path(data, expression)
    return expression


def get_by_path(data, path: str):
    """按 JSON 路径取值，例如 $.data.list[0].name"""
    if not isinstance(path, str) or not path.startswith("$"):
        raise ExtractError(f"提取路径格式错误：{path!r}，应以 $ 开头，例如 $.data.token")
    node = data
    for token in _tokens(path):
        try:
            node = node[token]
        except (KeyError, IndexError, TypeError):
            raise ExtractError(f"路径 {path} 提取失败：响应中找不到字段 {token!r}") from None
    return node


def _tokens(path: str) -> list:
    # $.data.list[0].name -> ["data", "list", 0, "name"]
    body = path[1:].lstrip(".")
    tokens = []
    for part in body.split("."):
        if not part:
            continue
        for m in re.finditer(r"([^\[\]]+)|\[(\d+)\]", part):
            key, index = m.groups()
            tokens.append(int(index) if index is not None else key)
    return tokens
