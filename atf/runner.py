"""执行引擎：渲染变量 → 发送请求 → 提取变量 → 断言，收集中文结果"""
import json
import time
from dataclasses import dataclass, field

import httpx

from . import assertion, extractor, template
from .errors import AssertFailError, ATFError, CaseFormatError
from .template import Variables

_MAX_PREVIEW = 3000


@dataclass
class StepDetail:
    """步骤详情，供 HTML / Allure 报告使用"""

    method: str = ""
    url: str = ""
    status_code: int = None
    request_body: str = ""
    response_body: str = ""


@dataclass
class StepResult:
    name: str
    passed: bool
    elapsed: float
    error: str = ""
    started_at: float = 0.0
    detail: StepDetail = field(default_factory=StepDetail)


@dataclass
class SuiteResult:
    name: str
    source: str
    steps: list = field(default_factory=list)
    skipped: int = 0
    started_at: float = 0.0

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

    def run_case_all(self, case: dict) -> list:
        """执行用例：若 config.datas 指定了数据源，则按行展开为多次执行"""
        datas = (case.get("config") or {}).get("datas")
        if not datas:
            return [self.run_case(case)]
        if isinstance(datas, list):
            rows = datas
        else:
            from .data import load_data_file, resolve_data_path

            rows = load_data_file(resolve_data_path(case, datas))
        results = []
        for index, row in enumerate(rows, 1):
            suffix = str(row.get("case_name") or row.get("用例名") or f"第{index}行")
            results.append(self.run_case(case, row=row, name_suffix=suffix))
        return results

    def run_case(self, case: dict, row: dict = None, name_suffix: str = None) -> SuiteResult:
        config = case.get("config") or {}
        variables = Variables(
            flat={**self.base_variables, **(config.get("variables") or {}), **(row or {})},
            env=self.env_variables,
        )
        name = config.get("name", "未命名用例")
        if name_suffix:
            name = f"{name} - {name_suffix}"
        suite = SuiteResult(
            name=name,
            source=case.get("__file__", ""),
            started_at=time.time(),
        )
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
        detail = StepDetail()
        started_at = time.time()
        start = time.perf_counter()
        try:
            self._execute(client, step, variables, config, detail)
            return StepResult(step["name"], True, time.perf_counter() - start,
                              "", started_at, detail)
        except ATFError as exc:
            return StepResult(step["name"], False, time.perf_counter() - start,
                              str(exc), started_at, detail)
        except httpx.HTTPError as exc:
            return StepResult(step["name"], False, time.perf_counter() - start,
                              f"请求发送失败：{exc}（请检查服务是否启动、网络是否连通）",
                              started_at, detail)

    def _execute(self, client, step, variables, config, detail: StepDetail):
        if "db" in step:
            self._execute_db(step, variables, detail)
        else:
            self._execute_http(client, step, variables, config, detail)

    def _execute_http(self, client, step, variables, config, detail: StepDetail):
        request = template.render(step["request"], variables)
        if not isinstance(request, dict):
            raise CaseFormatError(f"步骤「{step['name']}」的 request 必须是键值对")
        request = dict(request)
        method = str(request.pop("method", "GET")).upper()
        base_url = template.render(config.get("base_url", ""), variables)
        url = join_url(base_url, str(request.pop("url", "")))
        headers = {**(config.get("headers") or {}), **(request.pop("headers", None) or {})}

        detail.method = method
        detail.url = url
        detail.request_body = _preview_request(request)

        response = client.request(method, url, headers=headers, **request)
        detail.status_code = response.status_code
        detail.response_body = _truncate(response.text)
        self._post_process(response, step, variables)

    def _execute_db(self, step, variables, detail: StepDetail):
        from .db import query

        db_config = template.render(step["db"], variables)
        if not isinstance(db_config, dict):
            raise CaseFormatError(f"步骤「{step['name']}」的 db 必须是键值对")
        detail.method = "DB"
        detail.url = str(db_config.get("query", ""))
        result = query(db_config)
        detail.response_body = result.text
        self._post_process(result, step, variables)

    def _post_process(self, result, step, variables):
        for var_name, expression in (step.get("extract") or {}).items():
            variables.set(
                var_name,
                extractor.extract_value(result, template.render(expression, variables)),
            )
        for rule in step.get("validate") or []:
            self._check(rule, result, variables)

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


def _preview_request(request: dict) -> str:
    if "json" in request:
        return json.dumps(request["json"], ensure_ascii=False, indent=2)
    if "params" in request:
        return json.dumps(request["params"], ensure_ascii=False, indent=2)
    if "data" in request:
        data = request["data"]
        return data if isinstance(data, str) else str(data)
    return ""


def _truncate(text: str, limit: int = _MAX_PREVIEW) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n……（内容过长，已截断）"
