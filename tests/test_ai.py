import json
import os
import tempfile
import unittest
from pathlib import Path

import yaml

from atf.ai import generate_from_openapi

SPEC = {
    "openapi": "3.0.0",
    "paths": {
        "/api/login": {
            "post": {
                "summary": "用户登录",
                "requestBody": {"content": {"application/json": {"schema": {
                    "type": "object",
                    "properties": {"username": {"type": "string", "example": "admin"}},
                }}}},
                "responses": {"200": {"description": "成功"}},
            }
        },
        "/api/users": {
            "get": {
                "summary": "用户列表",
                "parameters": [{"name": "page", "in": "query", "schema": {"type": "integer"}}],
                "responses": {"200": {"description": "成功"}},
            }
        },
    },
}

SECURE_SPEC = {
    "openapi": "3.0.0",
    "components": {
        "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}}
    },
    "security": [{"bearerAuth": []}],
    "paths": {
        "/api/login": {
            "post": {
                "summary": "用户登录",
                "security": [],
                "requestBody": {"content": {"application/json": {"schema": {
                    "type": "object",
                    "properties": {
                        "username": {"type": "string", "example": "admin"},
                        "password": {"type": "string", "example": "123456"},
                    }}}}},
            }
        },
        "/api/users": {
            "get": {
                "summary": "用户列表",
                "parameters": [
                    {"name": "role", "in": "query",
                     "schema": {"type": "string", "enum": ["admin", "dev", "guest", "owner"]}},
                    {"name": "page", "in": "query",
                     "schema": {"type": "integer", "default": 1}},
                ],
            }
        },
    },
}


class TestAiGenerate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.spec_path = self.dir / "openapi.json"
        self.spec_path.write_text(json.dumps(SPEC), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_rule_based_generation(self):
        target = generate_from_openapi(self.spec_path, self.dir / "out")
        case = yaml.safe_load(target.read_text(encoding="utf-8"))
        self.assertEqual(len(case["teststeps"]), 2)
        login = case["teststeps"][0]
        self.assertEqual(login["name"], "用户登录")
        self.assertEqual(login["request"]["json"], {"username": "admin"})
        users = case["teststeps"][1]
        self.assertEqual(users["request"]["params"], {"page": 1})

    def test_llm_fallback_without_api_key(self):
        os.environ.pop("ATF_AI_API_KEY", None)
        target = generate_from_openapi(self.spec_path, self.dir / "out2", use_llm=True)
        case = yaml.safe_load(target.read_text(encoding="utf-8"))
        self.assertEqual(len(case["teststeps"]), 2)  # 无 key 时回退为基础用例，不崩溃


class TestAiEnhance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_spec(self, spec):
        path = self.dir / "openapi.json"
        path.write_text(json.dumps(spec), encoding="utf-8")
        return path

    def test_security_login_chain_and_enum_variants(self):
        target = generate_from_openapi(self._write_spec(SECURE_SPEC), self.dir / "out")
        text = target.read_text(encoding="utf-8")
        case = yaml.safe_load(text)
        steps = case["teststeps"]

        login = steps[0]
        self.assertEqual(login["name"], "登录获取令牌")
        self.assertEqual(login["extract"]["token"], "$.data.token")
        self.assertNotIn("headers", login["request"])  # 登录步骤本身不带认证头

        others = steps[1:]
        self.assertEqual(len(others), 3)  # 枚举 4 个值 → 上限 3 个变体
        roles = [step["request"]["params"]["role"] for step in others]
        self.assertEqual(roles, ["admin", "dev", "guest"])
        for step in others:
            self.assertEqual(step["request"]["headers"]["Authorization"], "Bearer ${token}")
            self.assertEqual(step["request"]["params"]["page"], 1)
        self.assertIn("# 检测到安全方案", text)  # 文件头给出需人工核对的中文提示

    def test_without_security_no_login_chain(self):
        spec = json.loads(json.dumps(SECURE_SPEC))
        spec.pop("components")
        spec.pop("security")
        target = generate_from_openapi(self._write_spec(spec), self.dir / "out")
        case = yaml.safe_load(target.read_text(encoding="utf-8"))
        names = [step["name"] for step in case["teststeps"]]
        self.assertNotIn("登录获取令牌", names)
        for step in case["teststeps"]:
            self.assertNotIn("headers", step["request"])


if __name__ == "__main__":
    unittest.main()
