import tempfile
import unittest
from pathlib import Path

from atf.html_report import write_html_report
from atf.runner import StepDetail, StepResult, SuiteResult
from atf.trend import load_history, record, trend_svg


def _suite(passed=True, name="用例"):
    detail = StepDetail(method="GET", url="/api/x", status_code=200)
    step = StepResult("步骤", passed, 0.01, "" if passed else "断言失败", 1000.0, detail)
    return SuiteResult(name, "case.yaml", [step], 0 if passed else 1, 999.0)


class TestTrend(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.history = self.dir / "history.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_record_writes_stats(self):
        record([_suite(passed=True)], self.history)
        records = load_history(self.history)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["total"], 1)
        self.assertEqual(records[0]["passed"], 1)
        self.assertEqual(records[0]["rate"], 100.0)

    def test_record_appends(self):
        for _ in range(3):
            record([_suite(passed=False)], self.history)
        self.assertEqual(len(load_history(self.history)), 3)

    def test_load_history_limit(self):
        for _ in range(30):
            record([_suite()], self.history)
        self.assertEqual(len(load_history(self.history, limit=5)), 5)

    def test_load_history_missing_file(self):
        self.assertEqual(load_history(self.dir / "nope.jsonl"), [])

    def test_load_history_skips_broken_lines(self):
        self.history.parent.mkdir(parents=True, exist_ok=True)
        self.history.write_text('{"rate": 90}\n不是JSON\n', encoding="utf-8")
        self.assertEqual(len(load_history(self.history)), 1)

    def test_trend_svg_needs_two_records(self):
        self.assertIn("不足 2 次", trend_svg([{"time": "t", "rate": 100}]))

    def test_trend_svg_renders_points(self):
        records = [{"time": f"第{i}次", "rate": r, "passed": r, "total": 100}
                   for i, r in enumerate((100, 50, 80))]
        svg = trend_svg(records)
        self.assertIn("<svg", svg)
        self.assertIn("polyline", svg)
        self.assertEqual(svg.count("<circle"), 3)

    def test_html_report_includes_trend(self):
        for _ in range(2):
            record([_suite()], self.history)
        target = write_html_report([_suite()], self.dir / "r.html",
                                   trend=load_history(self.history))
        content = target.read_text(encoding="utf-8")
        self.assertIn("通过率趋势", content)
        self.assertIn("<svg", content)

    def test_html_report_without_trend_section(self):
        target = write_html_report([_suite()], self.dir / "r2.html")
        self.assertNotIn("通过率趋势", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
