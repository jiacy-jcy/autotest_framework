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
├── template.py   变量渲染（${var} 与命名空间 ${env.x} / ${sys.X}）
├── extractor.py  响应取值（JSON 路径 / status_code / headers.x / re:正则）
├── assertion.py  断言引擎（中英文比较符）
├── report.py     中文控制台报告
├── html_report.py 自研单文件 HTML 报告（零依赖、内联样式）
├── allure_report.py 导出 Allure 结果（allure-results）
├── ai.py         OpenAPI→用例生成（规则引擎 + 可选 LLM 增强）
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
- v0.3（进行中）：CSV/Excel 数据驱动（已完成）、数据库断言、钩子函数
- 开发约定补充：pytest 插件测试放 `pytest_tests/`（用 pytester），勿放 `tests/`（后者由 unittest 收集，不依赖 pytest）
- 发布 PyPI 前：确认包名可用并改名（pyproject.toml 中 `name`）
- 已完成：GitHub Actions CI（`.github/workflows/test.yml`：Python 3.9–3.12 单测矩阵 + 端到端冒烟）
