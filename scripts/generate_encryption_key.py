"""生成 APP_ENCRYPTION_KEY（用于加密数据库密码等敏感配置）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "movie_system_api"))

from ops.crypto import generate_encryption_key

if __name__ == "__main__":
    key = generate_encryption_key()
    print("将以下内容写入 .env 或系统环境变量:")
    print(f"APP_ENCRYPTION_KEY={key}")
