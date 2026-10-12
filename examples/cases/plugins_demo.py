"""示例插件（ATF 插件机制演示）：注册自定义比较符与提取器"""


def register(registry):
    registry.register_comparator("约等于", _approx, "数值近似相等（误差 0.01 内）")
    registry.register_extractor("文本长度", lambda result, rest: len(result.text))


def _approx(actual, expected):
    try:
        return abs(float(actual) - float(expected)) <= 0.01
    except (TypeError, ValueError):
        return False
