"""
数据库容灾备份：SQL Server 全库 .bak + 业务表 JSON。

用法:
  python scripts/backup_database.py
  python scripts/backup_database.py --dir backups
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "movie_system_api"))

from ops.backup import run_scheduled_backup


def main():
    parser = argparse.ArgumentParser(description="电影推荐系统 - 数据库备份")
    parser.add_argument("--server", default=os.environ.get("SQL_SERVER", "localhost"))
    parser.add_argument("--database", default=os.environ.get("SQL_DATABASE", "movie_system"))
    parser.add_argument("--dir", default=os.environ.get("BACKUP_DIR", str(ROOT / "backups")))
    parser.add_argument("--driver", default=os.environ.get("SQL_DRIVER", "ODBC Driver 17 for SQL Server"))
    args = parser.parse_args()

    trusted = os.environ.get("SQL_TRUSTED_CONNECTION", "yes").lower() in ("1", "true", "yes")
    result = run_scheduled_backup(
        args.server,
        args.database,
        args.dir,
        driver=args.driver,
        trusted=trusted,
        username=os.environ.get("SQL_USERNAME", ""),
        password=os.environ.get("SQL_PASSWORD", ""),
    )
    print("备份完成:")
    print("  全库:", result["bak_file"])
    print("  JSON:", result["json_file"])


if __name__ == "__main__":
    main()
