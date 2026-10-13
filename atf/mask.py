"""报告脱敏：在报告的请求/响应体中对敏感字段打码

在 config.mask 中声明字段名列表，仅影响报告展示，不影响真实请求。
"""
import json

MASK = "******"


def mask_keys(config) -> list:
    """读取 config.mask：支持列表或逗号分隔字符串"""
    keys = (config or {}).get("mask")
    if not keys:
        return []
    if isinstance(keys, str):
        return [item.strip() for item in keys.split(",") if item.strip()]
    if isinstance(keys, list):
        return [str(item) for item in keys]
    return []


def mask_data(data, keys):
    """递归对字典中命中键名的值打码"""
    if not keys:
        return data
    key_set = set(keys)
    return _mask(data, key_set)


def _mask(value, key_set):
    if isinstance(value, dict):
        return {key: (MASK if key in key_set else _mask(item, key_set))
                for key, item in value.items()}
    if isinstance(value, list):
        return [_mask(item, key_set) for item in value]
    return value


def mask_text(text: str, keys) -> str:
    """对 JSON 文本脱敏；非 JSON 文本原样返回"""
    if not keys or not text:
        return text
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text
    return json.dumps(mask_data(data, keys), ensure_ascii=False, indent=2)
