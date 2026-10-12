import sys
import tempfile
import unittest
from pathlib import Path

from atf.errors import ATFError
from atf.runner import Runner

HOOKS_SOURCE = '''
calls = []

def before_case(context):
    calls.append("before_case")
    context.set("injected", "来自钩子")

def before_step(context):
    calls.append("before_step:" + context.step["name"])

def after_step(context):
    calls.append("after_step:" + context.step["name"])
'''


def _case(tmp, hooks):
    return {
        "config": {"name": "钩子用例", "hooks": hooks},
        "__file__": str(Path(tmp, "case.yaml")),
        "teststeps": [{
            "name": "查询常量",
            "db": {"url": "sqlite:///:memory:", "query": "SELECT 1 AS x"},
            "validate": [{"eq": ["$[0].x", 1]}, {"eq": ["${injected}", "来自钩子"]}],
        }],
    }


class TestHooks(unittest.TestCase):
    def setUp(self):
        sys.modules.pop("atf_hook_probe", None)

    def test_hooks_run_and_set_variables(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "atf_hook_probe.py").write_text(HOOKS_SOURCE, encoding="utf-8")
            hooks = {
                "before_case": "atf_hook_probe.before_case",
                "before_step": "atf_hook_probe.before_step",
                "after_step": "atf_hook_probe.after_step",
            }
            suite = Runner().run_case(_case(tmp, hooks))
            self.assertTrue(suite.passed, suite.steps[0].error)
            calls = sys.modules["atf_hook_probe"].calls
            self.assertIn("before_case", calls)
            self.assertIn("before_step:查询常量", calls)
            self.assertIn("after_step:查询常量", calls)

    def test_after_step_runs_even_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "atf_hook_probe.py").write_text(HOOKS_SOURCE, encoding="utf-8")
            case = _case(tmp, {"after_step": "atf_hook_probe.after_step"})
            case["teststeps"][0]["validate"] = [{"eq": ["$[0].x", 999]}]
            suite = Runner().run_case(case)
            self.assertFalse(suite.passed)
            self.assertIn("after_step:查询常量", sys.modules["atf_hook_probe"].calls)

    def test_unknown_event_chinese_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ATFError) as ctx:
                Runner().run_case(_case(tmp, {"before_all": "x.y"}))
            self.assertIn("未知的钩子事件", str(ctx.exception))

    def test_missing_hook_module_chinese_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ATFError) as ctx:
                Runner().run_case(_case(tmp, {"before_case": "no_such_module.func"}))
            self.assertIn("无法导入", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
