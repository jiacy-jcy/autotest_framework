"""命令行入口：atf run 执行用例 / atf gen 生成用例"""
import argparse
import sys

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

    p_gen = sub.add_parser("gen", help="从 OpenAPI/Swagger 文档生成用例（--llm 可 AI 增强）")
    p_gen.add_argument("spec", help="OpenAPI/Swagger 文档路径（JSON 格式）")
    p_gen.add_argument("-o", "--output", default="cases", help="用例输出目录，默认 cases")
    p_gen.add_argument("--llm", action="store_true",
                       help="调用大模型补充边界用例（需配置 ATF_AI_API_KEY 等环境变量）")

    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            return _cmd_run(args)
        if args.command == "gen":
            return _cmd_gen(args)
    except ATFError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    parser.print_help()
    return 0


def _cmd_run(args) -> int:
    from .parser import find_case_files, load_case_file, load_env_file
    from .report import print_suite, print_summary
    from .runner import Runner

    env = load_env_file(args.env) if args.env else {}
    runner = Runner(env=env, timeout=args.timeout)
    suites = [runner.run_case(load_case_file(file)) for file in find_case_files(args.case)]
    for suite in suites:
        print_suite(suite)
    return 0 if print_summary(suites) else 1


def _cmd_gen(args) -> int:
    from .ai import generate_from_openapi

    target = generate_from_openapi(args.spec, args.output, use_llm=args.llm)
    print(f"已生成用例文件：{target}")
    return 0
