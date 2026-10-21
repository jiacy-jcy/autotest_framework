"""自研单文件 HTML 报告：零依赖、全中文、可直接分享

生成的 HTML 内联全部样式，不引用任何外部资源，双击即可查看。
"""
import html
from datetime import datetime
from pathlib import Path

from .trend import trend_svg

_CSS = """
* { box-sizing: border-box; }
body { margin: 0; background: #f5f7fa; color: #1f2733;
  font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", system-ui, sans-serif; }
.container { max-width: 1080px; margin: 0 auto; padding: 32px 20px 64px; }
header h1 { margin: 0 0 4px; font-size: 26px; }
.meta { color: #6b7686; margin: 0 0 24px; font-size: 13px; }
.cards { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 28px; }
.card { flex: 1 1 120px; background: #fff; border-radius: 10px; padding: 14px 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,.06); border-top: 3px solid #c8d0dc; }
.card .num { font-size: 24px; font-weight: 700; }
.card .label { font-size: 12px; color: #6b7686; margin-top: 2px; }
.card.passed { border-top-color: #22a06b; } .card.passed .num { color: #22a06b; }
.card.failed { border-top-color: #e5484d; } .card.failed .num { color: #e5484d; }
.card.skipped { border-top-color: #b08900; } .card.skipped .num { color: #b08900; }
.suite { background: #fff; border-radius: 10px; margin-bottom: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,.06); overflow: hidden; }
.suite-head { padding: 16px 18px; border-bottom: 1px solid #eef1f5; }
.suite-head h2 { margin: 0; font-size: 17px; display: flex; align-items: center; gap: 10px; }
.source { display: block; color: #8a94a3; font-size: 12px; margin-top: 4px; word-break: break-all; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; padding: 10px 18px; border-bottom: 1px solid #eef1f5; vertical-align: top; }
th { color: #6b7686; font-weight: 600; font-size: 12px; background: #fafbfc; }
.mono { font-family: Consolas, Menlo, monospace; }
.url { word-break: break-all; }
.badge { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 12px; color: #fff; }
.badge.passed { background: #22a06b; } .badge.failed { background: #e5484d; } .badge.skipped { background: #b08900; }
.row-failed td { background: #fff6f6; }
.detail-row td { background: #fafbfc; }
.detail-row summary { cursor: pointer; color: #3b6fd4; font-size: 13px; }
.block { margin: 10px 0 0; }
.block-title { font-size: 12px; color: #6b7686; margin-bottom: 4px; }
pre { margin: 0; background: #1f2733; color: #e6edf3; padding: 12px 14px; border-radius: 8px;
  overflow: auto; font-size: 12px; line-height: 1.5; max-height: 320px; white-space: pre-wrap; word-break: break-all; }
.error { color: #c0392b; background: #fdecea; padding: 10px 12px; border-radius: 8px; font-size: 13px; margin-top: 8px; }
.axis { font-size: 10px; fill: #8a94a3; }
.label { font-size: 12px; fill: #3b6fd4; }
.trend-note { color: #8a94a3; font-size: 12px; margin: 4px 0; }
.analysis { background: #fff; border-radius: 10px; padding: 16px 18px; margin-bottom: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,.06); border-left: 4px solid #7b61ff; }
.analysis h2 { margin: 0 0 8px; font-size: 16px; }
.analysis-item { padding: 10px 0; border-top: 1px solid #eef1f5; }
.analysis-item:first-of-type { border-top: none; }
.analysis-head { display: flex; justify-content: space-between; gap: 10px; font-size: 14px; }
.analysis-body { color: #4a5568; font-size: 13px; margin-top: 4px; line-height: 1.6; }
.cat { display: inline-block; padding: 1px 9px; border-radius: 999px; font-size: 12px; color: #fff; background: #6b7686; white-space: nowrap; }
.cat.api { background: #e5484d; } .cat.case { background: #b08900; } .cat.env { background: #3b6fd4; }
.cat.auth { background: #8250df; } .cat.server { background: #c0392b; } .cat.unknown { background: #8a94a3; }
footer { text-align: center; color: #8a94a3; font-size: 12px; margin-top: 30px; }
"""

_CATEGORY_CLASS = {
    "接口变更": "api", "用例问题": "case", "环境问题": "env",
    "认证问题": "auth", "服务端异常": "server", "未知": "unknown",
}


def write_html_report(suites: list, path="reports/atf-report.html", analyses: list = None,
                      trend: list = None) -> Path:
    """生成 HTML 报告文件，返回文件路径。analyses 为失败分析，trend 为历史记录（可选）"""
    target = Path(path)
    if target.suffix.lower() not in (".html", ".htm"):
        target = target / "atf-report.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_render(suites, analyses, trend), encoding="utf-8")
    return target


def _render(suites: list, analyses: list = None, trend: list = None) -> str:
    stats = _stats(suites)
    cards = "\n".join(_suite_card(suite) for suite in suites) or '<p>没有可展示的用例。</p>'
    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>ATF 智测 · 测试报告</title>\n"
        f"<style>{_CSS}</style>\n</head>\n<body>\n<div class=\"container\">\n"
        f"{_header()}\n{_summary(stats)}\n{_trend_section(trend)}\n"
        f"{_analysis_section(analyses)}\n{cards}\n{_footer()}\n"
        "</div>\n</body>\n</html>\n"
    )


def _trend_section(records) -> str:
    if not records:
        return ""
    return ('<section class="suite"><div class="suite-head"><h2>'
            f"通过率趋势（最近 {len(records)} 次）</h2></div>"
            '<div style="padding: 8px 18px 12px">' + trend_svg(records) + "</div></section>")


def _analysis_section(analyses: list) -> str:
    if not analyses:
        return ""
    items = []
    for item in analyses:
        css_class = _CATEGORY_CLASS.get(item.category, "unknown")
        target = f"{item.method} {item.url}".strip()
        items.append(
            '<div class="analysis-item">'
            f'<div class="analysis-head"><span>{html.escape(item.suite)} / {html.escape(item.step)}'
            f'<span class="mono">　{html.escape(target)}</span></span>'
            f'<span class="cat {css_class}">{html.escape(item.category)}</span></div>'
            f'<div class="analysis-body">原因：{html.escape(item.reason)}<br>'
            f'建议：{html.escape(item.suggestion)}（来源：{html.escape(item.source)}）</div>'
            "</div>"
        )
    return '<section class="analysis"><h2>失败分析</h2>' + "".join(items) + "</section>"


def _header() -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return ("<header><h1>ATF 智测 · 测试报告</h1>"
            f'<p class="meta">生成时间：{now}</p></header>')


def _summary(stats: dict) -> str:
    def card(css_class, num, label):
        return (f'<div class="card {css_class}">'
                f'<div class="num">{num}</div><div class="label">{label}</div></div>')

    return ("<div class=\"cards\">"
            + card("", stats["total"], "总计")
            + card("passed", stats["passed"], "通过")
            + card("failed", stats["failed"], "失败")
            + card("skipped", stats["skipped"], "跳过")
            + card("", f'{stats["elapsed"]:.2f}s', "总耗时")
            + card("", f'{stats["rate"]:.1f}%', "通过率")
            + "</div>")


def _suite_card(suite) -> str:
    ok = suite.passed
    badge = f'<span class="badge {"passed" if ok else "failed"}">{"通过" if ok else "失败"}</span>'
    rows = "\n".join(_step_row(step) for step in suite.steps)
    skipped_row = ""
    if suite.skipped:
        skipped_row = ('<tr class="row-skipped"><td><span class="badge skipped">跳过</span></td>'
                       f'<td colspan="5">因前置步骤失败，跳过 {suite.skipped} 个步骤</td></tr>')
    return (
        '<section class="suite">'
        f'<div class="suite-head"><h2>{html.escape(suite.name)} {badge}</h2>'
        f'<span class="source">{html.escape(suite.source)}</span></div>'
        "<table><thead><tr>"
        "<th>状态</th><th>步骤</th><th>方法</th><th>接口</th><th>状态码</th><th>耗时</th>"
        f"</tr></thead><tbody>{rows}{skipped_row}</tbody></table></section>"
    )


def _step_row(step) -> str:
    status = "passed" if step.passed else "failed"
    label = "通过" if step.passed else "失败"
    code = "-" if step.detail.status_code is None else str(step.detail.status_code)
    row = (
        f'<tr class="row-{status}">'
        f'<td><span class="badge {status}">{label}</span></td>'
        f'<td class="step-name">{html.escape(step.name)}</td>'
        f'<td class="mono">{html.escape(step.detail.method or "-")}</td>'
        f'<td class="mono url">{html.escape(step.detail.url or "-")}</td>'
        f'<td class="mono">{code}</td>'
        f'<td class="mono">{step.elapsed:.2f}s</td>'
        "</tr>"
    )
    return row + _step_detail(step)


def _step_detail(step) -> str:
    blocks = []
    if step.error:
        blocks.append(f'<div class="error">{html.escape(step.error)}</div>')
    if step.detail.request_body:
        blocks.append('<div class="block"><div class="block-title">请求体</div>'
                      f'<pre>{html.escape(step.detail.request_body)}</pre></div>')
    if step.detail.response_body:
        blocks.append('<div class="block"><div class="block-title">响应体</div>'
                      f'<pre>{html.escape(step.detail.response_body)}</pre></div>')
    if not blocks:
        return ""
    opened = "" if step.passed else " open"
    return (f'<tr class="detail-row"><td colspan="6">'
            f'<details{opened}><summary>查看详情</summary>{"".join(blocks)}</details>'
            "</td></tr>")


def _footer() -> str:
    return '<footer>由 ATF 智测（AI 加持、中文友好的接口自动化测试框架）生成</footer>'


def _stats(suites: list) -> dict:
    total = sum(len(suite.steps) for suite in suites)
    failed = sum(1 for suite in suites for step in suite.steps if not step.passed)
    skipped = sum(suite.skipped for suite in suites)
    elapsed = sum(step.elapsed for suite in suites for step in suite.steps)
    passed = total - failed
    rate = (passed / total * 100) if total else 0.0
    return {"total": total, "passed": passed, "failed": failed,
            "skipped": skipped, "elapsed": elapsed, "rate": rate}
