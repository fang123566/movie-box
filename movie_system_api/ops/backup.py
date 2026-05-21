"""
SQL Server 容灾备份：全库 .bak + 核心业务表 JSON 导出。
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Union

import pyodbc

TABLES_FOR_JSON = ("genre", "movie", "user", "rating", "history", "movie_genre")


class SafeEncoder(json.JSONEncoder):
    """处理 SQL Server pyodbc 行中可能出现的所有非标准 JSON 类型。"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if hasattr(obj, "isoformat"):          # datetime / date / time
            return obj.isoformat()
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        if isinstance(obj, bool):              # bool 必须在 int 之前
            return obj
        return super().default(obj)


def _connection_string(
    server: str,
    database: str,
    driver: str,
    trusted: bool,
    username: str = "",
    password: str = "",
) -> str:
    if trusted:
        return (
            f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
            "Trusted_Connection=yes;TrustServerCertificate=yes;"
        )
    return (
        f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
        f"UID={username};PWD={password};TrustServerCertificate=yes;"
    )


def backup_full_database(
    server: str,
    database: str,
    backup_dir: Union[str, Path],
    *,
    driver: str = "ODBC Driver 17 for SQL Server",
    trusted: bool = True,
    username: str = "",
    password: str = "",
    use_compression: bool = True,
) -> Path:
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_path = backup_dir / f"{database}_{stamp}.bak"

    compression = ", COMPRESSION" if use_compression else ""
    sql = f"BACKUP DATABASE [{database}] TO DISK = ? WITH INIT, CHECKSUM{compression}"

    conn = pyodbc.connect(
        _connection_string(server, "master", driver, trusted, username, password),
        autocommit=True,
    )
    try:
        conn.cursor().execute(sql, (str(bak_path.resolve()),))
    finally:
        conn.close()

    return bak_path


def export_tables_json(
    server: str,
    database: str,
    backup_dir: Union[str, Path],
    *,
    driver: str = "ODBC Driver 17 for SQL Server",
    trusted: bool = True,
    username: str = "",
    password: str = "",
) -> Path:
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = backup_dir / f"{database}_tables_{stamp}.json"

    conn = pyodbc.connect(
        _connection_string(server, database, driver, trusted, username, password)
    )
    cursor = conn.cursor()
    payload = {"database": database, "exported_at": stamp, "tables": {}}

    try:
        for table in TABLES_FOR_JSON:
            name = f"[{table}]" if table == "user" else table
            cursor.execute(f"SELECT * FROM dbo.{name}")
            columns = [c[0] for c in cursor.description]
            payload["tables"][table] = [
                dict(zip(columns, row)) for row in cursor.fetchall()
            ]
    finally:
        cursor.close()
        conn.close()

    json_path.write_text(
        json.dumps(payload, cls=SafeEncoder, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return json_path


def restore_full_database(
    server: str,
    database: str,
    bak_path: Union[str, Path],
    *,
    driver: str = "ODBC Driver 17 for SQL Server",
    trusted: bool = True,
    username: str = "",
    password: str = "",
    replace: bool = True,
) -> None:
    bak_path = Path(bak_path).resolve()
    if not bak_path.exists():
        raise FileNotFoundError(bak_path)

    replace_clause = ", REPLACE" if replace else ""
    sql = f"""
    ALTER DATABASE [{database}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    RESTORE DATABASE [{database}] FROM DISK = ? WITH RECOVERY{replace_clause};
    ALTER DATABASE [{database}] SET MULTI_USER;
    """

    conn = pyodbc.connect(
        _connection_string(server, "master", driver, trusted, username, password),
        autocommit=True,
    )
    try:
        conn.cursor().execute(sql, (str(bak_path),))
    finally:
        conn.close()


def run_scheduled_backup(
    server: str,
    database: str,
    backup_dir: Union[str, Path],
    **kwargs,
) -> dict:
    """执行全库 + JSON 双轨备份，返回路径信息。"""
    bak = backup_full_database(server, database, backup_dir, **kwargs)
    js = export_tables_json(server, database, backup_dir, **kwargs)
    _prune_old_backups(Path(backup_dir), keep=int(os.environ.get("BACKUP_KEEP_COUNT", "7")))
    return {"bak_file": str(bak), "json_file": str(js)}


def _prune_old_backups(backup_dir: Path, keep: int = 7):
    files = sorted(backup_dir.glob("*.bak"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[keep:]:
        old.unlink(missing_ok=True)
    json_files = sorted(backup_dir.glob("*_tables_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in json_files[keep:]:
        old.unlink(missing_ok=True)


def try_sqlcmd_backup(server: str, database: str, bak_path: Path) -> bool:
    """若系统安装了 sqlcmd，可作为备用备份通道。"""
    sqlcmd = os.environ.get("SQLCMD_PATH", "sqlcmd")
    query = (
        f"BACKUP DATABASE [{database}] TO DISK = N'{bak_path}' "
        "WITH INIT, CHECKSUM, COMPRESSION"
    )
    try:
        subprocess.run(
            [sqlcmd, "-S", server, "-Q", query, "-b"],
            check=True,
            capture_output=True,
            timeout=600,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
