import unittest

from atf.assertion import compare
from atf.errors import ATFError


class TestAssertion(unittest.TestCase):
    def test_eq(self):
        self.assertTrue(compare("eq", 0, 0)[0])
        self.assertFalse(compare("eq", 0, 1)[0])

    def test_gt_with_number_coercion(self):
        self.assertTrue(compare("gt", "3.5", 2)[0])

    def test_contains(self):
        self.assertTrue(compare("contains", "登录成功", "成功")[0])

    def test_regex(self):
        self.assertTrue(compare("regex", "订单号A1001", r"^订单号")[0])

    def test_eq_string_fallback(self):
        # 数据驱动常见：CSV 里的 "1001" 与响应中的数字 1001 应视为相等
        self.assertTrue(compare("eq", 1001, "1001")[0])
        self.assertTrue(compare("eq", "0", 0)[0])
        self.assertFalse(compare("eq", "abc", 0)[0])

    def test_is_type(self):
        self.assertTrue(compare("is_type", 1, "int")[0])
        self.assertTrue(compare("is_type", "x", "str")[0])
        self.assertTrue(compare("is_type", {}, "dict")[0])
        self.assertTrue(compare("is_type", True, "bool")[0])
        self.assertFalse(compare("is_type", True, "int")[0])   # bool 不误判为 int
        self.assertFalse(compare("is_type", 1, "unknown")[0])
        self.assertTrue(compare("类型为", "x", "str")[0])

    def test_contains_any(self):
        self.assertTrue(compare("contains_any", [1, 2], [2, 3])[0])
        self.assertTrue(compare("contains_any", "admin", ["admin", "dev"])[0])
        self.assertTrue(compare("contains_any", ["admin"], "admin")[0])
        self.assertFalse(compare("contains_any", ["a"], ["b"])[0])
        self.assertTrue(compare("包含其一", "dev", ["admin", "dev"])[0])

    def test_chinese_alias(self):
        self.assertTrue(compare("等于", "admin", "admin")[0])
        self.assertTrue(compare("包含", "查询成功", "成功")[0])

    def test_failure_message_is_chinese(self):
        passed, reason = compare("eq", 1001, 0)
        self.assertFalse(passed)
        self.assertIn("期望等于", reason)
        self.assertIn("1001", reason)

    def test_unsupported_comparator(self):
        with self.assertRaises(ATFError) as ctx:
            compare("差不多", 1, 1)
        self.assertIn("不支持的比较符", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
