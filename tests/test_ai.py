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


if __name__ == "__main__":
    unittest.main()
