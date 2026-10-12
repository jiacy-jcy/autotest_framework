"""生成数据库断言示例数据：python examples/make_sqlite_db.py（在当前目录生成 demo.db）"""
import sqlite3

conn = sqlite3.connect("demo.db")
conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, status TEXT)")
conn.execute("DELETE FROM users")
conn.executemany(
    "INSERT INTO users (id, name, status) VALUES (?, ?, ?)",
    [(1, "张三", "active"), (2, "李四", "disabled")],
)
conn.commit()
conn.close()
print("已生成 demo.db（可与 examples/cases/db_check.yaml 配合使用）")
