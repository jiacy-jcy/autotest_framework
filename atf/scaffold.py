"""atf init 脚手架：生成一套可直接运行的示例项目

模板以字符串内嵌，避免额外打包配置（package_data）导致的安装问题。
"""
from pathlib import Path

_CONFIG_YAML = """\
# 环境变量配置：执行时用 --env 指定，可准备 dev/test/prod 多份
# 用例中通过命名空间引用，例如 ${env.base_url}（不会与系统环境变量冲突）
base_url: http://127.0.0.1:8899
username: admin
password: "123456"
"""

_EXAMPLE_CASE = """\
# 完整流程示例：登录 → 携带令牌查询 → 修改用户名
config:
  name: 用户模块接口流程
  base_url: ${env.base_url}

teststeps:
  - name: 登录获取令牌
    request:
      method: POST
      url: /api/login
      json:
        username: ${env.username}
        password: ${env.password}
    extract:
      token: $.data.token
      user_id: $.data.user_id
    validate:
      - eq: [status_code, 200]
      - eq: [$.code, 0]
      - contains: [$.msg, 成功]

  - name: 携带令牌查询用户详情
    request:
      method: GET
      url: /api/users/${user_id}
      headers:
        Authorization: Bearer ${token}
    validate:
      - eq: [$.data.name, 张三]
      - 等于: [$.data.role, admin]        # 中文比较符演示
      - 正则匹配: [$.msg, ^查询]

  - name: 修改用户姓名
    request:
      method: PUT
      url: /api/users/${user_id}
      headers:
        Authorization: Bearer ${token}
      json:
        name: 张三丰
    validate:
      - eq: [$.code, 0]
      - eq: [$.data.name, 张三丰]
"""

_MOCK_SERVER = '''\
"""本地演示接口服务（atf init 生成），用于离线体验：python mock_server.py"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

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
            user = USERS.get(int(self.path.rsplit("/", 1)[1]))
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
    server = HTTPServer(("127.0.0.1", 8899), Handler)
    print("演示服务已启动：http://127.0.0.1:8899 （按 Ctrl+C 停止）")
    server.serve_forever()
'''

_PROJECT_README = """\
# ATF 接口自动化项目

由 `atf init` 生成。

## 快速开始

```bash
python mock_server.py                      # 终端①：启动本地演示接口（端口 8899）
atf run cases/example.yaml -e config.yaml  # 终端②：执行示例用例
atf run cases -e config.yaml               # 执行整个 cases 目录
```

## 目录说明

- `config.yaml`   环境配置（base_url、账号等），用例中以 `${env.xxx}` 引用
- `cases/`        用例目录，`atf run cases` 可执行目录下全部用例
- `mock_server.py` 本地演示接口，仅用于验证框架，可删除

## 编写自己的用例

1. 修改 `config.yaml` 中的 `base_url` 指向你的接口
2. 参照 `cases/example.yaml` 编写用例
3. 用法细节参见框架 README
"""

TEMPLATES = {
    "config.yaml": _CONFIG_YAML,
    "cases/example.yaml": _EXAMPLE_CASE,
    "mock_server.py": _MOCK_SERVER,
    "README.md": _PROJECT_README,
}


def init_project(target, force: bool = False):
    """在 target 目录生成示例项目。

    返回 (根目录, 已生成文件列表, 因已存在而跳过的文件列表)。
    """
    root = Path(target)
    root.mkdir(parents=True, exist_ok=True)
    created, skipped = [], []
    for relative, content in TEMPLATES.items():
        path = root / relative
        if path.exists() and not force:
            skipped.append(relative)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        created.append(relative)
    return root, created, skipped
