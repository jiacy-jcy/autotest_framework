import tempfile
import unittest
from pathlib import Path

from atf.errors import CaseFormatError
from atf.parser import (case_tags, find_case_files, load_case_file, load_env_file,
                        resolve_case_files)


class TestParser(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, name, content):
        path = self.dir / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_load_valid_case(self):
        path = self._write("case.yaml", "config:\n  name: 测试\nteststeps:\n  - request:\n      url: /a\n")
        case = load_case_file(path)
        self.assertEqual(case["config"]["name"], "测试")
        self.assertEqual(case["teststeps"][0]["name"], "步骤1")

    def test_missing_teststeps_chinese_error(self):
        path = self._write("bad.yaml", "config:\n  name: 坏用例\n")
        with self.assertRaises(CaseFormatError) as ctx:
            load_case_file(path)
        self.assertIn("teststeps", str(ctx.exception))

    def test_load_env_file(self):
        path = self._write("env.yaml", "BASE_URL: http://x\npassword: '123'\n")
        self.assertEqual(load_env_file(path)["password"], "123")

    def test_env_profiles_selected_by_name(self):
        path = self._write("envs.yaml",
                           "timeout: 30\n"
                           "environments:\n"
                           "  test: {base_url: http://test, timeout: 5}\n"
                           "  prod: {base_url: http://prod}\n")
        env = load_env_file(path, name="prod")
        self.assertEqual(env, {"timeout": 30, "base_url": "http://prod"})  # 公共变量被分区覆盖
        env = load_env_file(path, name="test")
        self.assertEqual(env["timeout"], 5)

    def test_env_profiles_default(self):
        path = self._write("envs.yaml",
                           "default: test\n"
                           "environments:\n"
                           "  test: {base_url: http://test}\n"
                           "  prod: {base_url: http://prod}\n")
        self.assertEqual(load_env_file(path)["base_url"], "http://test")

    def test_env_profiles_missing_name_chinese_error(self):
        path = self._write("envs.yaml", "environments:\n  test: {base_url: http://test}\n")
        with self.assertRaises(CaseFormatError) as ctx:
            load_env_file(path)
        self.assertIn("--env-name", str(ctx.exception))
        self.assertIn("test", str(ctx.exception))  # 报错要列出可选环境

    def test_env_profiles_unknown_name_chinese_error(self):
        path = self._write("envs.yaml", "environments:\n  test: {base_url: http://test}\n")
        with self.assertRaises(CaseFormatError) as ctx:
            load_env_file(path, name="prod")
        self.assertIn("不存在", str(ctx.exception))

    def test_find_case_files_in_dir(self):
        self._write("a.yaml", "teststeps: []\n")
        self._write("b.yml", "teststeps: []\n")
        self._write("c.txt", "不是用例\n")
        self.assertEqual(len(find_case_files(self.dir)), 2)

    def test_resolve_suite_expands_cases(self):
        self._write("a.yaml", "teststeps:\n  - request:\n      url: /a\n")
        self._write("b.yaml", "teststeps:\n  - request:\n      url: /b\n")
        suite = self._write("suite.yaml", "name: 套件\ncases:\n  - a.yaml\n  - b.yaml\n")
        files = resolve_case_files(suite)
        self.assertEqual([f.name for f in files], ["a.yaml", "b.yaml"])

    def test_resolve_suite_missing_case_error(self):
        suite = self._write("suite.yaml", "cases:\n  - nope.yaml\n")
        with self.assertRaises(CaseFormatError):
            resolve_case_files(suite)

    def test_case_tags(self):
        self.assertEqual(case_tags({"config": {"tags": ["smoke", "user"]}}), ["smoke", "user"])
        self.assertEqual(case_tags({"tags": "a, b"}), ["a", "b"])
        self.assertEqual(case_tags({}), [])


if __name__ == "__main__":
    unittest.main()
