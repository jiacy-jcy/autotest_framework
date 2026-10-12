"""钩子函数：在用例生命周期插入自定义 Python 逻辑

在用例 config.hooks 中以「模块.函数」形式引用，例如：

    config:
      hooks:
        before_case: hooks.before_case
        before_step: myproj.hooks.sign_request
        after_step:  myproj.hooks.log_step

支持的事件：before_case、after_case、before_step、after_step；
钩子函数接收单个 HookContext 参数，可通过 context.set/get 读写变量。
"""
import importlib
import sys
from dataclasses import dataclass, field

from .errors import ATFError, VariableNotFoundError

EVENTS = ("before_case", "after_case", "before_step", "after_step")
_EVENT_HINT = "before_case / after_case / before_step / after_step"


@dataclass
class HookContext:
    """钩子上下文：暴露变量、配置、当前步骤与执行结果"""

    variables: object
    config: dict = field(default_factory=dict)
    case: dict = None
    step: dict = None
    result: object = None

    def set(self, name, value):
        """写入一个运行时变量，供用例后续以 ${name} 引用"""
        self.variables.set(name, value)

    def get(self, name, default=None):
        """读取变量，不存在时返回默认值"""
        try:
            return self.variables.resolve(name)
        except VariableNotFoundError:
            return default


def load_hooks(config: dict, search_dirs=None) -> dict:
    specs = config.get("hooks") or {}
    if not isinstance(specs, dict):
        raise ATFError("config.hooks 必须是键值对，例如：hooks: {before_step: 模块.函数}")
    unknown = [name for name in specs if name not in EVENTS]
    if unknown:
        raise ATFError(f"未知的钩子事件：{'、'.join(unknown)}（可用：{_EVENT_HINT}）")
    hooks = {}
    for event in EVENTS:
        dotted = specs.get(event)
        if dotted:
            hooks[event] = resolve_callable(str(dotted), search_dirs)
    return hooks


def resolve_callable(dotted: str, search_dirs=None):
    """把「模块.函数」解析为可调用对象，必要时把目录临时加入 sys.path"""
    module_name, sep, attr = dotted.rpartition(".")
    if not sep:
        raise ATFError(f"钩子必须写成「模块.函数」形式：{dotted}")
    for directory in (search_dirs or []):
        if directory and directory not in sys.path:
            sys.path.insert(0, directory)
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise ATFError(
            f"无法导入钩子模块 {module_name}：{exc}"
            f"（请确认模块文件位置，或将其目录加入 PYTHONPATH）"
        ) from None
    func = getattr(module, attr, None)
    if not callable(func):
        raise ATFError(f"钩子 {dotted} 不存在或不可调用")
    return func
