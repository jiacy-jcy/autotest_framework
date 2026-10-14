"""JSON Schema 断言（可选依赖 atf[schema]，使用 jsonschema 库）

用法：
    - schema: ["$.data", schemas/user.json]   # 文件路径相对用例文件所在目录
    - schema: ["$.data.name", {type: string}]  # 也可直接内联
"""
import json
from pathlib import Path

from .errors import ATFError


def load_schema_file(path, base_dir=None) -> dict:
    """加载 JSON Schema 文件：绝对路径原样，相对路径基于用例文件目录"""
    p = Path(path)
    if not p.is_absolute() and base_dir:
        p = Path(base_dir) / p
    if not p.exists():
        raise ATFError(f"JSON Schema 文件不存在：{p}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ATFError(f"JSON Schema 文件 {p.name} 不是合法 JSON：{exc}") from None


def validate(instance, schema) -> tuple:
    """按 JSON Schema 校验，返回 (是否通过, 中文失败原因)"""
    if not isinstance(schema, dict):
        raise ATFError("JSON Schema 必须是对象（支持内联写法或文件路径）")
    try:
        from jsonschema.validators import Draft202012Validator, validator_for
    except ImportError:
        raise ATFError("JSON Schema 断言需要 jsonschema，请先安装：pip install atf[schema]") from None
    validator_class = validator_for(schema) or Draft202012Validator
    errors = sorted(validator_class(schema).iter_errors(instance),
                    key=lambda error: list(error.absolute_path))
    if not errors:
        return True, ""
    first = errors[0]
    location = "/".join(str(item) for item in first.absolute_path) or "根节点"
    return False, f"不符合 JSON Schema（位置：{location}）：{_short(first.message)}"


def _short(message: str, limit: int = 200) -> str:
    message = str(message).replace("\n", " ")
    return message if len(message) <= limit else message[:limit] + "……"
