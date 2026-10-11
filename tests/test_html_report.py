import tempfile
import unittest
from pathlib import Path

from atf.html_report import write_html_report
from atf.runner import StepDetail, StepResult, SuiteResult


def _detail():
    return StepDetail(method="POST", url="http://127.0.0.1/api/login", status_code=200,
                      request_body='{"username": "admin"}', response_body='{"code": 0}')


def _passing_suite():
    step = StepResult("登录获取令牌", True, 0.02, "", 1000.0, _detail())
    return SuiteResult("用户模块接口流程", "cases/user_flow.yaml", [step], 0, 999.0)


def _failing_suite():
    ok = StepResult("登录", True, 0.02, "", 1000.0, _detail())
    bad_detail = StepDetail(method="GET", url="http://x/api/users/1", status_code=200,
                            response_body='{"code": 1001}')
    bad = StepResult("查询<x>", False, 0.03, "断言失败：$.code 期望等于 0，实际为 1001", 1001.0, bad_detail)
    return SuiteResult("失败用例", "cases/bad.yaml", [ok, bad], 1, 999.0)


class TestHtmlReport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_generates_file(self):
        path = write_html_report([_passing_suite()], self.dir / "r.html")
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        self.assertIn("ATF 智测 · 测试报告", content)
        self.assertIn("通过", content)

    def test_directory_argument_gets_default_filename(self):
        path = write_html_report([_passing_suite()], self.dir / "out")
        self.assertEqual(path.name, "atf-report.html")
        self.assertTrue(path.exists())

    def test_summary_and_failure_shown(self):
        content = write_html_report(
            [_passing_suite(), _failing_suite()], self.dir / "r.html"
        ).read_text(encoding="utf-8")
        self.assertIn("通过率", content)
        self.assertIn("断言失败", content)

    def test_escapes_special_characters(self):
        content = write_html_report([_failing_suite()], self.dir / "r.html").read_text(encoding="utf-8")
        self.assertIn("查询&lt;x&gt;", content)
        self.assertNotIn("查询<x>", content)


if __name__ == "__main__":
    unittest.main()
