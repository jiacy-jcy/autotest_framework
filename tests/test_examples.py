"""校验 examples/ 下的示例用例都能被正常加载（防止示例随改动失效）"""
import unittest
from pathlib import Path

import yaml

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

    def test_feature_suite_targets_exist_and_load(self):
        suite_path = EXAMPLES_DIR.parent / "feature_suite.yaml"
        suite = yaml.safe_load(suite_path.read_text(encoding="utf-8"))
        self.assertTrue(suite["cases"], "特性巡检套件应引用用例")
        for relative in suite["cases"]:
            with self.subTest(case=relative):
                case = load_case_file(EXAMPLES_DIR.parent / relative)
                self.assertTrue(case["teststeps"])


if __name__ == "__main__":
    unittest.main()
