import tempfile
import unittest
from pathlib import Path

from atf.errors import CaseFormatError
from atf.parser import find_case_files, load_case_file, load_env_file


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

    def test_find_case_files_in_dir(self):
        self._write("a.yaml", "teststeps: []\n")
        self._write("b.yml", "teststeps: []\n")
        self._write("c.txt", "不是用例\n")
        self.assertEqual(len(find_case_files(self.dir)), 2)


if __name__ == "__main__":
    unittest.main()
