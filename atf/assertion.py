"""断言引擎：支持中英文比较符，失败信息全中文（中文友好特性之一）"""
import operator
import re

from . import plugins
from .errors import ATFError


def _ordering(op):
    """大小比较前先做数字转换，兼容 "3" 与 3 混用的情况"""
    def check(actual, expected):
        try:
            actual, expected = float(actual), float(expected)
        except (TypeError, ValueError):
            pass
        try:
            return op(actual, expected)
        except TypeError:
            return False
    return check


def _eq(actual, expected):
    """相等判断：先做严格比较，失败时回退到字符串比较（兼容 "0" 与 0）"""
    return actual == expected or str(actual) == str(expected)


def _ne(actual, expected):
    return not _eq(actual, expected)


# 比较符 -> (判断函数, 中文描述)
COMPARATORS = {
    "eq": (_eq, "等于"),
    "ne": (_ne, "不等于"),
    "gt": (_ordering(operator.gt), "大于"),
    "ge": (_ordering(operator.ge), "大于等于"),
    "lt": (_ordering(operator.lt), "小于"),
    "le": (_ordering(operator.le), "小于等于"),
    "contains": (lambda a, b: b in a, "包含"),
    "not_contains": (lambda a, b: b not in a, "不包含"),
    "regex": (lambda a, b: re.search(str(b), str(a)) is not None, "正则匹配"),
    "len_eq": (lambda a, b: len(a) == int(b), "长度等于"),
    "in": (lambda a, b: a in b, "属于"),
    "startswith": (lambda a, b: str(a).startswith(str(b)), "以此开头"),
    "endswith": (lambda a, b: str(a).endswith(str(b)), "以此结尾"),
}

# 中文比较符别名：YAML 里可以直接写「等于: [$.code, 0]」
ALIASES = {
    "等于": "eq", "不等于": "ne", "大于": "gt", "大于等于": "ge",
    "小于": "lt", "小于等于": "le", "包含": "contains", "不包含": "not_contains",
    "正则匹配": "regex", "长度等于": "len_eq", "属于": "in",
}


def compare(comparator: str, actual, expected) -> tuple:
    """执行一次比较，返回 (是否通过, 失败原因)"""
    plugins.ensure_loaded()
    name = ALIASES.get(comparator, comparator)
    if name in plugins.registry.comparators:
        func, desc = plugins.registry.comparators[name]
        try:
            passed = bool(func(actual, expected))
        except (TypeError, ValueError):
            passed = False
        if passed:
            return True, ""
        return False, f"期望{desc or name} {expected!r}，实际为 {actual!r}"
    if name not in COMPARATORS:
        available = "、".join(list(COMPARATORS) + list(ALIASES))
        raise ATFError(f"不支持的比较符：{comparator}，可用：{available}")
    func, desc = COMPARATORS[name]
    try:
        passed = bool(func(actual, expected))
    except (TypeError, ValueError):
        passed = False
    if passed:
        return True, ""
    return False, f"期望{desc} {expected!r}，实际为 {actual!r}"
