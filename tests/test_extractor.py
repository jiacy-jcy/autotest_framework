import unittest

import httpx

from atf.errors import ExtractError
from atf.extractor import extract_value


class TestExtractor(unittest.TestCase):
    def setUp(self):
        self.resp = httpx.Response(
            200, json={"code": 0, "data": {"list": [{"name": "张三"}], "token": "t1"}}
        )

    def test_json_path(self):
        self.assertEqual(extract_value(self.resp, "$.data.list[0].name"), "张三")

    def test_status_code(self):
        self.assertEqual(extract_value(self.resp, "status_code"), 200)

    def test_regex_on_text(self):
        resp = httpx.Response(200, text="token=abc123;")
        self.assertEqual(extract_value(resp, r"re:token=(\w+)"), "abc123")

    def test_missing_path_chinese_error(self):
        with self.assertRaises(ExtractError) as ctx:
            extract_value(self.resp, "$.data.nothing")
        self.assertIn("找不到字段", str(ctx.exception))

    def test_literal_passthrough(self):
        self.assertEqual(extract_value(self.resp, "普通字符串"), "普通字符串")


if __name__ == "__main__":
    unittest.main()
