import unittest

from atf.errors import ATFError, ExtractError
from atf.extractor import extract_value
from atf.plugins import ensure_loaded, registry

try:
    import lxml  # noqa: F401
    HAS_LXML = True
except ImportError:
    HAS_LXML = False

_PAGE = "<html><body><h1>你好，世界</h1><p id='greet'>ATF 智测</p></body></html>"


class _Stub:
    def __init__(self, text):
        self.text = text


class TestXpathExtractor(unittest.TestCase):
    def setUp(self):
        ensure_loaded()

    def test_registered_via_plugin_contract(self):
        # 以插件形式注册（与第三方插件同一套 register 契约）
        self.assertIn("xpath", registry.extractors)

    @unittest.skipUnless(HAS_LXML, "未安装 lxml")
    def test_extract_element_text(self):
        self.assertEqual(extract_value(_Stub(_PAGE), "xpath://h1"), "你好，世界")

    @unittest.skipUnless(HAS_LXML, "未安装 lxml")
    def test_extract_attribute(self):
        self.assertEqual(extract_value(_Stub(_PAGE), "xpath://p/@id"), "greet")

    @unittest.skipUnless(HAS_LXML, "未安装 lxml")
    def test_no_match_chinese_error(self):
        with self.assertRaises(ExtractError):
            extract_value(_Stub("<html></html>"), "xpath://h1")

    @unittest.skipUnless(HAS_LXML, "未安装 lxml")
    def test_bad_expression_chinese_error(self):
        with self.assertRaises(ATFError):
            extract_value(_Stub(_PAGE), "xpath://[")

    @unittest.skipUnless(HAS_LXML, "未安装 lxml")
    def test_empty_text_chinese_error(self):
        with self.assertRaises(ExtractError):
            extract_value(_Stub(""), "xpath://h1")


if __name__ == "__main__":
    unittest.main()
