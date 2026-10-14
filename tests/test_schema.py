import tempfile
import unittest
from pathlib import Path

from atf.errors import ATFError
from atf.runner import Runner
from atf.schema import load_schema_file, validate

try:
    import jsonschema  # noqa: F401
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

_SIMPLE = {
    "type": "object", "required": ["n"],
    "properties": {"n": {"type": "integer"}},
}


@unittest.skipUnless(HAS_JSONSCHEMA, "未安装 jsonschema")
class TestSchema(unittest.TestCase):
    def test_validate_pass(self):
        ok, reason = validate({"n": 1}, _SIMPLE)
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_validate_fail_chinese_reason_with_location(self):
        ok, reason = validate({"n": "x"}, _SIMPLE)
        self.assertFalse(ok)
        self.assertIn("不符合 JSON Schema", reason)
        self.assertIn("位置：n", reason)

    def test_validate_non_dict_schema_error(self):
        with self.assertRaises(ATFError):
            validate({}, "not-a-schema")

    def test_load_schema_file_relative_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "s.json").write_text('{"type": "object"}', encoding="utf-8")
            self.assertEqual(load_schema_file("s.json", tmp), {"type": "object"})
            with self.assertRaises(ATFError):
                load_schema_file("nope.json", tmp)

    def test_schema_file_and_inline_in_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "s.json").write_text('{"type": "object", "required": ["n"],'
                                           ' "properties": {"n": {"type": "integer"}}}',
                                           encoding="utf-8")
            case = {
                "config": {"name": "结构校验"},
                "__file__": str(Path(tmp, "case.yaml")),
                "teststeps": [{
                    "name": "查询",
                    "db": {"url": "sqlite:///:memory:", "query": "SELECT 42 AS n"},
                    "validate": [
                        {"schema": ["$[0]", "s.json"]},
                        {"schema": ["$[0].n", {"type": "integer"}]},
                    ],
                }],
            }
            suite = Runner().run_case(case)
            self.assertTrue(suite.passed, suite.steps[0].error)

    def test_schema_failure_in_case_reports_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "s.json").write_text('{"type": "object", "required": ["n"],'
                                           ' "properties": {"n": {"type": "string"}}}',
                                           encoding="utf-8")
            case = {
                "config": {"name": "结构校验"},
                "__file__": str(Path(tmp, "case.yaml")),
                "teststeps": [{
                    "name": "查询",
                    "db": {"url": "sqlite:///:memory:", "query": "SELECT 42 AS n"},
                    "validate": [{"schema": ["$[0]", "s.json"]}],
                }],
            }
            suite = Runner().run_case(case)
            self.assertFalse(suite.passed)
            self.assertIn("不符合 JSON Schema", suite.steps[0].error)
            self.assertIn("位置：n", suite.steps[0].error)


if __name__ == "__main__":
    unittest.main()
