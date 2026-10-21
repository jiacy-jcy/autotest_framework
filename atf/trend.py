"""报告趋势：本地累积历史执行结果，在 HTML 报告中绘制通过率趋势

历史记录写入 reports/history.jsonl，一行一条 JSON，只追加不修改；
趋势图用内联 SVG 绘制，不引用任何外部资源，保持报告单文件零依赖。
"""
import json
from datetime import datetime
from pathlib import Path


def record(suites: list, history_path="reports/history.jsonl") -> Path:
    """把本次执行结果追加到历史文件，返回文件路径"""
    total = sum(len(suite.steps) for suite in suites)
    failed = sum(1 for suite in suites for step in suite.steps if not step.passed)
    skipped = sum(suite.skipped for suite in suites)
    elapsed = sum(step.elapsed for suite in suites for step in suite.steps)
    passed = total - failed
    rate = round(passed / total * 100, 1) if total else 0.0
    entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": total, "passed": passed, "failed": failed,
        "skipped": skipped, "elapsed": round(elapsed, 2), "rate": rate,
    }
    path = Path(history_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path


def load_history(history_path="reports/history.jsonl", limit: int = 20) -> list:
    """读取最近 limit 条历史记录；文件不存在或个别行损坏时跳过"""
    path = Path(history_path)
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            records.append(item)
    return records[-limit:]


def trend_svg(records: list) -> str:
    """把通过率趋势渲染成内联 SVG"""
    if len(records) < 2:
        return ('<p class="trend-note">历史记录不足 2 次，暂不绘制趋势；'
                "继续带 --trend 执行即可积累。</p>")
    width, height = 640, 220
    left, right, top, bottom = 44, 16, 20, 34
    inner_w, inner_h = width - left - right, height - top - bottom

    def x(i):
        return left + inner_w * i / (len(records) - 1)

    def y(rate):
        return top + inner_h * (100 - rate) / 100

    points = " ".join(f"{x(i):.1f},{y(r['rate']):.1f}" for i, r in enumerate(records))
    dots = "".join(
        f'<circle cx="{x(i):.1f}" cy="{y(r["rate"]):.1f}" r="3.5" fill="#3b6fd4">'
        f'<title>{r["time"]}　通过率 {r["rate"]}%（{r["passed"]}/{r["total"]}）</title></circle>'
        for i, r in enumerate(records)
    )
    grid = "".join(
        f'<line x1="{left}" y1="{y(v):.1f}" x2="{width - right}" y2="{y(v):.1f}" stroke="#eef1f5"/>'
        f'<text x="{left - 8}" y="{y(v) + 4:.1f}" text-anchor="end" class="axis">{v}%</text>'
        for v in (0, 50, 100)
    )
    last = records[-1]
    label = (f'<text x="{x(len(records) - 1) - 6:.1f}" y="{y(last["rate"]) - 10:.1f}" '
             f'text-anchor="end" class="label">{last["rate"]}%</text>')
    return (f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="通过率趋势">'
            f"{grid}<polyline points=\"{points}\" fill=\"none\" "
            f'stroke="#3b6fd4" stroke-width="2">{dots}</polyline>{label}</svg>')
