"""
从 .bak 文件恢复 SQL Server 数据库（会覆盖现有库，慎用）。

用法:
  python scripts/restore_database.py --file backups/movie_system_20260101_120000.bak
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "movie_system_api"))

from ops.backup import restore_full_database


def main():
    parser = argparse.ArgumentParser(description="电影推荐系统 - 数据库恢复")
    parser.add_argument("--file", required=True, help=".bak 备份文件路径")
    parser.add_argument("--server", default=os.environ.get("SQL_SERVER", "localhost"))
    parser.add_argument("--database", default=os.environ.get("SQL_DATABASE", "movie_system"))
    parser.add_argument("--driver", default=os.environ.get("SQL_DRIVER", "ODBC Driver 17 for SQL Server"))
    args = parser.parse_args()

    bak = Path(args.file)
    if not bak.exists():
        raise SystemExit(f"备份文件不存在: {bak}")

    confirm = input(f"确认从 {bak} 恢复数据库 [{args.database}]？输入 YES 继续: ")
    if confirm.strip() != "YES":
        print("已取消")
        return

    trusted = os.environ.get("SQL_TRUSTED_CONNECTION", "yes").lower() in ("1", "true", "yes")
    restore_full_database(
        args.server,
        args.database,
        bak,
        driver=args.driver,
        trusted=trusted,
        username=os.environ.get("SQL_USERNAME", ""),
        password=os.environ.get("SQL_PASSWORD", ""),
        replace=True,
    )
    print("恢复完成")


if __name__ == "__main__":
    main()
