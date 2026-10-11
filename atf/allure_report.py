"""导出 Allure 结果（allure-results 目录），供 allure generate 生成报告

本模块只负责产出 Allure 标准格式的结果文件，不依赖 allure CLI 或 Java；
用户已有 Allure 环境时可直接生成 HTML 报告。
"""
import json
import platform
import uuid
from pathlib import Path

from . import __version__


def write_allure_results(suites: list, results_dir="allure-results") -> Path:
    """把用例执行结果写入 Allure 结果目录，返回该目录路径"""
    target = Path(results_dir)
    target.mkdir(parents=True, exist_ok=True)
    for suite in suites:
        result = _to_allure(suite)
        (target / f"{result['uuid']}-result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    (target / "environment.properties").write_text(
        f"Framework=ATF\n"
        f"Framework.Version={__version__}\n"
        f"Python={platform.python_version()}\n",
        encoding="utf-8",
    )
    return target


def _to_allure(suite) -> dict:
    steps = []
    for step in suite.steps:
        item = {
            "name": step.name,
            "status": "passed" if step.passed else "failed",
            "stage": "finished",
            "start": int(step.started_at * 1000),
            "stop": int((step.started_at + step.elapsed) * 1000),
        }
        if not step.passed and step.error:
            item["statusDetails"] = {"message": step.error}
        steps.append(item)
    if suite.skipped:
        steps.append({
            "name": f"因前置失败跳过 {suite.skipped} 个步骤",
            "status": "skipped",
            "stage": "finished",
        })

    failed = not suite.passed
    result = {
        "uuid": str(uuid.uuid4()),
        "name": suite.name,
        "fullName": suite.source or suite.name,
        "status": "failed" if failed else "passed",
        "stage": "finished",
        "start": int(suite.started_at * 1000),
        "stop": int((suite.started_at + sum(s.elapsed for s in suite.steps)) * 1000),
        "labels": [
            {"name": "framework", "value": "ATF"},
            {"name": "language", "value": "python"},
            {"name": "suite", "value": suite.name},
        ],
        "steps": steps,
    }
    if failed:
        result["statusDetails"] = {
            "message": next((s.error for s in suite.steps if s.error), "用例执行失败")
        }
    return result
