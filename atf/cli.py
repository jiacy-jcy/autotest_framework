"""命令行入口：atf run 执行用例 / atf gen 生成用例 / atf init 初始化项目"""
import argparse
import sys
from pathlib import Path

from . import __version__
from .errors import ATFError


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="atf", description="ATF 智测 —— AI 加持、中文友好的接口自动化测试框架"
    )
    parser.add_argument("--version", action="version", version=f"atf {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="命令")

    p_run = sub.add_parser("run", help="执行 YAML 用例（支持单个文件或整个目录）")
    p_run.add_argument("case", help="用例文件或目录路径")
    p_run.add_argument("-e", "--env", help="环境变量配置文件（YAML 键值对）")
    p_run.add_argument("-t", "--timeout", type=float, default=30.0, help="请求超时秒数，默认 30")
    p_run.add_argument("--html", nargs="?", const="reports/atf-report.html", default=None,
                       help="生成 HTML 报告，可指定路径（默认 reports/atf-report.html）")
    p_run.add_argument("--allure", nargs="?", const="allure-results", default=None,
                       help="导出 Allure 结果目录，可指定路径（默认 allure-results）")
    p_run.add_argument("--ai-analyze", action="store_true",
                       help="失败时分析原因（配置 ATF_AI_API_KEY 则用大模型，否则给出规则判断）")
    p_run.add_argument("--tags", help="仅运行包含指定标签的用例，多个用逗号分隔，如 smoke,login")
    p_run.add_argument("-w", "--workers", type=int, default=1, help="并发执行的用例数，默认 1（顺序执行）")
    p_run.add_argument("--retry", type=int, default=0, help="失败用例重试次数，默认 0")

    p_gen = sub.add_parser("gen", help="从 OpenAPI/Swagger 文档生成用例（--llm 可 AI 增强）")
    p_gen.add_argument("spec", help="OpenAPI/Swagger 文档路径（JSON 格式）")
    p_gen.add_argument("-o", "--output", default="cases", help="用例输出目录，默认 cases")
    p_gen.add_argument("--llm", action="store_true",
                       help="调用大模型补充边界用例（需配置 ATF_AI_API_KEY 等环境变量）")

    p_init = sub.add_parser("init", help="初始化示例项目（生成配置、用例与演示服务）")
    p_init.add_argument("dir", nargs="?", default=".", help="目标目录，默认当前目录")
    p_init.add_argument("--force", action="store_true", help="覆盖已存在的同名文件")

    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            return _cmd_run(args)
        if args.command == "gen":
            return _cmd_gen(args)
        if args.command == "init":
            return _cmd_init(args)
    except ATFError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    parser.print_help()
    return 0


def _cmd_run(args) -> int:
    from .parser import case_tags, load_case_file, load_env_file, resolve_case_files
    from .report import print_suite, print_summary
    from .runner import Runner

    env = load_env_file(args.env) if args.env else {}
    tag_filter = _parse_tags(getattr(args, "tags", None))

    cases = []
    for file in resolve_case_files(args.case):
        case = load_case_file(file)
        if tag_filter and not tag_filter.intersection(case_tags(case)):
            continue
        cases.append(case)
    if not cases:
        print("没有匹配的用例（请检查路径与 --tags 标签过滤）")
        return 0

    runner = Runner(env=env, timeout=args.timeout, retry=args.retry)
    suites = runner.run_cases(cases, workers=args.workers)
    for suite in suites:
        print_suite(suite)
    all_passed = print_summary(suites)

    analyses = None
    if getattr(args, "ai_analyze", False):
        from .analyze import analyze_failures, print_analysis

        analyses = analyze_failures(suites)
        print_analysis(analyses)

    if args.html:
        from .html_report import write_html_report

        path = write_html_report(suites, args.html, analyses=analyses)
        print(f"HTML 报告已生成：{Path(path).resolve()}")
    if args.allure:
        from .allure_report import write_allure_results

        path = write_allure_results(suites, args.allure)
        print(f"Allure 结果已导出：{Path(path).resolve()}"
              f"（可执行 allure generate {path} -o allure-report 生成 HTML 报告）")
    return 0 if all_passed else 1


def _parse_tags(value) -> set:
    if not value:
        return set()
    return {item.strip() for item in str(value).split(",") if item.strip()}


def _cmd_gen(args) -> int:
    from .ai import generate_from_openapi

    target = generate_from_openapi(args.spec, args.output, use_llm=args.llm)
    print(f"已生成用例文件：{target}")
    return 0


def _cmd_init(args) -> int:
    from .scaffold import init_project

    root, created, skipped = init_project(args.dir, force=args.force)
    print(f"√ 已初始化 ATF 项目：{root.resolve()}")
    if created:
        print("  已生成：")
        for name in created:
            print(f"    {name}")
    if skipped:
        print("  已存在（未覆盖，如需覆盖请加 --force）：")
        for name in skipped:
            print(f"    {name}")
    print("\n下一步：")
    print("  1. 启动演示服务：python mock_server.py")
    print("  2. 执行示例用例：atf run cases/example.yaml -e config.yaml")
    print("  3. 修改 config.yaml 的 base_url 指向你的接口，开始编写用例")
    return 0
