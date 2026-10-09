"""变量模板渲染：支持 ${变量} 与命名空间 ${env.变量} / ${sys.变量}"""
import os
import re

from .errors import VariableNotFoundError

_PATTERN = re.compile(r"\$\{([^}]+)\}")

# 命名空间 -> 中文说明
NAMESPACES = {
    "env": "环境配置（--env 文件）",
    "sys": "系统环境变量",
}


class Variables:
    """变量上下文：按来源分区，避免与系统环境变量意外重名。

    - flat：用例 config.variables 与运行时 extract 得到的变量（${name}）
    - env ：--env 配置文件中的变量（${env.name}）
    - sys ：系统环境变量（${sys.NAME}），仅在显式使用命名空间时读取

    无前缀的 ${name} 不会回退到系统环境变量，从根上杜绝「${username}
    意外命中 Windows 系统 USERNAME」这类静默错误。
    """

    def __init__(self, flat: dict = None, env: dict = None):
        self.flat = dict(flat or {})
        self.env = dict(env or {})

    def set(self, name: str, value):
        """写入运行时变量（extract / 框架内部）"""
        self.flat[name] = value

    def resolve(self, name: str):
        name = name.strip()
        prefix, sep, key = name.partition(".")
        if sep == "." and prefix in NAMESPACES:
            if prefix == "env":
                if key in self.env:
                    return self.env[key]
            elif prefix == "sys":
                if key in os.environ:
                    return os.environ[key]
            raise VariableNotFoundError(
                f"变量 ${{{name}}} 未定义：命名空间 {prefix}（{NAMESPACES[prefix]}）中不存在 {key!r}"
            )
        if name in self.flat:
            return self.flat[name]
        raise VariableNotFoundError(
            f"变量 ${{{name}}} 未定义：请检查用例 config.variables 与 extract 提取结果；"
            f"配置变量请用 ${{env.{name}}}，系统变量请用 ${{sys.{name}}}"
        )


def render(value, variables):
    """递归渲染字符串/字典/列表中的 ${var} 占位符。

    整串占位（如 "${env.uid}"）时保留变量的原始类型（数字、字典等），
    嵌入在文本中时（如 "Bearer ${token}"）按字符串替换。
    variables 可传 Variables 对象或普通字典（自动包装为无前缀变量）。
    """
    if not isinstance(variables, Variables):
        variables = Variables(flat=variables)
    if isinstance(value, str):
        return _render_str(value, variables)
    if isinstance(value, dict):
        return {key: render(item, variables) for key, item in value.items()}
    if isinstance(value, list):
        return [render(item, variables) for item in value]
    return value


def _render_str(text: str, variables: Variables):
    whole = _PATTERN.fullmatch(text)
    if whole:
        return variables.resolve(whole.group(1))
    return _PATTERN.sub(lambda m: str(variables.resolve(m.group(1))), text)
