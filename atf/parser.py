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
        if not isinstance(step, dict) or "request" not in step:
            raise CaseFormatError(f"用例文件 {p.name} 第 {index} 个步骤缺少 request 定义")
        step.setdefault("name", f"步骤{index}")
    data.setdefault("config", {})
    data["__file__"] = str(p)
    return data


def load_env_file(path) -> dict:
    """加载环境变量配置文件（扁平的 YAML 键值对）"""
    p = Path(path)
    if not p.exists():
        raise CaseFormatError(f"环境配置文件不存在：{p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise CaseFormatError(f"环境配置文件 {p.name} 的内容必须是 YAML 键值对")
    return data


def find_case_files(path) -> list:
    """根据传入路径返回用例文件列表：目录时收集全部 yaml 文件"""
    p = Path(path)
    if p.is_dir():
        files = sorted(p.glob("*.yaml")) + sorted(p.glob("*.yml"))
        if not files:
            raise CaseFormatError(f"目录 {p} 下没有找到 .yaml/.yml 用例文件")
        return files
    return [p]
