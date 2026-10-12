import tempfile
import unittest
from pathlib import Path

import httpx

from atf import assertion, extractor
from atf.errors import ATFError
from atf.plugins import registry
from atf.runner import Runner

PLUGIN_SOURCE = '''
def register(registry):
    registry.register_comparator("偶数", lambda a, b: int(a) % 2 == 0, "为偶数")
    registry.register_extractor("文本长度", lambda result, rest: len(result.text))
'''


class TestPlugins(unittest.TestCase):
    def test_custom_comparator(self):
        registry.register_comparator("是偶数", lambda a, b: int(a) % 2 == 0, "为偶数")
        self.assertTrue(assertion.compare("是偶数", 4, None)[0])
        self.assertFalse(assertion.compare("是偶数", 3, None)[0])

    def test_custom_extractor(self):
        registry.register_extractor("长度", lambda result, rest: len(result.text))
        resp = httpx.Response(200, text="abcdef")
        self.assertEqual(extractor.extract_value(resp, "长度:"), 6)

    def test_load_plugin_and_use_in_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "atf_probe_plugin.py").write_text(PLUGIN_SOURCE, encoding="utf-8")
            case = {
                "config": {"name": "插件用例", "plugins": ["atf_probe_plugin"]},
                "__file__": str(Path(tmp, "case.yaml")),
                "teststeps": [{
                    "name": "检查",
                    "db": {"url": "sqlite:///:memory:", "query": "SELECT 4 AS n"},
                    "extract": {"size": "文本长度:"},
                    "validate": [{"偶数": ["$[0].n", 0]}, {"gt": ["${size}", 0]}],
                }],
            }
            suite = Runner().run_case(case)
            self.assertTrue(suite.passed, suite.steps[0].error)

    def test_unknown_plugin_module_chinese_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            case = {
                "config": {"name": "x", "plugins": ["no_such_plugin_module"]},
                "__file__": str(Path(tmp, "case.yaml")),
                "teststeps": [{"name": "步骤", "db": {"url": "sqlite:///:memory:", "query": "SELECT 1"}}],
            }
            with self.assertRaises(ATFError) as ctx:
                Runner().run_case(case)
            self.assertIn("无法导入插件模块", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
