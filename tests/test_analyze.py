import unittest

from atf.analyze import analyze_failures, classify_by_rules, print_analysis
from atf.runner import StepDetail, StepResult, SuiteResult


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


if __name__ == "__main__":
    unittest.main()
