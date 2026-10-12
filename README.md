# ATF 智测

[![测试](https://github.com/jiacy-jcy/autotest_framework/actions/workflows/test.yml/badge.svg)](https://github.com/jiacy-jcy/autotest_framework/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**AI 加持、中文友好的接口自动化测试框架**（Python）

零代码基础也能写接口用例：YAML 描述、全中文报错、支持中文比较符；
内置规则引擎可从 OpenAPI/Swagger 文档一键生成用例，接入大模型后还能自动补充边界场景。

## 特性

- **低代码**：YAML 写用例，不懂 Python 也能上手
- **中文友好**：中文报错、中文比较符（`等于`、`包含`、`正则匹配`）、中文文档
- **AI 加持**：`atf gen` 从 OpenAPI/Swagger 生成用例；`--ai-analyze` 自动分析失败原因
- **流程编排**：变量提取与传递（`extract`），轻松实现「登录 → 携带令牌访问」
- **数据驱动**：`${变量}` 占位符贯穿请求、断言；支持 `--env` 环境配置与 CSV/Excel 参数化
- **数据库与钩子**：`db` 步骤直接校验数据库（SQLite 内置，MySQL/PostgreSQL 可选）；生命周期钩子可注入自定义逻辑
- **测试报告**：`--html` 零依赖单文件 HTML 报告，`--allure` 导出 Allure 结果
- **pytest 集成**：`pip install atf[pytest]` 后，YAML 用例可直接在 pytest 中运行
- **开箱即用**：`atf init` 一键生成项目，自带离线演示服务，5 分钟跑通

## 快速开始

```bash
pip install -e .                     # 安装（发布后改为 pip install atf）
atf init myproject                   # 初始化示例项目（生成配置、用例、演示服务）
cd myproject
python mock_server.py                # 终端①：启动本地演示接口（端口 8899）
atf run cases/example.yaml -e config.yaml   # 终端②：执行用例
```

> 已有项目可直接用仓库自带的 `examples/` 体验：`python examples/mock_server.py`
> 配合 `atf run examples/cases/user_flow.yaml -e examples/config.yaml`。

输出：

```
【用例集】用户模块接口流程（examples\cases\user_flow.yaml）
  √ 登录获取令牌 …… 通过（0.02秒）
  √ 携带令牌查询用户详情 …… 通过（0.02秒）
  √ 修改用户姓名 …… 通过（0.01秒）

====================================================
  执行完毕：共 3 步 | 通过 3 | 失败 0 | 跳过 0 | 耗时 0.05秒
====================================================
```

## 用例语法

```yaml
config:
  name: 用户模块接口流程
  base_url: ${env.base_url}      # 来自 --env 配置（见下方变量来源说明）

teststeps:
  - name: 登录获取令牌
    request:
      method: POST
      url: /api/login
      json: {username: ${env.username}, password: ${env.password}}
    extract:                      # 从响应提取变量，供后续步骤使用
      token: $.data.token         # JSON 路径；也支持 status_code、headers.x、re:正则
    validate:
      - eq: [status_code, 200]
      - contains: [$.msg, 成功]
      - 等于: [$.code, 0]          # 中文比较符
```

可用比较符：`eq ne gt ge lt le contains not_contains regex len_eq in startswith endswith`，
以及中文别名：`等于 不等于 大于 大于等于 小于 小于等于 包含 不包含 正则匹配 长度等于 属于`。

断言支持第三参数自定义提示：`- eq: [$.code, 0, 登录应成功]`。

### 变量来源与命名空间

用例中的 `${变量}` 按来源分区，彻底避免与系统环境变量重名：

| 写法 | 来源 | 用途 |
|------|------|------|
| `${name}` | 用例 `config.variables` + `extract` 提取结果 | 运行时变量 |
| `${env.name}` | `--env` 配置文件 | dev/test/prod 环境配置 |
| `${sys.NAME}` | 系统环境变量 | 显式引用，常用于 CI 注入密钥 |

> **关键**：无前缀的 `${name}` **不会**回退到系统环境变量。
> 想读系统变量必须显式写 `${sys.NAME}`。
> 这样就不会再出现 `${username}` 意外命中 Windows 系统 `USERNAME` 而静默取到错误值的问题。

配置示例：

```yaml
# examples/config.yaml —— 执行时通过 --env 指定
base_url: http://127.0.0.1:8899
username: admin
password: "123456"
```

用例中通过 `${env.base_url}`、`${env.username}`、`${env.password}` 引用。

> 提示：`env` 与 `sys` 是保留的命名空间前缀。若个别变量名本身含点号
> （如 `foo.bar`），只要 `foo` 不是 `env`/`sys` 就会按普通变量名整段查找。

## 数据驱动

在 `config.datas` 指定 CSV 或 Excel 文件，用例会按每一行数据分别执行：

```yaml
config:
  name: 登录参数化
  base_url: ${env.base_url}
  datas: login_data.csv          # 相对用例文件所在目录；也支持 .xlsx

teststeps:
  - name: 登录
    request:
      method: POST
      url: /api/login
      json: {username: ${username}, password: ${password}}
    validate:
      - eq: [$.code, "${expect_code}"]   # 流式序列中的 ${...} 需加引号
```

```csv
case_name,username,password,expect_code
正确登录,admin,123456,0
密码错误,admin,wrong-password,1001
```

- 列名即变量名，可直接在用例中以 `${列名}` 引用
- 可选列 `case_name`（或 `用例名`）用于区分每次执行的名称
- 数据值统一按字符串处理；断言 `eq` / `ne` 会做字符串回退（`1001` 与 `"1001"` 视为相等）
- Excel（`.xlsx`）需安装：`pip install atf[excel]`
- 在 pytest 中，每一行数据会被参数化为一个独立的用例

> 小贴士：在 YAML 的**流式序列**（`[a, b]`）中引用 `${变量}` 时，`{` 会被误认为映射起点，
> 需写成 `[$.code, "${expect_code}"]`。改用块状写法（`- eq:` 换行后 `- $.code` / `- ${expect_code}`）则无需引号。

## 数据库断言

步骤可用 `db` 代替 `request`，直接对数据库做校验或准备数据：

```yaml
teststeps:
  - name: 校验用户状态
    db:
      url: sqlite:///demo.db          # 连接串见下方说明
      query: "SELECT status FROM users WHERE id = :uid"
      args:
        uid: 1
    extract:
      status: $[0].status
    validate:
      - eq: ["${status}", active]
```

- 查询结果按行转换为字典列表，用 JSON 路径取值（`$[0].status`）
- 命名参数用 `args`（如 `:uid`）；位置参数用 `params`（按数据库的占位符书写：SQLite 用 `?`，MySQL/PostgreSQL 用 `%s`）
- 连接串：`sqlite:///demo.db`、`sqlite:///C:/abs/demo.db`、`mysql://user:pass@host:3306/db`、`postgresql://user:pass@host:5432/db`
- SQLite 内置零依赖；MySQL 需 `pip install atf[mysql]`，PostgreSQL 需 `pip install atf[postgresql]`

## 钩子函数

在 `config.hooks` 中引用 Python 函数（`模块.函数`），在生命周期插入自定义逻辑：

```yaml
config:
  name: 带钩子的用例
  hooks:
    before_case: hooks.before_case
    before_step: hooks.before_step
    after_step:  hooks.after_step
```

支持 `before_case` / `after_case` / `before_step` / `after_step`，钩子函数接收一个 `context` 参数：

```python
def before_case(context):
    context.set("run_id", "RUN-001")   # 注入变量，供用例以 ${run_id} 引用

def before_step(context):
    context.step["request"]["headers"]["X-Run-Id"] = context.get("run_id")

def after_step(context):
    if context.result and not context.result.passed:
        print(f"步骤失败：{context.step['name']}")
```

- 框架会自动把「当前工作目录」与「用例文件所在目录」加入模块搜索路径
- 钩子出错会转为中文错误：`before_step` 出错会导致该步骤失败；`after_step` 出错会把本已通过的步骤判为失败

## AI 生成用例

```bash
atf gen openapi.json -o cases          # 规则引擎离线生成基础用例
atf gen openapi.json -o cases --llm    # 追加 AI 生成的边界/异常用例
```

AI 增强通过环境变量配置（兼容 OpenAI 及各类国产模型的兼容接口）：

```bash
set ATF_AI_BASE_URL=https://api.deepseek.com/v1
set ATF_AI_API_KEY=你的密钥
set ATF_AI_MODEL=deepseek-chat
```

未配置密钥时自动回退为规则引擎，不影响使用。

## AI 失败分析

`atf run --ai-analyze` 会在有失败时给出原因分类与修复建议，帮助快速判断"是接口变了还是用例错了"：

```bash
atf run cases -e config.yaml --ai-analyze
atf run cases -e config.yaml --ai-analyze --html report.html   # 分析结果同时写入 HTML 报告
```

- **无密钥**：内置规则引擎离线分类（环境问题 / 认证问题 / 接口变更 / 服务端异常 / 用例问题）
- **配置 `ATF_AI_API_KEY`**：交给大模型给出更准确的原因与建议
- 分类结果同时出现在控制台与 HTML 报告中

示例输出：

```
[1] 接口变更示例 / 登录后提取不存在的字段（POST http://127.0.0.1:8899/api/login）
    分类：接口变更
    原因：响应中缺少断言的字段
    建议：响应结构可能变化，核对该字段是否改名或被移除
```

## 测试报告

`atf run` 支持两种报告输出：

```bash
atf run cases -e config.yaml --html                  # 生成 reports/atf-report.html
atf run cases -e config.yaml --html out/report.html  # 自定义路径
atf run cases -e config.yaml --allure                # 导出 allure-results/
```

- **HTML 报告（默认）**：零依赖、单文件、全中文，双击即可查看；含汇总统计，逐步展示方法、接口、状态码与耗时，失败步骤自动展开请求体、响应体与失败原因
- **Allure**：导出标准结果，供已有 Allure 的团队使用：`allure generate allure-results -o allure-report`

## 在 pytest 中使用

安装 `pytest` 增强后，ATF 会通过 entry point 自动注册为 pytest 插件，
带有 `teststeps` 的 YAML 会被收集为 pytest 用例，从而复用 pytest 的 `-k` 选择、报告与 CI 生态：

```bash
pip install atf[pytest]
pytest cases -v --atf-env config.yaml   # 像跑普通测试一样运行 ATF 用例
pytest cases -k 登录                      # 用 -k 选择用例
```

- `--atf-env`：指定环境变量配置（等同于 `atf run -e`）
- `--atf-timeout`：请求超时秒数
- 非 ATF 结构的 YAML 不会被收集，可与其他工具共存

## 命令一览

| 命令 | 说明 |
|------|------|
| `atf init [目录] [--force]` | 初始化示例项目（配置 + 用例 + 演示服务） |
| `atf run <用例文件或目录> [-e 环境配置.yaml] [--html 路径] [--allure 目录] [--ai-analyze] [-t 超时秒]` | 执行用例，可生成报告并分析失败，全部通过退出码为 0 |
| `atf gen <openapi.json> [-o 输出目录] [--llm]` | 生成用例 |
| `atf --version` | 查看版本 |

## 路线图

- [x] v0.1 核心引擎：YAML 用例 / 变量提取 / 中英文断言 / 控制台报告 / AI 生成
- [x] v0.2 项目脚手架、测试报告 HTML + Allure、pytest 插件
- [x] v0.3 数据驱动（CSV/Excel）、数据库断言、钩子函数
- [x] v0.4 AI 失败用例智能分析（自动定位是接口变更还是用例问题）

## 参与贡献

欢迎 Issue 和 PR。开发规范见 [AGENTS.md](AGENTS.md)。

## License

MIT
