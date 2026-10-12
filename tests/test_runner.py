import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from atf.runner import Runner


class _Handler(BaseHTTPRequestHandler):
    def _reply(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/api/login":
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length) or b"{}")
            if data.get("username") == "admin" and data.get("password") == "123456":
                self._reply({"code": 0, "msg": "登录成功", "data": {"token": "t-001", "user_id": 7}})
            else:
                self._reply({"code": 1001, "msg": "用户名或密码错误"})
        else:
            self._reply({"code": 404, "msg": "接口不存在"}, 404)

    def do_GET(self):
        if self.path.startswith("/api/users/"):
            if self.headers.get("Authorization") != "Bearer t-001":
                self._reply({"code": 401, "msg": "未授权"}, 401)
                return
            uid = int(self.path.rsplit("/", 1)[1])
            self._reply({"code": 0, "msg": "查询成功", "data": {"id": uid, "name": "张三"}})
        else:
            self._reply({"code": 404, "msg": "接口不存在"}, 404)

    def log_message(self, *args):
        pass


class TestRunner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _case(self, login_validate):
        return {
            "config": {"name": "流程", "base_url": f"http://127.0.0.1:{self.port}"},
            "teststeps": [
                {"name": "登录",
                 "request": {"method": "POST", "url": "/api/login",
                             "json": {"username": "admin", "password": "123456"}},
                 "extract": {"token": "$.data.token", "uid": "$.data.user_id"},
                 "validate": login_validate},
                {"name": "查询",
                 "request": {"method": "GET", "url": "/api/users/${uid}",
                             "headers": {"Authorization": "Bearer ${token}"}},
                 "validate": [{"eq": ["$.data.name", "张三"]}]},
            ],
        }

    def test_full_flow_pass(self):
        suite = Runner().run_case(self._case([{"eq": ["$.code", 0]}]))
        self.assertTrue(suite.passed)
        self.assertEqual(len(suite.steps), 2)

    def test_failure_skips_remaining_steps(self):
        suite = Runner().run_case(self._case([{"eq": ["$.code", 999]}]))
        self.assertFalse(suite.passed)
        self.assertEqual(suite.skipped, 1)
        self.assertIn("断言失败", suite.steps[0].error)

    def test_chinese_comparator_in_flow(self):
        suite = Runner().run_case(self._case([{"等于": ["$.msg", "登录成功"]}]))
        self.assertTrue(suite.steps[0].passed)

    def test_variable_extracted_and_passed_to_next_step(self):
        # 若 token 提取或传递失败，第二步查询会返回 401 导致断言失败
        suite = Runner().run_case(self._case([{"eq": ["status_code", 200]}]))
        self.assertTrue(all(step.passed for step in suite.steps))

    def test_data_driven_runs_once_per_row(self):
        base_url = f"http://127.0.0.1:{self.port}"
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "login.csv").write_text(
                "case_name,username,password,expect_code\n"
                "正确登录,admin,123456,0\n"
                "密码错误,admin,000000,1001\n",
                encoding="utf-8",
            )
            case = {
                "config": {"name": "登录参数化", "base_url": base_url, "datas": "login.csv"},
                "__file__": str(Path(tmp, "case.yaml")),
                "teststeps": [{
                    "name": "登录",
                    "request": {"method": "POST", "url": "/api/login",
                                "json": {"username": "${username}", "password": "${password}"}},
                    "validate": [{"eq": ["$.code", "${expect_code}"]}],
                }],
            }
            suites = Runner().run_case_all(case)
        self.assertEqual(len(suites), 2)
        self.assertTrue(all(suite.passed for suite in suites))
        self.assertIn("正确登录", suites[0].name)
        self.assertIn("密码错误", suites[1].name)

    def test_env_namespace_in_flow(self):
        case = {
            "config": {"name": "环境变量流程", "base_url": "${env.base_url}"},
            "teststeps": [{
                "name": "查询",
                "request": {"method": "GET", "url": "/api/users/7",
                            "headers": {"Authorization": "Bearer ${env.token}"}},
                "validate": [{"eq": ["$.code", 0]}],
            }],
        }
        runner = Runner(env={"base_url": f"http://127.0.0.1:{self.port}", "token": "t-001"})
        self.assertTrue(runner.run_case(case).passed)


if __name__ == "__main__":
    unittest.main()
