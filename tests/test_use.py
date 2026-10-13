import tempfile
import unittest
from pathlib import Path

from atf.errors import ATFError
from atf.runner import Runner

COMMON = """
config:
  name: 前置
teststeps:
  - name: 取值
    db:
      url: "sqlite:///:memory:"
      query: "SELECT 42 AS n"
    extract:
      n: "$[0].n"
    validate:
      - eq: ["$[0].n", 42]
"""


class TestUse(unittest.TestCase):
    def test_use_inlines_and_shares_variables(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "common.yaml").write_text(COMMON, encoding="utf-8")
            case = {
                "config": {"name": "主用例"},
                "__file__": str(Path(tmp, "main.yaml")),
                "teststeps": [
                    {"use": "common.yaml"},
                    {"name": "引用上一步变量", "db": {"url": "sqlite:///:memory:",
                                                   "query": "SELECT 1 AS x"},
                     "validate": [{"eq": ["${n}", 42]}]},
                ],
            }
            suite = Runner().run_case(case)
            self.assertTrue(suite.passed, suite.steps[0].error)
            self.assertEqual(len(suite.steps), 2)
            self.assertEqual(suite.steps[0].name, "前置 / 取值")

    def test_missing_subcase_chinese_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = {
                "config": {"name": "主用例"},
                "__file__": str(Path(tmp, "main.yaml")),
                "teststeps": [{"use": "nope.yaml"}],
            }
            with self.assertRaises(ATFError) as ctx:
                Runner().run_case(case)
            self.assertIn("子用例文件不存在", str(ctx.exception))

    def test_cycle_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.yaml").write_text(
                "config: {name: A}\nteststeps:\n  - use: b.yaml\n", encoding="utf-8")
            Path(tmp, "b.yaml").write_text(
                "config: {name: B}\nteststeps:\n  - use: a.yaml\n", encoding="utf-8")
            case = {
                "config": {"name": "主用例"},
                "__file__": str(Path(tmp, "a.yaml")),
                "teststeps": [{"use": "b.yaml"}],
            }
            with self.assertRaises(ATFError) as ctx:
                Runner().run_case(case)
            self.assertIn("循环引用", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
