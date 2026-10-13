# AGENTS.md —— ATF 智测开发指南

## 项目定位

AI 加持、中文友好的 Python 接口自动化测试框架。两大差异化：**AI 用例生成** 与 **全中文体验**（报错、比较符、文档）。
规划方向：开源积累影响力 → 内容推广 → 远期商业化。

## 目录结构

```
atf/            框架核心包
├── cli.py        命令行入口（run / gen / init）
├── scaffold.py   atf init 脚手架（内嵌模板，零打包配置）
├── runner.py     执行引擎：渲染变量→发请求→提取→断言
├── parser.py     YAML 用例加载与格式校验
├── data.py       数据驱动（CSV/Excel 加载，值统一为字符串）
├── db.py         数据库断言（SQLite 内置；MySQL/PostgreSQL 可选依赖）
├── hooks.py      生命周期钩子（before/after_case、before/after_step）
├── plugins.py    插件系统（注册自定义比较符/提取器；config.plugins 与 entry point）
├── template.py   变量渲染（${var} 与命名空间 ${env.x} / ${sys.X}）
├── extractor.py  响应取值（JSON 路径 / status_code / headers.x / re:正则）
├── assertion.py  断言引擎（中英文比较符）
├── report.py     中文控制台报告
├── html_report.py 自研单文件 HTML 报告（零依赖、内联样式）
├── allure_report.py 导出 Allure 结果（allure-results）
├── ai.py         OpenAPI→用例生成（规则引擎 + 可选 LLM 增强）
├── analyze.py    失败分析（规则分类 + 可选 LLM 精修）
├── pytest_plugin.py pytest 插件（YAML 用例接入 pytest，entry point pytest11）
└── errors.py     异常体系（错误信息必须中文）
examples/       离线可跑的示例（mock_server + 用例 + openapi.json）
tests/          框架自身测试（unittest，零额外依赖）
pytest_tests/   pytest 插件测试（依赖 pytest，用 pytester 隔离运行）
.github/        GitHub Actions CI（单元测试矩阵 + pytest 插件 + 端到端冒烟）
```

## 常用命令

```bash
python -m venv .venv && .venv\Scripts\pip install -e .   # 环境搭建
.venv\Scripts\python -m unittest discover -s tests       # 跑测试
.venv\Scripts\python examples\mock_server.py             # 启动演示接口（8899 端口）
.venv\Scripts\atf run examples\cases\user_flow.yaml -e examples\config.yaml  # 端到端验证
```

## 开发约定（重要）

- **一切面向用户的信息必须中文**：报错、CLI 帮助、报告、文档、注释
- 控制台输出只用 GBK 安全字符（√ × ……），避免用户终端乱码
- 依赖保持极简（当前仅 httpx + PyYAML），新增依赖需在 README 说明理由
- 测试用 stdlib unittest（零额外依赖）；涉及 HTTP 的测试用内置 mock server（`http.server` 起随机端口），不依赖外网
- 新特性必须同步：单测 + README 说明 + examples 示例（如适用）
- AI 相关功能必须「无密钥可回退」，保证离线可用
- 变量来源必须用命名空间区分：`${name}` 为用例/运行时变量，`${env.name}` 为 `--env` 配置，`${sys.NAME}` 为系统环境变量
- 无前缀变量**禁止**回退系统环境变量（Windows 环境变量大小写不敏感，`${username}` 会静默命中系统 `USERNAME`）；只有显式 `${sys.NAME}` 才读取系统变量
- 数据驱动值统一为字符串，避免数字列在请求体中意外变数字；断言 `eq`/`ne` 做字符串回退（`"0"` 与 `0` 相等）
- YAML 流式序列 `[a, b]` 中引用 `${变量}` 必须加引号（`[$.code, "${x}"]`），否则 `{` 会被误判为映射起点
- 修改本文件涉及的任何结构/命令/约定时，同步更新本文件

## 路线图（发布前检查项）

- v0.2（已完成，0.2.0）：`atf init` 脚手架、测试报告 HTML + Allure、pytest 插件
- v0.3（已完成，0.3.0）：CSV/Excel 数据驱动、数据库断言、钩子函数
- v0.4（已完成，0.4.0）：AI 失败分析（`atf run --ai-analyze`，规则分类 + LLM 精修）
- v0.5（已完成，0.5.0）：执行增强（套件/标签/`-w` 并发/`--retry` 重试）、插件系统
- 插件契约：模块提供 `register(registry)`，用 `registry.register_comparator/register_extractor` 注册；同时支持 entry point 组 `atf.plugins`
- 开发约定补充：pytest 插件测试放 `pytest_tests/`（用 pytester），勿放 `tests/`（后者由 unittest 收集，不依赖 pytest）
- 钩子事件：before_case / after_case / before_step / after_step；钩子文件会自动从「当前目录 + 用例目录」导入
- 发布 PyPI 前：确认包名可用并改名（pyproject.toml 中 `name`）
- 已完成：GitHub Actions CI（`.github/workflows/test.yml`：Python 3.9–3.12 单测矩阵 + 端到端冒烟）

### 后续迭代规划（v0.6 → v1.0）

总方向：**补复用短板 → 降使用门槛 → v1.0 稳定发布**。不内置浏览器自动化（UI 层留给插件生态）。

- v0.6 复用度补强（优先级最高，团队采用的分水岭）：
  - 套件级会话共享：`config` 新增 `session: shared`，套件内复用同一 httpx.Client，登录一次全程携带
  - 子用例引用：步骤支持 `use: login.yaml`，公共前置模块化（改一处全套件生效）
  - 内置变量函数：`${uuid()}` / `${timestamp()}` / `${rand_str(8)}` / `${int(1,100)}`，模板层函数求值
  - 报告脱敏：`config.mask` 列表，HTML/Allure 报告中打码敏感字段
- v0.7 断言与提取增强：
  - JSON Schema 断言（jsonschema 作可选依赖 `atf[schema]`）
  - 类型断言 `is_type`、数组包含 `contains_any`
  - HTML/XPath 提取器（可选依赖 `atf[html]`，注册 `xpath:` 前缀；兼作插件生态样板）
- v0.8 零代码生成生态（差异化主打）：
  - HAR → 用例：`atf gen --har`，浏览器 DevTools 导出一键转换（对无 OpenAPI 的零基础用户是杀手级功能）
  - curl → 用例：`atf gen --curl`
  - OpenAPI 生成增强：识别 `securitySchemes` 自动串联登录流；参数枚举自动参数化
  - AI 修补建议：失败分析给出用例修改 diff（ai-fix）
- v0.9 企业落地：
  - 多环境 profile：config 内 dev/test/prod 分区，`--env-name` 切换
  - 报告趋势：本地累积历史通过率，HTML 报告画趋势图
  - CI/CD 示例：GitHub Actions / Jenkins / GitLab CI 文档与模板
- v1.0 稳定与发布：
  - 改名 + 发布 PyPI（建议提前到 v0.7/v0.8 先发 0.x，`pip install -e .` 对普通用户是门槛，早发布早积累用户）
  - 插件生态：`atf.plugins` entry point 规范文档 + 官方示例插件
  - 规模验证：数千用例下 `-w` 并发与报告生成的性能

### 关键决策

- **UI 层不内置**：不引入 Selenium/Playwright，另写《ATF + Playwright 分层实践》文档引导组合使用，保持「AI + 中文 + 极简依赖」定位
- **依赖约束延续**：新能力一律走可选依赖（`atf[excel]` 模式），核心保持 httpx + PyYAML
- HAR/curl 生成与子用例引用需同步在 `pytest_tests/` 补 pytest 插件侧行为验证
