"""执行引擎：渲染变量 → 发送请求 → 提取变量 → 断言，收集中文结果"""
import time
from dataclasses import dataclass, field

import httpx

from . import assertion, extractor, template
from .errors import AssertFailError, ATFError, CaseFormatError
from .template import Variables


@dataclass
class StepResult:
    name: str
    passed: bool
    elapsed: float
    error: str = ""


@dataclass
class SuiteResult:
    name: str
    source: str
    steps: list = field(default_factory=list)
    skipped: int = 0

    @property
    def passed(self) -> bool:
        return all(step.passed for step in self.steps)


def join_url(base_url: str, url: str) -> str:
    if url.startswith(("http://", "https://")):
        return url
    return base_url.rstrip("/") + "/" + url.lstrip("/")


class Runner:
    def __init__(self, variables: dict = None, env: dict = None, timeout: float = 30.0):
        # variables：无前缀基础变量；env：--env 配置文件变量（命名空间 env）
        self.base_variables = dict(variables or {})
        self.env_variables = dict(env or {})
        self.timeout = timeout

    def run_case(self, case: dict) -> SuiteResult:
        config = case.get("config") or {}
        variables = Variables(
            flat={**self.base_variables, **(config.get("variables") or {})},
            env=self.env_variables,
        )
        suite = SuiteResult(name=config.get("name", "未命名用例"), source=case.get("__file__", ""))
        steps = case["teststeps"]
        with httpx.Client(timeout=self.timeout) as client:
            for index, step in enumerate(steps):
                result = self._run_step(client, step, variables, config)
                suite.steps.append(result)
                if not result.passed:
                    # 流程型用例：步骤失败后跳过后续，避免一连串无意义的报错
                    suite.skipped = len(steps) - index - 1
                    break
        return suite

    def _run_step(self, client, step, variables, config) -> StepResult:
        start = time.perf_counter()
        try:
            self._execute(client, step, variables, config)
            return StepResult(step["name"], True, time.perf_counter() - start)
        except ATFError as exc:
            return StepResult(step["name"], False, time.perf_counter() - start, str(exc))
        except httpx.HTTPError as exc:
            return StepResult(step["name"], False, time.perf_counter() - start,
                              f"请求发送失败：{exc}（请检查服务是否启动、网络是否连通）")

    def _execute(self, client, step, variables, config):
        request = template.render(step["request"], variables)
        if not isinstance(request, dict):
            raise CaseFormatError(f"步骤「{step['name']}」的 request 必须是键值对")
        request = dict(request)
        method = str(request.pop("method", "GET")).upper()
        base_url = template.render(config.get("base_url", ""), variables)
        url = join_url(base_url, str(request.pop("url", "")))
        headers = {**(config.get("headers") or {}), **(request.pop("headers", None) or {})}

        response = client.request(method, url, headers=headers, **request)

        for var_name, expression in (step.get("extract") or {}).items():
            variables.set(
                var_name,
                extractor.extract_value(response, template.render(expression, variables)),
            )
        for rule in step.get("validate") or []:
            self._check(rule, response, variables)

    def _check(self, rule, response, variables):
        if not isinstance(rule, dict) or len(rule) != 1:
            raise CaseFormatError(f"断言格式错误：{rule!r}，应写成 - 比较符: [检查对象, 期望值]")
        (comparator, args), = rule.items()
        if not isinstance(args, list) or len(args) < 2:
            raise CaseFormatError(f"断言格式错误：{rule!r}，应写成 - 比较符: [检查对象, 期望值]")
        expression = template.render(args[0], variables)
        expected = template.render(args[1], variables)
        actual = extractor.extract_value(response, expression)
        passed, reason = assertion.compare(str(comparator), actual, expected)
        if not passed:
            custom = f"（{args[2]}）" if len(args) > 2 else ""
            raise AssertFailError(f"断言失败{custom}：{expression} {reason}")
