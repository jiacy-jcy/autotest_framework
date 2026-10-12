"""校验 examples/ 下的示例用例都能被正常加载（防止示例随改动失效）"""
import unittest
from pathlib import Path

from atf.parser import load_case_file

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples" / "cases"


class TestExamples(unittest.TestCase):
    def test_all_example_cases_load(self):
        files = sorted(EXAMPLES_DIR.glob("*.yaml")) + sorted(EXAMPLES_DIR.glob("*.yml"))
        self.assertTrue(files, "examples/cases 下应有示例用例")
        for file in files:
            with self.subTest(case=file.name):
                case = load_case_file(file)
                self.assertTrue(case["teststeps"])


if __name__ == "__main__":
    unittest.main()
