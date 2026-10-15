"""AI 失败用例智能分析

先由规则引擎给出离线可用的初步分类，配置大模型后再精修分类与建议：
- 无密钥：只输出规则判断（离线可用）
- 有密钥：把失败信息交给大模型，返回更准确的原因与修复建议
- 修补建议：配置密钥后，--ai-fix 可让大模型给出修改后的步骤 YAML（以 diff 展示）

分类取值：环境问题 / 认证问题 / 接口变更 / 服务端异常 / 用例问题 / 未知
"""
import difflib
import json
import os
from dataclasses import dataclass

import httpx
import yaml

CATEGORIES = ("环境问题", "认证问题", "接口变更", "服务端异常", "用例问题", "未知")


@dataclass
class FailureAnalysis:
    suite: str
    step: str
    method: str
    url: str
    status_code: int
    error: str
    category: str
    reason: str
    suggestion: str
    source: str = "规则"
    step_yaml: str = ""    # 原始步骤 YAML，供修补建议对比
    fix: str = ""          # 建议修改（unified diff）

    def to_dict(self) -> dict:
        return {
            "suite": self.suite, "step": self.step, "method": self.method,
            "url": self.url, "status_code": self.status_code, "error": self.error,
            "category": self.category, "reason": self.reason,
            "suggestion": self.suggestion, "source": self.source, "fix": self.fix,
        }


def analyze_failures(suites: list, use_ai: bool = True, suggest_fix: bool = False) -> list:
    """分析所有失败步骤，返回 FailureAnalysis 列表"""
    analyses = []
    for suite in suites:
        for step in suite.steps:
            if step.passed:
                continue
            category, reason, suggestion = classify_by_rules(step)
            analyses.append(FailureAnalysis(
                suite=suite.name, step=step.name,
                method=step.detail.method, url=step.detail.url,
                status_code=step.detail.status_code, error=step.error,
                category=category, reason=reason, suggestion=suggestion,
                step_yaml=_dump_step(step.raw_step),
            ))
    if analyses and use_ai:
        analyses = _refine_with_llm(analyses)
    if analyses and suggest_fix and use_ai:
        analyses = _suggest_fixes(analyses)
    return analyses


def classify_by_rules(step) -> tuple:
    """基于错误信息与状态码做离线分类，返回 (分类, 原因, 建议)"""
    error = step.error or ""
    status = step.detail.status_code
    if "请求发送失败" in error or "连接" in error or "超时" in error or "timed out" in error:
        return "环境问题", "请求未能送达服务端", "确认被测服务已启动，接口地址与网络可达"
    if status in (401, 403):
        return "认证问题", f"服务端返回 {status}", "检查登录态/令牌是否有效，并确认已正确提取与传递"
    if status in (500, 502, 503, 504):
        return "服务端异常", f"服务端返回 {status}", "疑似接口缺陷，建议联系后端结合服务端日志排查"
    if status == 404:
        return "接口变更", "服务端返回 404", "接口路径可能已变更，核对最新接口文档"
    if "不是合法 JSON" in error:
        return "接口变更", "响应体不是合法 JSON", "响应格式可能已变化，核对接口返回类型"
    if "找不到字段" in error:
        return "接口变更", "响应中缺少断言的字段", "响应结构可能变化，核对该字段是否改名或被移除"
    if "断言失败" in error:
        return "用例问题", "断言期望与实际返回不一致", "核对该接口的业务规则与用例期望值/数据是否正确"
    if "未定义" in error and "变量" in error:
        return "用例问题", "用例引用了未定义的变量", "检查变量名、--env 配置与数据源列名"
    if "数据文件" in error:
        return "用例问题", "数据源存在问题", "检查数据文件路径、格式与行内容"
    if "数据库操作失败" in error:
        return "环境问题", "数据库访问失败", "检查数据库连接串与数据库可用性"
    return "未知", "未能自动归类", "请人工查看请求与响应详情"


def _dump_step(raw_step: dict) -> str:
    if not raw_step:
        return ""
    return yaml.safe_dump(raw_step, allow_unicode=True, sort_keys=False)


def _llm_complete(prompt: str) -> str:
    """调用大模型（OpenAI 兼容接口），返回回复文本"""
    base_url = os.environ.get("ATF_AI_BASE_URL", "https://api.openai.com/v1")
    api_key = os.environ.get("ATF_AI_API_KEY", "")
    model = os.environ.get("ATF_AI_MODEL", "gpt-4o-mini")
    resp = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}]},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _refine_with_llm(analyses: list) -> list:
    if not os.environ.get("ATF_AI_API_KEY", ""):
        print("提示：未配置环境变量 ATF_AI_API_KEY，仅给出规则判断（配置后可获得更精确的 AI 分析）")
        return analyses
    payload = [
        {"index": i, "step": a.step, "method": a.method, "url": a.url,
         "status": a.status_code, "error": a.error}
        for i, a in enumerate(analyses, 1)
    ]
    prompt = (
        "你是资深接口测试专家。下面是失败的接口自动化用例，请判断每个失败最可能的原因。\n"
        f"分类只能取其中之一：{'、'.join(CATEGORIES)}。\n"
        "只返回 JSON 数组，每项含 index、category、reason、suggestion 四个字段，"
        "不要任何解释或代码块标记：\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
    try:
        refined = json.loads(_strip_code_fence(_llm_complete(prompt)))
        if not isinstance(refined, list):
            return analyses
        by_index = {int(item["index"]): item for item in refined if "index" in item}
        for i, analysis in enumerate(analyses, 1):
            item = by_index.get(i)
            if not item:
                continue
            if item.get("category") in CATEGORIES:
                analysis.category = item["category"]
            analysis.reason = str(item.get("reason") or analysis.reason)
            analysis.suggestion = str(item.get("suggestion") or analysis.suggestion)
            analysis.source = "AI"
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        print(f"提示：AI 分析失败（{exc}），已回退为规则判断")
    return analyses


def _suggest_fixes(analyses: list) -> list:
    """请大模型给出每个失败步骤修改后的 YAML，并以 diff 形式附加到分析结果"""
    if not os.environ.get("ATF_AI_API_KEY", ""):
        print("提示：未配置环境变量 ATF_AI_API_KEY，无法生成用例修补建议（--ai-fix）")
        return analyses
    for analysis in analyses:
        if not analysis.step_yaml:
            continue
        prompt = (
            "你是资深接口测试专家。下面是一个失败的接口自动化步骤（YAML）、错误信息与请求概要，"
            "请给出修改后的完整步骤 YAML：保持结构与字段风格，只修改必要字段"
            "（如期望值、提取路径、接口地址），用于修复该失败。\n"
            "只返回 YAML，不要解释或代码块标记。\n\n"
            f"# 原步骤\n{analysis.step_yaml}\n# 错误信息\n{analysis.error}\n"
            f"# 请求\n{analysis.method} {analysis.url}（状态码 {analysis.status_code}）\n"
        )
        try:
            fixed_yaml = _strip_code_fence(_llm_complete(prompt))
            parsed = yaml.safe_load(fixed_yaml)
            if not isinstance(parsed, dict) or "request" not in parsed:
                continue
            analysis.fix = _diff_yaml(analysis.step_yaml, fixed_yaml)
        except (httpx.HTTPError, yaml.YAMLError, ValueError, KeyError):
            continue
    return analyses


def _diff_yaml(before: str, after: str) -> str:
    diff = difflib.unified_diff(
        before.splitlines(), after.splitlines(),
        fromfile="原步骤", tofile="建议修改", lineterm="")
    return "\n".join(diff)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    return text.strip()


def print_analysis(analyses: list):
    """在控制台打印中文分析结果"""
    if not analyses:
        print("\n未发现失败步骤，无需分析。")
        return
    print(f"\n{'-' * 52}")
    print(f"  失败分析（共 {len(analyses)} 处，来源：{_sources(analyses)}）")
    print(f"{'-' * 52}")
    for index, item in enumerate(analyses, 1):
        target = f"{item.method} {item.url}" if item.method else item.url
        print(f"[{index}] {item.suite} / {item.step}（{target}）")
        print(f"    分类：{item.category}")
        print(f"    原因：{item.reason}")
        print(f"    建议：{item.suggestion}")
        if item.fix:
            print("    建议修改（diff）：")
            for line in item.fix.splitlines():
                print(f"      {line}")


def _sources(analyses: list) -> str:
    kinds = []
    for item in analyses:
        if item.source not in kinds:
            kinds.append(item.source)
    return "、".join(kinds)
