import json
import tempfile
import unittest
from pathlib import Path

from atf.allure_report import write_allure_results
from atf.runner import StepDetail, StepResult, SuiteResult


def _failing_suite():
    detail = StepDetail(method="POST", url="http://x/api/login", status_code=200)
    ok = StepResult("登录", True, 0.02, "", 1000.0, detail)
    bad = StepResult("查询", False, 0.03, "断言失败：期望等于 0", 1001.0, detail)
    return SuiteResult("失败用例", "cases/bad.yaml", [ok, bad], 1, 999.0)


class TestAllureReport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "allure-results"

    def tearDown(self):
        self.tmp.cleanup()

    def test_writes_result_and_environment(self):
        path = write_allure_results([_failing_suite()], self.dir)
        self.assertEqual(len(list(path.glob("*-result.json"))), 1)
        self.assertTrue((path / "environment.properties").exists())

    def test_result_content(self):
        path = write_allure_results([_failing_suite()], self.dir)
        result = json.loads(next(path.glob("*-result.json")).read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["name"], "失败用例")
        self.assertEqual(len(result["steps"]), 3)  # 2 个步骤 + 1 条跳过记录
        statuses = [s["status"] for s in result["steps"]]
        self.assertIn("passed", statuses)
        self.assertIn("failed", statuses)
        self.assertIn("skipped", statuses)
        self.assertIn("期望等于 0", result["statusDetails"]["message"])

    def test_passing_suite_status(self):
        detail = StepDetail(method="POST", url="http://x/api/login", status_code=200)
        suite = SuiteResult("通过用例", "cases/ok.yaml",
                            [StepResult("登录", True, 0.02, "", 1000.0, detail)], 0, 999.0)
        path = write_allure_results([suite], self.dir)
        result = json.loads(next(path.glob("*-result.json")).read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "passed")


if __name__ == "__main__":
    unittest.main()
