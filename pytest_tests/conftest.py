import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

# 启用 pytester 插件（用于在隔离目录中真实运行 pytest）
pytest_plugins = ["pytester"]


class _Handler(BaseHTTPRequestHandler):
    def _reply(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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


@pytest.fixture(scope="session")
def mock_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()
