import base64
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from atf.converters import detect_source, generate_from_curl, generate_from_har
from atf.errors import ATFError

HAR = {
    "log": {
        "version": "1.2",
        "entries": [
            {"_resourceType": "script",
             "request": {"method": "GET", "url": "https://demo.local/static/app.js", "headers": []}},
            {"_resourceType": "preflight",
             "request": {"method": "OPTIONS", "url": "https://demo.local/api/login", "headers": []}},
            {"_resourceType": "xhr",
             "request": {"method": "POST", "url": "https://demo.local/api/login",
                         "headers": [{"name": "Content-Type", "value": "application/json"},
                                     {"name": "Content-Length", "value": "52"},
                                     {"name": "User-Agent", "value": "Mozilla/5.0"}],
                         "postData": {"mimeType": "application/json",
                                      "text": '{"username": "admin", "password": "123456"}'}}},
            {"_resourceType": "xhr",
             "request": {"method": "GET", "url": "https://demo.local/api/users/1",
                         "headers": [{"name": "Authorization", "value": "Bearer token-demo-001"},
                                     {"name": "Accept", "value": "application/json"}]}},
            {"_resourceType": "xhr",
             "request": {"method": "GET", "url": "https://demo.local/api/users/1",
                         "headers": [{"name": "Authorization", "value": "Bearer token-demo-001"},
                                     {"name": "Accept", "value": "application/json"}]}},
        ]
    }
}


class TestConverters(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _har_file(self):
        path = self.dir / "demo.har"
        path.write_text(json.dumps(HAR), encoding="utf-8")
        return path

    def _load(self, target):
        return yaml.safe_load(target.read_text(encoding="utf-8"))

    def test_detect_source(self):
        self.assertEqual(detect_source(self._har_file()), "har")
        spec = self.dir / "openapi.json"
        spec.write_text('{"openapi": "3.0.0", "paths": {}}', encoding="utf-8")
        self.assertEqual(detect_source(spec), "openapi")
        other = self.dir / "other.json"
        other.write_text('{"foo": 1}', encoding="utf-8")
        with self.assertRaises(ATFError):
            detect_source(other)

    def test_har_filters_static_and_dedup(self):
        case = self._load(generate_from_har(self._har_file(), self.dir / "out"))
        self.assertEqual(case["config"]["base_url"], "https://demo.local")
        steps = case["teststeps"]
        self.assertEqual(len(steps), 2)  # 过滤静态与预检，重复请求去重
        self.assertEqual(steps[0]["request"]["method"], "POST")
        self.assertEqual(steps[0]["request"]["url"], "/api/login")
        self.assertEqual(steps[0]["request"]["json"],
                         {"username": "admin", "password": "123456"})
        self.assertNotIn("Content-Length", steps[0]["request"]["headers"])  # 剔除无意义头
        self.assertEqual(steps[1]["request"]["url"], "/api/users/1")
        self.assertEqual(steps[1]["request"]["headers"]["Authorization"], "Bearer token-demo-001")

    def test_har_without_entries_chinese_error(self):
        path = self.dir / "empty.har"
        path.write_text('{"log": {"entries": []}}', encoding="utf-8")
        with self.assertRaises(ATFError):
            generate_from_har(path, self.dir / "out")

    def test_curl_json_body(self):
        command = ("curl 'https://demo.local/api/login' -X POST "
                   "-H 'Content-Type: application/json' "
                   "--data-raw '{\"username\": \"admin\", \"password\": \"123456\"}' "
                   "--compressed -s")
        case = self._load(generate_from_curl(command, self.dir / "out"))
        step = case["teststeps"][0]
        self.assertEqual(case["config"]["base_url"], "https://demo.local")
        self.assertEqual(step["request"]["method"], "POST")
        self.assertEqual(step["request"]["url"], "/api/login")
        self.assertEqual(step["request"]["json"], {"username": "admin", "password": "123456"})
        self.assertEqual(step["request"]["headers"]["Content-Type"], "application/json")

    def test_curl_form_defaults_to_post(self):
        case = self._load(generate_from_curl(
            "curl 'https://demo.local/api/form' -d 'username=admin&password=123'", self.dir / "out"))
        step = case["teststeps"][0]
        self.assertEqual(step["request"]["method"], "POST")  # 带 -d 时默认 POST
        self.assertEqual(step["request"]["data"], {"username": "admin", "password": "123"})

    def test_curl_basic_auth_user_agent_and_file_input(self):
        cmd_file = self.dir / "cmd.txt"
        cmd_file.write_text("curl https://demo.local/api/x -u 'admin:secret' -A 'UA/1.0'",
                            encoding="utf-8")
        case = self._load(generate_from_curl(str(cmd_file), self.dir / "out"))
        step = case["teststeps"][0]
        self.assertEqual(step["request"]["method"], "GET")
        expected = base64.b64encode(b"admin:secret").decode("ascii")
        self.assertEqual(step["request"]["headers"]["Authorization"], f"Basic {expected}")
        self.assertEqual(step["request"]["headers"]["User-Agent"], "UA/1.0")

    def test_curl_missing_url_chinese_error(self):
        with self.assertRaises(ATFError):
            generate_from_curl("curl -X POST -d 'a=1'", self.dir / "out")

    def test_curl_empty_chinese_error(self):
        with self.assertRaises(ATFError):
            generate_from_curl("   ", self.dir / "out")


if __name__ == "__main__":
    unittest.main()
