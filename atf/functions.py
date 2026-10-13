"""内置变量函数：在模板中以 ${函数(参数)} 形式调用

内置：uuid() / timestamp() / rand_str(长度) / int(下界, 上界)
字符串参数需加引号（如 ${rand_str(8)}、${pick('a','b')}）；插件可注册更多函数。
"""
import ast
import random
import string
import time
import uuid as _uuid

from .errors import ATFError


def _fn_uuid() -> str:
    return str(_uuid.uuid4())


def _fn_timestamp() -> int:
    return int(time.time())


def _fn_rand_str(length=8) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choices(alphabet, k=int(length)))


def _fn_rand_int(low, high) -> int:
    return random.randint(int(low), int(high))


BUILTIN = {
    "uuid": _fn_uuid,
    "timestamp": _fn_timestamp,
    "rand_str": _fn_rand_str,
    "int": _fn_rand_int,
}


def evaluate(name: str, arg_text: str):
    func = BUILTIN.get(name)
    if func is None:
        from . import plugins

        plugins.ensure_loaded()
        func = plugins.registry.functions.get(name)
    if func is None:
        raise ATFError(f"未知的变量函数：{name}()（内置：{'、'.join(BUILTIN)}）")
    try:
        return func(*_parse_args(arg_text))
    except ATFError:
        raise
    except (TypeError, ValueError) as exc:
        raise ATFError(f"变量函数 {name}() 参数错误：{exc}") from None


def _parse_args(text: str) -> list:
    text = text.strip()
    if not text:
        return []
    try:
        value = ast.literal_eval(f"({text},)")
    except (ValueError, SyntaxError):
        raise ATFError(f"变量函数参数解析失败：{text}（字符串参数请用引号）") from None
    return list(value) if isinstance(value, tuple) else [value]
