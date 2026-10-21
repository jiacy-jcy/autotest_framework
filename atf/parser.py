"""YAML 用例加载与格式校验（错误信息全中文）"""
from pathlib import Path

import yaml

from .errors import CaseFormatError


def load_case_file(path) -> dict:
    """加载单个用例文件并做基本格式校验"""
    p = Path(path)
    if not p.exists():
        raise CaseFormatError(f"用例文件不存在：{p}")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CaseFormatError(f"用例文件 {p.name} 的 YAML 语法有误：{exc}") from None
    if not isinstance(data, dict):
        raise CaseFormatError(f"用例文件 {p.name} 的内容必须是 YAML 对象")
    steps = data.get("teststeps")
    if not isinstance(steps, list) or not steps:
        raise CaseFormatError(f"用例文件 {p.name} 缺少非空的 teststeps 列表")
    for index, step in enumerate(steps, 1):
        if not isinstance(step, dict) or not ("request" in step or "db" in step or "use" in step):
            raise CaseFormatError(f"用例文件 {p.name} 第 {index} 个步骤缺少 request、db 或 use 定义")
        step.setdefault("name", f"步骤{index}")
    data.setdefault("config", {})
    data["__file__"] = str(p)
    return data


_RESERVED_ENV_KEYS = ("environments", "default")


def load_env_file(path, name=None) -> dict:
    """加载环境变量配置文件，支持两种写法：

    - 扁平键值对（原有写法）：所有键直接作为变量
    - 多环境分区：environments 下按名称分区，用 name 参数选择；
      顶层其余键作为公共变量，分区中的同名键覆盖公共变量
    """
    p = Path(path)
    if not p.exists():
        raise CaseFormatError(f"环境配置文件不存在：{p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise CaseFormatError(f"环境配置文件 {p.name} 的内容必须是 YAML 键值对")
    environments = data.get("environments")
    if not environments:
        return data
    if not isinstance(environments, dict):
        raise CaseFormatError(f"环境配置文件 {p.name} 的 environments 必须是键值对")
    available = "、".join(environments)
    name = name or data.get("default")
    if not name:
        raise CaseFormatError(
            f"环境配置文件 {p.name} 包含多个环境（{available}），"
            f"请用 --env-name 指定，或在文件中用 default 声明默认环境"
        )
    chosen = environments.get(name)
    if chosen is None:
        raise CaseFormatError(f"环境 {name} 在 {p.name} 中不存在，可选：{available}")
    if not isinstance(chosen, dict):
        raise CaseFormatError(f"环境配置文件 {p.name} 中环境 {name} 的内容必须是键值对")
    common = {key: value for key, value in data.items() if key not in _RESERVED_ENV_KEYS}
    return {**common, **chosen}


def find_case_files(path) -> list:
    """根据传入路径返回用例文件列表：目录时收集全部 yaml 文件"""
    return _iter_yaml_files(path)


def _iter_yaml_files(path) -> list:
    p = Path(path)
    if p.is_dir():
        files = sorted(p.glob("*.yaml")) + sorted(p.glob("*.yml"))
        if not files:
            raise CaseFormatError(f"目录 {p} 下没有找到 .yaml/.yml 文件")
        return files
    if not p.exists():
        raise CaseFormatError(f"路径不存在：{p}")
    return [p]


def _read_raw_yaml(path):
    p = Path(path)
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CaseFormatError(f"文件 {p.name} 的 YAML 语法有误：{exc}") from None


def is_suite(data) -> bool:
    """套件文件：含 cases 列表且不含 teststeps"""
    return isinstance(data, dict) and "cases" in data and "teststeps" not in data


def resolve_case_files(path) -> list:
    """把 目录 / 用例文件 / 套件文件 统一解析为用例文件路径列表。

    套件文件（含 cases 列表）会被展开为其中的用例，路径相对套件文件所在目录。
    """
    result = []
    for candidate in _iter_yaml_files(path):
        data = _read_raw_yaml(candidate)
        if not is_suite(data):
            result.append(Path(candidate))
            continue
        base = Path(candidate).parent
        cases = data.get("cases")
        if not isinstance(cases, list) or not cases:
            raise CaseFormatError(f"套件 {Path(candidate).name} 的 cases 必须是非空列表")
        for item in cases:
            case_path = base / str(item)
            if case_path.suffix.lower() not in (".yaml", ".yml"):
                raise CaseFormatError(f"套件 {Path(candidate).name} 只能引用 .yaml/.yml 用例：{case_path}")
            if not case_path.exists():
                raise CaseFormatError(f"套件 {Path(candidate).name} 引用的用例不存在：{case_path}")
            result.append(case_path)
    return result


def case_tags(case: dict) -> list:
    """读取用例标签：config.tags 或顶层 tags，均支持列表或逗号分隔字符串"""
    tags = (case.get("config") or {}).get("tags")
    if tags is None:
        tags = case.get("tags")
    if tags is None:
        return []
    if isinstance(tags, str):
        return [item.strip() for item in tags.split(",") if item.strip()]
    if isinstance(tags, list):
        return [str(item) for item in tags]
    raise CaseFormatError("tags 必须是列表或逗号分隔的字符串")
