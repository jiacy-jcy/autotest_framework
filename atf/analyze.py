"""AI 失败用例智能分析

先由规则引擎给出离线可用的初步分类，配置大模型后再精修分类与建议：
- 无密钥：只输出规则判断（离线可用）
- 有密钥：把失败信息交给大模型，返回更准确的原因与修复建议

分类取值：环境问题 / 认证问题 / 接口变更 / 服务端异常 / 用例问题 / 未知
"""
import json
import os
from dataclasses import dataclass

import httpx

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

    def to_dict(self) -> dict:
        return {
            "suite": self.suite, "step": self.step, "method": self.method,
            "url": self.url, "status_code": self.status_code, "error": self.error,
            "category": self.category, "reason": self.reason,
            "suggestion": self.suggestion, "source": self.source,
        }


def analyze_failures(suites: list, use_ai: bool = True) -> list:
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
            ))
    if analyses and use_ai:
        analyses = _refine_with_llm(analyses)
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


def _refine_with_llm(analyses: list) -> list:
    base_url = os.environ.get("ATF_AI_BASE_URL", "https://api.openai.com/v1")
    api_key = os.environ.get("ATF_AI_API_KEY", "")
    model = os.environ.get("ATF_AI_MODEL", "gpt-4o-mini")
    if not api_key:
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
        resp = httpx.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            timeout=60,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        refined = json.loads(_strip_code_fence(text))
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


def _sources(analyses: list) -> str:
    kinds = []
    for item in analyses:
        if item.source not in kinds:
            kinds.append(item.source)
    return "、".join(kinds)
