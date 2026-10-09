"""框架异常体系：所有错误信息均为中文，方便使用者定位问题"""


class ATFError(Exception):
    """框架基础异常"""


class CaseFormatError(ATFError):
    """用例文件或配置文件格式错误"""


class VariableNotFoundError(ATFError):
    """引用了未定义的变量"""


class ExtractError(ATFError):
    """从响应中提取变量失败"""


class AssertFailError(ATFError):
    """接口断言失败"""
