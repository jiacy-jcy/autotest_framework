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


# is_type 支持的类型写法（不区分大小写，中英文均可）
_TYPE_NAMES = {
    "str": str, "string": str, "字符串": str,
    "int": int, "integer": int, "整数": int,
    "float": float, "number": (int, float), "数字": (int, float),
    "bool": bool, "boolean": bool, "布尔": bool,
    "list": list, "array": list, "列表": list,
    "dict": dict, "object": dict, "对象": dict, "map": dict,
    "null": type(None), "none": type(None), "空": type(None),
}


def _is_type(actual, expected):
    name = str(expected).strip().lower()
    types = _TYPE_NAMES.get(name)
    if types is None:
        return False
    if isinstance(actual, bool) and name not in ("bool", "boolean", "布尔"):
        return False  # bool 是 int 的子类，避免 True 被误判为 int
    return isinstance(actual, types)


def _contains_any(actual, expected):
    """数组包含：任一交集成立即通过（兼容 标量∈数组、数组含标量 两种方向）"""
    try:
        actual_seq = isinstance(actual, (list, tuple, set))
        expected_seq = isinstance(expected, (list, tuple, set))
        if actual_seq and expected_seq:
            return bool(set(actual) & set(expected))
        if actual_seq:
            return expected in actual
        if expected_seq:
            return actual in expected
        return False
    except TypeError:
        return False


def _schema(actual, expected):
    from .schema import validate

    return validate(actual, expected)[0]


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
    "is_type": (_is_type, "类型为"),
    "contains_any": (_contains_any, "包含其一"),
    "schema": (_schema, "符合 JSON Schema"),
}

# 中文比较符别名：YAML 里可以直接写「等于: [$.code, 0]」
ALIASES = {
    "等于": "eq", "不等于": "ne", "大于": "gt", "大于等于": "ge",
    "小于": "lt", "小于等于": "le", "包含": "contains", "不包含": "not_contains",
    "正则匹配": "regex", "长度等于": "len_eq", "属于": "in",
    "类型为": "is_type", "包含其一": "contains_any", "符合模式": "schema",
}


def compare(comparator: str, actual, expected) -> tuple:
    """执行一次比较，返回 (是否通过, 失败原因)"""
    plugins.ensure_loaded()
    name = ALIASES.get(comparator, comparator)
    entry = plugins.registry.comparators.get(name) or COMPARATORS.get(name)
    if entry is None:
        available = "、".join(list(COMPARATORS) + list(ALIASES))
        raise ATFError(f"不支持的比较符：{comparator}，可用：{available}")
    func, desc = entry
    try:
        passed = bool(func(actual, expected))
    except (TypeError, ValueError):
        passed = False
    if passed:
        return True, ""
    if name == "schema":
        from .schema import validate

        return False, validate(actual, expected)[1]
    return False, f"期望{desc or name} {expected!r}，实际为 {actual!r}"
