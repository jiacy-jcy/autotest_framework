import tempfile
import unittest
from pathlib import Path

from atf.data import load_data_file, resolve_data_path
from atf.errors import ATFError


class TestData(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _csv(self, name, content):
        path = self.dir / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_csv_values_are_strings(self):
        path = self._csv("d.csv", "case_name,code,price,code_str\n正确,1001,3.5,001\n")
        row = load_data_file(path)[0]
        self.assertEqual(row["code"], "1001")  # 统一按字符串处理
        self.assertEqual(row["price"], "3.5")
        self.assertEqual(row["code_str"], "001")
        self.assertEqual(row["case_name"], "正确")

    def test_utf8_bom_csv(self):
        path = self.dir / "bom.csv"
        path.write_bytes("\ufeffname,age\n张三,18\n".encode("utf-8"))
        row = load_data_file(path)[0]
        self.assertEqual(row["name"], "张三")
        self.assertEqual(row["age"], "18")

    def test_resolve_path_relative_to_case(self):
        case = {"__file__": str(self.dir / "cases" / "x.yaml")}
        self.assertEqual(resolve_data_path(case, "data/d.csv"),
                         self.dir / "cases" / "data" / "d.csv")

    def test_missing_file_chinese_error(self):
        with self.assertRaises(ATFError):
            load_data_file(self.dir / "nope.csv")

    def test_unsupported_extension(self):
        path = self._csv("d.txt", "a\n1\n")
        with self.assertRaises(ATFError) as ctx:
            load_data_file(path)
        self.assertIn("不支持", str(ctx.exception))

    def test_empty_data_chinese_error(self):
        with self.assertRaises(ATFError):
            load_data_file(self._csv("empty.csv", "a,b\n"))

    def test_excel_roundtrip_if_available(self):
        try:
            import openpyxl
        except ImportError:
            self.skipTest("未安装 openpyxl")
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(["name", "count"])
        sheet.append(["张三", 3])
        path = self.dir / "d.xlsx"
        workbook.save(path)
        row = load_data_file(path)[0]
        self.assertEqual(row["name"], "张三")
        self.assertEqual(row["count"], "3")  # Excel 数字也统一为字符串


if __name__ == "__main__":
    unittest.main()
