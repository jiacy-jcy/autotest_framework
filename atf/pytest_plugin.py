"""pytest 插件：让 ATF 的 YAML 用例在 pytest 中直接运行

安装 atf（含 pytest 环境）后，pytest 会通过 entry point 自动加载本插件，
把带有 teststeps 的 *.yaml / *.yml 文件收集为 pytest 用例，
从而融入 pytest 的用例选择（-k）、报告与 CI 生态。
"""
import yaml
import pytest

from .errors import CaseFormatError
from .parser import load_case_file, load_env_file
from .runner import Runner


def pytest_addoption(parser):
    group = parser.getgroup("atf", "ATF 接口自动化")
    group.addoption("--atf-env", action="store", default=None, metavar="文件",
                    help="ATF 环境变量配置文件（YAML 键值对），命名空间为 env")
    group.addoption("--atf-timeout", action="store", type=float, default=30.0,
                    help="ATF 请求超时秒数（默认 30）")


def pytest_configure(config):
    config.addinivalue_line("markers", "atf: ATF 接口自动化用例")
    config._atf_env = {}
    env_file = config.getoption("--atf-env")
    if env_file:
        try:
            config._atf_env = load_env_file(env_file)
        except CaseFormatError as exc:
            raise pytest.UsageError(str(exc)) from exc


def pytest_collect_file(file_path, parent):
    if file_path.suffix.lower() in (".yaml", ".yml"):
        return AtfCaseFile.from_parent(parent, path=file_path)
    return None


class AtfCaseFile(pytest.File):
    def collect(self):
        # 只接管结构化合法的 ATF 用例：解析失败或缺少 teststeps 时返回空，交给其它插件
        try:
            data = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            return []
        if not isinstance(data, dict) or "teststeps" not in data:
            return []
        case = load_case_file(self.path)
        name = (case.get("config") or {}).get("name") or self.path.stem
        item = AtfCaseItem.from_parent(self, name=name)
        item.atf_case = case
        return [item]


class AtfCaseItem(pytest.Item):
    atf_case = None

    def runtest(self):
        env = getattr(self.config, "_atf_env", {})
        timeout = self.config.getoption("--atf-timeout")
        suite = Runner(env=env, timeout=timeout).run_case(self.atf_case)
        if not suite.passed:
            raise AtfCaseFailed(suite)

    def repr_failure(self, excinfo, style=None):
        if isinstance(excinfo.value, AtfCaseFailed):
            return excinfo.value.render()
        return super().repr_failure(excinfo, style=style)

    def reportinfo(self):
        return self.path, 0, f"ATF 用例：{self.name}"


class AtfCaseFailed(Exception):
    """ATF 用例执行失败，携带各步骤结果用于中文失败展示"""

    def __init__(self, suite):
        self.suite = suite
        super().__init__(f"用例「{suite.name}」执行失败")

    def render(self) -> str:
        lines = [f"ATF 用例失败：{self.suite.name}"]
        for step in self.suite.steps:
            mark = "√" if step.passed else "×"
            lines.append(f"  {mark} {step.name}（{step.elapsed:.2f}秒）")
            if step.error:
                lines.append(f"      {step.error}")
        if self.suite.skipped:
            lines.append(f"  - 后续 {self.suite.skipped} 个步骤因前置失败被跳过")
        return "\n".join(lines)
