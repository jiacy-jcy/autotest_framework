import sqlite3
import tempfile
import unittest
from pathlib import Path

from atf.db import query
from atf.errors import ATFError
from atf.runner import Runner


class TestDb(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "t.db"
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, status TEXT)")
        conn.executemany("INSERT INTO users VALUES (?, ?, ?)",
                         [(1, "张三", "active"), (2, "李四", "disabled")])
        conn.commit()
        conn.close()
        self.url = f"sqlite:///{self.db_path.as_posix()}"

    def tearDown(self):
        self.tmp.cleanup()

    def test_query_with_named_args(self):
        result = query({"url": self.url,
                        "query": "SELECT name, status FROM users WHERE id = :uid",
                        "args": {"uid": 1}})
        self.assertEqual(result.json(), [{"name": "张三", "status": "active"}])

    def test_runner_db_step(self):
        case = {
            "config": {"name": "数据库断言"},
            "teststeps": [{
                "name": "查询用户",
                "db": {"url": "${env.db}",
                       "query": "SELECT name, status FROM users WHERE id = :uid",
                       "args": {"uid": 2}},
                "extract": {"name": "$[0].name", "status": "$[0].status"},
                "validate": [{"eq": ["${name}", "李四"]}, {"eq": ["${status}", "disabled"]}],
            }],
        }
        suite = Runner(env={"db": self.url}).run_case(case)
        self.assertTrue(suite.passed, suite.steps[0].error)
        self.assertEqual(suite.steps[0].detail.method, "DB")

    def test_missing_query_chinese_error(self):
        with self.assertRaises(ATFError):
            query({"url": self.url})

    def test_missing_url_chinese_error(self):
        with self.assertRaises(ATFError):
            query({"query": "SELECT 1"})

    def test_unsupported_scheme_chinese_error(self):
        with self.assertRaises(ATFError) as ctx:
            query({"url": "oracle://x", "query": "SELECT 1"})
        self.assertIn("不支持", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
