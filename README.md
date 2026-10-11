# ATF 智测

[![测试](https://github.com/jiacy-jcy/autotest_framework/actions/workflows/test.yml/badge.svg)](https://github.com/jiacy-jcy/autotest_framework/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**AI 加持、中文友好的接口自动化测试框架**（Python）

零代码基础也能写接口用例：YAML 描述、全中文报错、支持中文比较符；
内置规则引擎可从 OpenAPI/Swagger 文档一键生成用例，接入大模型后还能自动补充边界场景。

## 特性

- **低代码**：YAML 写用例，不懂 Python 也能上手
- **中文友好**：中文报错、中文比较符（`等于`、`包含`、`正则匹配`）、中文文档
- **AI 加持**：`atf gen` 从 OpenAPI/Swagger 生成用例，`--llm` 调用大模型补充边界用例
- **流程编排**：变量提取与传递（`extract`），轻松实现「登录 → 携带令牌访问」
- **数据驱动**：`${变量}` 占位符贯穿请求、断言，支持环境变量与 `--env` 配置文件
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
| `atf run <用例文件或目录> [-e 环境配置.yaml] [--html 路径] [--allure 目录] [-t 超时秒]` | 执行用例，可同时生成报告，全部通过退出码为 0 |
| `atf gen <openapi.json> [-o 输出目录] [--llm]` | 生成用例 |
| `atf --version` | 查看版本 |

## 路线图

- [x] v0.1 核心引擎：YAML 用例 / 变量提取 / 中英文断言 / 控制台报告 / AI 生成
- [x] v0.2 项目脚手架、测试报告 HTML + Allure、pytest 插件
- [ ] v0.3 数据驱动（CSV/Excel）、数据库断言插件、钩子函数
- [ ] v0.4 AI 失败用例智能分析（自动定位是接口变更还是用例问题）

## 参与贡献

欢迎 Issue 和 PR。开发规范见 [AGENTS.md](AGENTS.md)。

## License

MIT
