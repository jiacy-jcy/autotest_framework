import os
import unittest
from unittest import mock

import yaml

from atf import analyze
from atf.analyze import analyze_failures, classify_by_rules, print_analysis
from atf.runner import Runner, StepDetail, StepResult, SuiteResult


def _failed_step(name, error, status=None, method="POST", url="/api/x"):
    return StepResult(name, False, 0.01, error, 1000.0,
                      StepDetail(method=method, url=url, status_code=status))


def _suite(steps):
    return SuiteResult("用例", "case.yaml", steps, 0, 999.0)


class TestAnalyze(unittest.TestCase):
    def test_pass_steps_ignored(self):
        suite = _suite([StepResult("ok", True, 0.01, "", 1000.0, StepDetail())])
        self.assertEqual(analyze_failures([suite], use_ai=False), [])

    def test_environment_error(self):
        step = _failed_step("请求", "请求发送失败：连接被拒绝（请检查服务是否启动、网络是否连通）")
        self.assertEqual(classify_by_rules(step)[0], "环境问题")

    def test_auth_error(self):
        step = _failed_step("登录", "断言失败：status_code 期望等于 200，实际为 401", status=401)
        self.assertEqual(classify_by_rules(step)[0], "认证问题")

    def test_server_error(self):
        step = _failed_step("查询", "断言失败：$.code 期望等于 0，实际为 500", status=500)
        self.assertEqual(classify_by_rules(step)[0], "服务端异常")

    def test_api_change_missing_field(self):
        step = _failed_step("查询", "路径 $.data.token 提取失败：响应中找不到字段 'token'")
        self.assertEqual(classify_by_rules(step)[0], "接口变更")

    def test_case_issue(self):
        step = _failed_step("查询", "断言失败：$.code 期望等于 0，实际为 1001")
        self.assertEqual(classify_by_rules(step)[0], "用例问题")

    def test_analyze_collects_failures(self):
        suite = _suite([_failed_step("查询", "断言失败：$.code 期望等于 0，实际为 1001")])
        analyses = analyze_failures([suite], use_ai=False)
        self.assertEqual(len(analyses), 1)
        self.assertEqual(analyses[0].category, "用例问题")
        self.assertEqual(analyses[0].source, "规则")
        self.assertEqual(analyses[0].to_dict()["suite"], "用例")

    def test_print_analysis_handles_empty(self):
        print_analysis([])  # 不应抛出异常


class TestAiFix(unittest.TestCase):
    def test_raw_step_propagates_from_runner(self):
        case = {
            "config": {"name": "结构校验"},
            "teststeps": [{
                "name": "查询",
                "db": {"url": "sqlite:///:memory:", "query": "SELECT 42 AS n"},
                "validate": [{"eq": ["$[0].n", 999]}],
            }],
        }
        suite = Runner().run_case(case)
        self.assertFalse(suite.passed)
        analyses = analyze_failures([suite], use_ai=False)
        self.assertIn("validate", analyses[0].step_yaml)  # 原步骤 YAML 可用于修补建议

    def test_fix_diff_with_mocked_llm(self):
        raw_step = {"name": "登录", "request": {"method": "POST", "url": "/api/login",
                     "json": {"username": "admin", "password": "123456"}},
                    "validate": [{"eq": ["$.code", 999]}]}
        step = StepResult("登录", False, 0.01, "断言失败：$.code 期望等于 999，实际为 0",
                          1000.0, StepDetail(method="POST", url="/api/login", status_code=200),
                          raw_step)
        suite = SuiteResult("用例", "case.yaml", [step], 0, 999.0)
        fixed = dict(raw_step)
        fixed["validate"] = [{"eq": ["$.code", 0]}]
        fixed_yaml = yaml.safe_dump(fixed, allow_unicode=True, sort_keys=False)

        os.environ["ATF_AI_API_KEY"] = "test-key"
        try:
            with mock.patch.object(analyze, "_llm_complete", return_value=fixed_yaml):
                analyses = analyze.analyze_failures([suite], use_ai=True, suggest_fix=True)
        finally:
            os.environ.pop("ATF_AI_API_KEY", None)

        self.assertEqual(len(analyses), 1)
        self.assertTrue(analyses[0].fix)
        self.assertIn("999", analyses[0].fix)
        self.assertIn("建议修改", analyses[0].fix)

    def test_fix_without_api_key_prints_hint(self):
        suite = _suite([_failed_step("查询", "断言失败：$.code 期望等于 0，实际为 1001")])
        os.environ.pop("ATF_AI_API_KEY", None)
        analyses = analyze_failures([suite], use_ai=True, suggest_fix=True)
        self.assertEqual(analyses[0].fix, "")  # 无密钥时不生成修补建议，不崩溃


if __name__ == "__main__":
    unittest.main()
