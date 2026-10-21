"""一次性生成全部演示数据：python examples/prepare_demo_data.py

- demo.db                数据库断言示例用（examples/cases/db_check.yaml）
- cases/login_data.xlsx  Excel 数据驱动示例用（examples/cases/excel_datas.yaml）

只生成缺失的文件；已存在则跳过。
"""
import sqlite3
from pathlib import Path

HERE = Path(__file__).parent

_USERS_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, status TEXT)"
)
_USERS_ROWS = [(1, "张三", "active"), (2, "李四", "disabled")]
_LOGIN_ROWS = [
    ["case_name", "username", "password", "expect_code", "expect_msg"],
    ["正确登录", "admin", "123456", "0", "成功"],
    ["密码错误", "admin", "wrong-password", "1001", "密码错误"],
]


def make_demo_db() -> Path:
    target = HERE / "demo.db"
    if target.exists():
        print(f"已存在，跳过：{target}")
        return target
    conn = sqlite3.connect(target)
    conn.execute(_USERS_SCHEMA)
    conn.executemany("INSERT INTO users (id, name, status) VALUES (?, ?, ?)", _USERS_ROWS)
    conn.commit()
    conn.close()
    print(f"已生成：{target}")
    return target


def make_login_xlsx() -> Path:
    target = HERE / "cases" / "login_data.xlsx"
    if target.exists():
        print(f"已存在，跳过：{target}")
        return target
    try:
        from openpyxl import Workbook
    except ImportError:
        print(f"提示：未安装 openpyxl，跳过 {target.name}（pip install -e \".[excel]\" 后重新运行）")
        return target
    workbook = Workbook()
    sheet = workbook.active
    for row in _LOGIN_ROWS:
        sheet.append(row)
    workbook.save(target)
    print(f"已生成：{target}")
    return target


if __name__ == "__main__":
    make_demo_db()
    make_login_xlsx()
    print("演示数据准备完毕。")
