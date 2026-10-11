import tempfile
import unittest
from pathlib import Path

from atf.parser import load_case_file
from atf.scaffold import TEMPLATES, init_project

EXPECTED = ("config.yaml", "cases/example.yaml", "mock_server.py", "README.md")


class TestScaffold(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "proj"

    def tearDown(self):
        self.tmp.cleanup()

    def test_init_creates_all_files(self):
        root, created, skipped = init_project(self.dir)
        self.assertEqual(skipped, [])
        self.assertEqual(sorted(created), sorted(EXPECTED))
        for name in EXPECTED:
            self.assertTrue((root / name).exists(), name)

    def test_init_does_not_overwrite_by_default(self):
        init_project(self.dir)
        target = self.dir / "config.yaml"
        target.write_text("自定义内容", encoding="utf-8")
        _, created, skipped = init_project(self.dir)
        self.assertIn("config.yaml", skipped)
        self.assertEqual(created, [])
        self.assertEqual(target.read_text(encoding="utf-8"), "自定义内容")

    def test_init_force_overwrites(self):
        init_project(self.dir)
        target = self.dir / "config.yaml"
        target.write_text("自定义内容", encoding="utf-8")
        _, created, _ = init_project(self.dir, force=True)
        self.assertIn("config.yaml", created)
        self.assertEqual(target.read_text(encoding="utf-8"), TEMPLATES["config.yaml"])

    def test_generated_case_is_loadable(self):
        root, _, _ = init_project(self.dir)
        case = load_case_file(root / "cases" / "example.yaml")
        self.assertEqual(len(case["teststeps"]), 3)
        self.assertEqual(case["teststeps"][0]["name"], "登录获取令牌")


if __name__ == "__main__":
    unittest.main()
