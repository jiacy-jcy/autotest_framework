"""插件系统：注册自定义比较符与提取器，扩展框架能力

两种加载方式：
- 用例级：config.plugins 列出「模块名」，模块需提供 register(registry) 函数
- 生态级：第三方包通过 entry point（组名 atf.plugins）声明，安装后自动加载

插件示例：

    def register(registry):
        registry.register_comparator("约等于", lambda a, b: abs(float(a) - float(b)) <= 0.01, "数值近似相等")
        registry.register_extractor("长度", lambda result, rest: len(result.text))
"""
import importlib
import sys

from .errors import ATFError


class Registry:
    def __init__(self):
        self.comparators = {}   # 名称 -> (判断函数, 中文描述)
        self.extractors = {}    # 前缀 -> 函数(result, 剩余表达式)
        self.functions = {}     # 变量函数名 -> 函数(*args)

    def register_comparator(self, name: str, func, description: str = ""):
        if not callable(func):
            raise ATFError(f"比较符 {name} 的处理函数不可调用")
        self.comparators[name] = (func, description)

    def register_extractor(self, prefix: str, func):
        if not callable(func):
            raise ATFError(f"提取器 {prefix} 的处理函数不可调用")
        self.extractors[prefix] = func

    def register_function(self, name: str, func):
        if not callable(func):
            raise ATFError(f"变量函数 {name} 的处理函数不可调用")
        self.functions[name] = func


registry = Registry()
_loaded = False


def ensure_loaded():
    """确保 entry point 中的插件已加载（只执行一次）"""
    global _loaded
    if _loaded:
        return
    _loaded = True
    for name, plugin in _discover_entrypoints():
        _activate(plugin, name)


def load_plugins(config: dict, search_dirs=None):
    """按 config.plugins 加载用例级插件"""
    ensure_loaded()
    specs = config.get("plugins") if isinstance(config, dict) else None
    if not specs:
        return
    if isinstance(specs, str):
        specs = [item.strip() for item in specs.split(",") if item.strip()]
    if not isinstance(specs, list):
        raise ATFError("config.plugins 必须是列表或逗号分隔的字符串")
    for spec in specs:
        module = _import_module(str(spec), search_dirs)
        _activate(module, str(spec))


def _discover_entrypoints() -> list:
    try:
        from importlib.metadata import entry_points
    except ImportError:
        return []
    try:
        group = entry_points()
        selected = group.select(group="atf.plugins") if hasattr(group, "select") \
            else group.get("atf.plugins", [])
    except Exception:
        return []
    plugins = []
    for entry in selected:
        try:
            plugins.append((entry.name, entry.load()))
        except Exception as exc:
            print(f"提示：加载插件 {entry.name} 失败：{exc}")
    return plugins


def _import_module(name: str, search_dirs):
    for directory in (search_dirs or []):
        if directory and directory not in sys.path:
            sys.path.insert(0, directory)
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise ATFError(f"无法导入插件模块 {name}：{exc}（请确认模块位置或加入 PYTHONPATH）") from None


def _activate(plugin, name: str):
    register = getattr(plugin, "register", None)
    if callable(register):
        register(registry)
    else:
        print(f"提示：插件 {name} 未提供 register(registry) 函数，已跳过")
