from __future__ import annotations

import os
import re
from typing import Optional

import pyodbc

from ops.db_pool import ConnectionPool

SQL_SERVER = os.environ.get("SQL_SERVER", "localhost")
SQL_DATABASE = os.environ.get("SQL_DATABASE", "movie_system")
SQL_USERNAME = os.environ.get("SQL_USERNAME", "")
SQL_PASSWORD = os.environ.get("SQL_PASSWORD", "")
SQL_PASSWORD_ENCRYPTED = os.environ.get("SQL_PASSWORD_ENCRYPTED", "").lower() in ("1", "true", "yes")
SQL_DRIVER = os.environ.get("SQL_DRIVER", "ODBC Driver 17 for SQL Server")
SQL_TRUSTED_CONNECTION = os.environ.get("SQL_TRUSTED_CONNECTION", "yes").lower() in ("1", "true", "yes")
DB_POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "10"))
DB_POOL_OVERFLOW = int(os.environ.get("DB_POOL_OVERFLOW", "5"))

_pool: Optional[ConnectionPool] = None


class DictCursor:
    def __init__(self, cursor):
        self.cursor = cursor
        self.last_insert_table = None

    def execute(self, sql, params=None):
        self.last_insert_table = self._get_insert_table(sql)
        sql, params = self._convert_pagination(sql, params or [])
        sql = self._convert_sql(sql)
        self.cursor.execute(sql, params)
        return self

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def fetchall(self):
        return [self._row_to_dict(row) for row in self.cursor.fetchall()]

    def close(self):
        self.cursor.close()

    @property
    def rowcount(self):
        return self.cursor.rowcount

    @property
    def lastrowid(self):
        if not self.last_insert_table:
            return None
        self.cursor.execute(f"SELECT CAST(IDENT_CURRENT('{self.last_insert_table}') AS int) AS last_id")
        row = self.cursor.fetchone()
        return row[0] if row else None

    def _row_to_dict(self, row):
        columns = [column[0] for column in self.cursor.description]
        return dict(zip(columns, row))

    def _convert_sql(self, sql):
        sql = sql.replace("%s", "?")
        sql = re.sub(r"\bFROM\s+user\b", "FROM [user]", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bJOIN\s+user\b", "JOIN [user]", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bUPDATE\s+user\b", "UPDATE [user]", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bINSERT\s+INTO\s+user\b", "INSERT INTO [user]", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bDELETE\s+FROM\s+user\b", "DELETE FROM [user]", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bDATE\(([^)]+)\)", r"CAST(\1 AS date)", sql, flags=re.IGNORECASE)
        sql = re.sub(
            r"(SELECT\s+COUNT\(\*\)\s+AS\s+total\s+FROM\s+\(.+?)\s+ORDER\s+BY\s+.+?(\)\s+as\s+count_table)",
            r"\1\2",
            sql,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return sql

    def _get_insert_table(self, sql):
        match = re.search(r"\bINSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)\b", sql, flags=re.IGNORECASE)
        if not match:
            return None
        table_name = match.group(1).lower()
        if table_name == "user":
            return "dbo.[user]"
        return f"dbo.{table_name}"

    def _convert_pagination(self, sql, params):
        if re.search(r"\s+LIMIT\s+%s\s+OFFSET\s+%s", sql, flags=re.IGNORECASE):
            sql = re.sub(
                r"\s+LIMIT\s+%s\s+OFFSET\s+%s",
                " OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
                sql,
                flags=re.IGNORECASE,
            )
            if len(params) >= 2:
                params = list(params)
                params[-2], params[-1] = params[-1], params[-2]
        return sql, params


class Connection:
    def __init__(self, connection):
        self.connection = connection

    def cursor(self, *args, **kwargs):
        return DictCursor(self.connection.cursor())

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


class PooledConnection(Connection):
    """归还连接池而非销毁物理连接。"""

    def __init__(self, raw_connection, pool: ConnectionPool):
        super().__init__(raw_connection)
        self._pool = pool
        self._discarded = False

    def close(self):
        if self._discarded:
            return
        self._pool.release(self.connection, discard=self._discarded)

    def mark_discard(self):
        self._discarded = True


def _resolve_password() -> str:
    if not SQL_PASSWORD:
        return ""
    if SQL_PASSWORD_ENCRYPTED or SQL_PASSWORD.startswith("enc:"):
        from ops.crypto import resolve_db_password

        return resolve_db_password(SQL_PASSWORD, encrypted=True)
    return SQL_PASSWORD


def build_connection_string(*, database: str | None = None) -> str:
    db = database or SQL_DATABASE
    if SQL_TRUSTED_CONNECTION:
        return (
            f"DRIVER={{{SQL_DRIVER}}};"
            f"SERVER={SQL_SERVER};"
            f"DATABASE={db};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
        )
    pwd = _resolve_password()
    return (
        f"DRIVER={{{SQL_DRIVER}}};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={db};"
        f"UID={SQL_USERNAME};"
        f"PWD={pwd};"
        "TrustServerCertificate=yes;"
    )


def _create_raw_connection():
    return pyodbc.connect(build_connection_string())


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            _create_raw_connection,
            pool_size=DB_POOL_SIZE,
            overflow=DB_POOL_OVERFLOW,
        )
    return _pool


def get_connection():
    if os.environ.get("DB_POOL_ENABLED", "yes").lower() in ("0", "false", "no"):
        return Connection(pyodbc.connect(build_connection_string()))
    pool = _get_pool()
    raw = pool.acquire()
    return PooledConnection(raw, pool)


def pool_stats() -> dict:
    if _pool is None:
        return {"enabled": False}
    return {"enabled": True, **_pool.stats}


def ping_database() -> bool:
    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 AS ok")
        row = cursor.fetchone()
        return bool(row and row.get("ok") == 1)
    except Exception:
        return False
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()
