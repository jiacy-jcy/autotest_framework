"""本地演示接口服务，用于离线体验框架：python examples/mock_server.py"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

USERS = {1: {"id": 1, "name": "张三", "role": "admin"}}
VALID_TOKEN = "token-demo-001"


class Handler(BaseHTTPRequestHandler):
    def _reply(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    def _authorized(self):
        return self.headers.get("Authorization") == f"Bearer {VALID_TOKEN}"

    def do_POST(self):
        if self.path == "/api/login":
            data = self._read_json()
            if data.get("username") == "admin" and data.get("password") == "123456":
                self._reply({"code": 0, "msg": "登录成功",
                             "data": {"token": VALID_TOKEN, "user_id": 1}})
            else:
                self._reply({"code": 1001, "msg": "用户名或密码错误"})
        else:
            self._reply({"code": 404, "msg": "接口不存在"}, 404)

    def do_GET(self):
        if self.path.startswith("/api/users/"):
            if not self._authorized():
                self._reply({"code": 401, "msg": "未授权，请先登录"}, 401)
                return
            user_id = int(self.path.rsplit("/", 1)[1])
            user = USERS.get(user_id)
            if user:
                self._reply({"code": 0, "msg": "查询成功", "data": user})
            else:
                self._reply({"code": 404, "msg": "用户不存在"}, 404)
        else:
            self._reply({"code": 404, "msg": "接口不存在"}, 404)

    def do_PUT(self):
        if self.path.startswith("/api/users/"):
            if not self._authorized():
                self._reply({"code": 401, "msg": "未授权，请先登录"}, 401)
                return
            user_id = int(self.path.rsplit("/", 1)[1])
            if user_id not in USERS:
                self._reply({"code": 404, "msg": "用户不存在"}, 404)
                return
            data = self._read_json()
            USERS[user_id].update({k: v for k, v in data.items() if k in ("name", "role")})
            self._reply({"code": 0, "msg": "修改成功", "data": USERS[user_id]})
        else:
            self._reply({"code": 404, "msg": "接口不存在"}, 404)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8899), Handler)
    print("演示服务已启动：http://127.0.0.1:8899 （按 Ctrl+C 停止）")
    server.serve_forever()
