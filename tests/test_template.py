import os
import unittest

from atf import template
from atf.errors import VariableNotFoundError
from atf.template import Variables


class TestTemplate(unittest.TestCase):
    def test_embedded_placeholder(self):
        self.assertEqual(template.render("Bearer ${t}", {"t": "abc"}), "Bearer abc")

    def test_whole_placeholder_keeps_type(self):
        self.assertEqual(template.render("${n}", {"n": 200}), 200)

    def test_nested_structure(self):
        data = {"a": ["${x}"], "b": {"c": "${x}"}}
        self.assertEqual(template.render(data, {"x": 1}), {"a": [1], "b": {"c": 1}})

    def test_env_namespace(self):
        variables = Variables(flat={}, env={"username": "admin", "port": 8899})
        self.assertEqual(template.render("${env.username}", variables), "admin")
        self.assertEqual(template.render("${env.port}", variables), 8899)
        self.assertEqual(template.render("用户：${env.username}", variables), "用户：admin")

    def test_sys_namespace(self):
        os.environ["ATF_SYS_VAR"] = "hello"
        self.assertEqual(template.render("${sys.ATF_SYS_VAR}", Variables(flat={}, env={})), "hello")

    def test_no_silent_fallback_to_system_env(self):
        # 关键：无前缀变量不再回退系统环境变量，${ATF_LEAK} 不会取到系统值
        os.environ["ATF_LEAK"] = "系统值"
        variables = Variables(flat={}, env={"ATF_LEAK": "配置值"})
        with self.assertRaises(VariableNotFoundError):
            template.render("${ATF_LEAK}", variables)
        self.assertEqual(template.render("${env.ATF_LEAK}", variables), "配置值")
        self.assertEqual(template.render("${sys.ATF_LEAK}", variables), "系统值")

    def test_extracted_variables_are_flat(self):
        variables = Variables(flat={"token": "t1"}, env={})
        variables.set("uid", 7)
        self.assertEqual(template.render("${token}", variables), "t1")
        self.assertEqual(template.render("${uid}", variables), 7)

    def test_missing_namespace_key_chinese_error(self):
        with self.assertRaises(VariableNotFoundError) as ctx:
            template.render("${env.missing}", Variables(flat={}, env={}))
        self.assertIn("命名空间", str(ctx.exception))

    def test_missing_variable_chinese_error(self):
        with self.assertRaises(VariableNotFoundError) as ctx:
            template.render("${no_such_var}", {})
        self.assertIn("未定义", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
