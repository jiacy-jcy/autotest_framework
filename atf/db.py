"""数据库断言：执行 SQL 并把结果适配为可被 extractor / 断言消费的对象

- SQLite 使用标准库 sqlite3，零依赖
- MySQL 需要 PyMySQL（可选依赖 atf[mysql]）
- PostgreSQL 需要 psycopg2（可选依赖 atf[postgresql]）

连接串（url）示例：
- sqlite:///demo.db            相对当前工作目录
- sqlite:////abs/path/demo.db  绝对路径（Unix）
- sqlite:///C:/abs/demo.db     Windows 绝对路径
- sqlite:///:memory:           内存库
- mysql://user:pass@host:3306/dbname
- postgresql://user:pass@host:5432/dbname
"""
import json
from pathlib import Path
from urllib.parse import urlparse

from .errors import ATFError

_SQLITE_SCHEMES = ("sqlite", "sqlite3")
_MYSQL_SCHEMES = ("mysql", "mysql+pymysql")
_POSTGRES_SCHEMES = ("postgresql", "postgres", "postgresql+psycopg2")


class QueryResult:
    """把查询结果适配成 extractor 能消费的响应对象"""

    def __init__(self, rows: list):
        self.rows = rows

    @property
    def status_code(self):
        return None

    @property
    def headers(self):
        return {}

    @property
    def text(self) -> str:
        return json.dumps(self.rows, ensure_ascii=False, default=str)

    def json(self):
        return self.rows


def query(config: dict, base_dir=None) -> QueryResult:
    """按步骤中的 db 配置执行查询，返回 QueryResult（sqlite 相对路径基于 base_dir）"""
    url = config.get("url")
    sql = config.get("query")
    if not url:
        raise ATFError("数据库步骤缺少 url（连接串）")
    if not sql:
        raise ATFError("数据库步骤缺少 query（SQL 语句）")
    connection = _connect(url, base_dir)
    try:
        cursor = connection.cursor()
        params = config.get("args") or config.get("params")
        if params is not None:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        data = [dict(zip(columns, row)) for row in rows]
        connection.commit()
        return QueryResult(data)
    except ATFError:
        raise
    except Exception as exc:  # 驱动种类繁多，统一转换为中文提示
        raise ATFError(f"数据库操作失败：{exc}") from None
    finally:
        connection.close()


def _connect(url: str, base_dir=None):
    parsed = urlparse(url)
    scheme = parsed.scheme
    if scheme in _SQLITE_SCHEMES:
        import sqlite3

        return sqlite3.connect(_sqlite_path(url, base_dir))
    if scheme in _MYSQL_SCHEMES:
        try:
            import pymysql
        except ImportError:
            raise ATFError("连接 MySQL 需要 PyMySQL，请先安装：pip install atf[mysql]") from None
        return pymysql.connect(
            host=parsed.hostname or "127.0.0.1",
            port=parsed.port or 3306,
            user=parsed.username or "",
            password=parsed.password or "",
            database=(parsed.path or "").lstrip("/"),
            charset="utf8mb4",
        )
    if scheme in _POSTGRES_SCHEMES:
        try:
            import psycopg2
        except ImportError:
            raise ATFError("连接 PostgreSQL 需要 psycopg2，请先安装：pip install atf[postgresql]") from None
        return psycopg2.connect(
            host=parsed.hostname or "127.0.0.1",
            port=parsed.port or 5432,
            user=parsed.username or "",
            password=parsed.password or "",
            dbname=(parsed.path or "").lstrip("/"),
        )
    raise ATFError(f"不支持的数据库类型：{scheme}（支持 sqlite / mysql / postgresql）")


def _sqlite_path(url: str, base_dir=None) -> str:
    rest = url.split("://", 1)[1]
    if rest in (":memory:", "/:memory:"):
        return ":memory:"
    path = rest[1:] if rest.startswith("/") else rest
    # 相对路径基于用例所在目录解析，与数据文件/子用例的规则保持一致
    if base_dir and not Path(path).is_absolute():
        return str(Path(base_dir) / path)
    return path
