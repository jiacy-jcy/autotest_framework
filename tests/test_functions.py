import unittest

from atf import template
from atf.errors import ATFError
from atf.functions import evaluate
from atf.plugins import registry


class TestFunctions(unittest.TestCase):
    def test_uuid_length(self):
        self.assertEqual(len(evaluate("uuid", "")), 36)

    def test_rand_str_length(self):
        self.assertEqual(len(evaluate("rand_str", "10")), 10)
        self.assertEqual(len(evaluate("rand_str", "")), 8)  # 默认长度 8

    def test_int_range(self):
        for _ in range(20):
            self.assertIn(evaluate("int", "1,3"), (1, 2, 3))

    def test_timestamp(self):
        self.assertGreater(evaluate("timestamp", ""), 0)

    def test_render_function_inline_and_whole(self):
        self.assertEqual(len(template.render("${rand_str(5)}", {})), 5)
        self.assertRegex(template.render("id-${uuid()}", {}), r"^id-[0-9a-f-]{36}$")

    def test_unknown_function_chinese_error(self):
        with self.assertRaises(ATFError) as ctx:
            evaluate("no_such_fn", "")
        self.assertIn("未知的变量函数", str(ctx.exception))

    def test_bad_args_chinese_error(self):
        with self.assertRaises(ATFError):
            evaluate("int", "abc")  # 未加引号的字符串 → 解析失败

    def test_plugin_registered_function(self):
        registry.register_function("定值", lambda: "固定值")
        self.assertEqual(template.render("${定值()}", {}), "固定值")


if __name__ == "__main__":
    unittest.main()
