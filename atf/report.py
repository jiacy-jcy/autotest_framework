"""中文控制台报告（v0.2 将接入 Allure）"""
from .runner import SuiteResult


def print_suite(suite: SuiteResult):
    retry_note = f"（经 {suite.attempts} 次尝试）" if suite.attempts > 1 else ""
    print(f"\n【用例集】{suite.name}{retry_note}（{suite.source}）")
    for step in suite.steps:
        mark = "√" if step.passed else "×"
        status = "通过" if step.passed else "失败"
        print(f"  {mark} {step.name} …… {status}（{step.elapsed:.2f}秒）")
        if step.error:
            print(f"      {step.error}")
    if suite.skipped:
        print(f"  - 后续 {suite.skipped} 个步骤因前置失败被跳过")


def print_summary(suites: list) -> bool:
    """打印汇总信息，返回是否全部通过（供 CLI 作为退出码）"""
    total = sum(len(suite.steps) for suite in suites)
    failed = sum(1 for suite in suites for step in suite.steps if not step.passed)
    skipped = sum(suite.skipped for suite in suites)
    elapsed = sum(step.elapsed for suite in suites for step in suite.steps)
    line = "=" * 52
    print(f"\n{line}")
    print(f"  执行完毕：共 {total} 步 | 通过 {total - failed} | 失败 {failed} | 跳过 {skipped} | 耗时 {elapsed:.2f}秒")
    print(line)
    return failed == 0
