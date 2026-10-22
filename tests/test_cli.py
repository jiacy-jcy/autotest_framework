"""CLI 集成测试：直接调用 atf.cli.main 验证参数与退出码（用例走 db 步骤，不依赖网络）"""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from atf.cli import main

_DB_CASE = """\
config:
  name: 数据库用例
teststeps:
  - name: 查询
    db:
      url: "sqlite:///:memory:"
      query: "SELECT 0 AS code"
    validate:
      - eq: ["$[0].code", 0]
"""

_DB_CASE_ENV = """\
config:
  name: 环境用例
teststeps:
  - name: 查询
    db:
      url: "sqlite:///:memory:"
      query: "SELECT 42 AS v"
    validate:
      - eq: ["$[0].v", "${env.expect}"]
"""

_ENVS = """\
default: test
environments:
  test: {expect: 42}
  prod: {expect: 41}
"""

_CURL_CMD = "curl 'https://demo.local/api/login' -X POST --data-raw '{\"username\": \"admin\"}'"


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.case_ok = self._write("case_ok.yaml", _DB_CASE)
        self.case_fail = self._write("case_fail.yaml", _DB_CASE.replace(", 0]", ", 999]"))

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, name, content):
        path = self.dir / name
        path.write_text(content, encoding="utf-8")
        return path

    def _run(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue() + err.getvalue()


class TestCliRun(CliTestCase):
    def test_pass_exits_zero(self):
        code, out = self._run("run", str(self.case_ok))
        self.assertEqual(code, 0)
        self.assertIn("执行完毕", out)

    def test_fail_exits_one(self):
        code, out = self._run("run", str(self.case_fail))
        self.assertEqual(code, 1)
        self.assertIn("断言失败", out)

    def test_missing_case_exits_two(self):
        code, out = self._run("run", str(self.dir / "nope.yaml"))
        self.assertEqual(code, 2)
        self.assertIn("不存在", out)

    def test_tags_no_match_exits_zero_with_hint(self):
        code, out = self._run("run", str(self.case_ok), "--tags", "不存在的标签")
        self.assertEqual(code, 0)
        self.assertIn("没有匹配的用例", out)

    def test_env_name_requires_env_file(self):
        code, out = self._run("run", str(self.case_ok), "--env-name", "test")
        self.assertEqual(code, 2)
        self.assertIn("--env-name", out)

    def test_env_name_selects_profile(self):
        envs = self._write("envs.yaml", _ENVS)
        case_env = self._write("case_env.yaml", _DB_CASE_ENV)
        code, _ = self._run("run", str(case_env), "-e", str(envs))
        self.assertEqual(code, 0)  # default: test
        code, _ = self._run("run", str(case_env), "-e", str(envs), "--env-name", "prod")
        self.assertEqual(code, 1)  # prod 期望 41 ≠ 42

    def test_tags_filters_cases(self):
        tagged = self._write("tagged.yaml", _DB_CASE.replace(
            "name: 数据库用例", "name: 数据库用例\n  tags: [smoke]"))
        code, out = self._run("run", str(self.dir), "--tags", "smoke")
        self.assertEqual(code, 0)
        self.assertEqual(out.count("数据库用例"), 1)  # 只跑了带标签的用例

    def test_trend_writes_history_and_report(self):
        report_dir = self.dir / "rep"
        code, _ = self._run("run", str(self.case_ok), "--trend", "--html", str(report_dir))
        self.assertEqual(code, 0)
        self.assertTrue((report_dir / "atf-report.html").exists())
        self.assertTrue((report_dir / "history.jsonl").exists())


class TestCliGen(CliTestCase):
    def test_gen_openapi_writes_cases(self):
        repo = Path(__file__).resolve().parent.parent
        out = self.dir / "gen_out"
        code, _ = self._run("gen", str(repo / "examples" / "openapi.json"), "-o", str(out))
        self.assertEqual(code, 0)
        self.assertTrue((out / "generated_cases.yaml").exists())

    def test_gen_curl(self):
        cmd_file = self._write("cmd.txt", _CURL_CMD)
        out = self.dir / "curl_out"
        code, _ = self._run("gen", "--curl", str(cmd_file), "-o", str(out))
        self.assertEqual(code, 0)
        self.assertTrue((out / "curl_cases.yaml").exists())

    def test_gen_curl_and_spec_conflict(self):
        cmd_file = self._write("cmd.txt", _CURL_CMD)
        code, out = self._run("gen", str(self.case_ok), "--curl", str(cmd_file))
        self.assertEqual(code, 2)
        self.assertIn("不能同时使用", out)


class TestCliInit(CliTestCase):
    def test_init_creates_project(self):
        target = self.dir / "proj"
        code, out = self._run("init", str(target))
        self.assertEqual(code, 0)
        for name in ("config.yaml", "cases/example.yaml", "mock_server.py", "README.md"):
            self.assertTrue((target / name).exists(), name)
        self.assertIn("已初始化", out)

    def test_init_does_not_overwrite(self):
        target = self.dir / "proj"
        self._run("init", str(target))
        config = target / "config.yaml"
        config.write_text("自定义内容", encoding="utf-8")
        code, out = self._run("init", str(target))
        self.assertEqual(code, 0)
        self.assertIn("未覆盖", out)
        self.assertEqual(config.read_text(encoding="utf-8"), "自定义内容")


if __name__ == "__main__":
    unittest.main()
