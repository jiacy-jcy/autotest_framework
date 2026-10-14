"""HTML/XPath 提取器（可选依赖 atf[html]，使用 lxml 库）

本模块通过插件注册机制提供 xpath: 前缀的提取器，与第三方插件
使用同一套 register(registry) 契约——它同时也是「如何写一个 ATF 插件」的样板。

用法（extract 中）：
    title: "xpath://h1"        # 取第一个匹配节点的文本
    id: "xpath://p/@id"       # 取属性
"""
from .errors import ATFError, ExtractError


def register(registry):
    registry.register_extractor("xpath", extract)


def extract(result, expression):
    try:
        from lxml import html as lxml_html
    except ImportError:
        raise ATFError("XPath 提取需要 lxml，请先安装：pip install atf[html]") from None
    text = getattr(result, "text", "") or ""
    if not text:
        raise ExtractError("响应内容为空，无法执行 XPath 提取")
    try:
        nodes = lxml_html.fromstring(text).xpath(expression)
    except Exception as exc:
        raise ATFError(f"XPath 表达式错误：{expression!r}（{exc}）") from None
    if not nodes:
        raise ExtractError(f"XPath {expression!r} 未在响应内容中匹配到任何节点")
    node = nodes[0]
    if hasattr(node, "text_content"):  # 元素节点 → 取其文本
        return (node.text_content() or "").strip()
    return node  # 属性/字符串节点 → 原样返回
