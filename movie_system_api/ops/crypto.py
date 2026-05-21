"""
密码与敏感配置加解密。

- 用户密码：PBKDF2-SHA256（werkzeug），兼容旧版 SHA256 十六进制哈希
- 配置/密钥：Fernet 对称加密（环境变量 APP_ENCRYPTION_KEY）
"""
from __future__ import annotations

from typing import Optional
import hashlib
import os

from werkzeug.security import check_password_hash, generate_password_hash

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover
    Fernet = None
    InvalidToken = Exception

PBKDF2_METHOD = "pbkdf2:sha256"
LEGACY_SHA256_LEN = 64


def hash_password(password: str) -> str:
    return generate_password_hash(password, method=PBKDF2_METHOD, salt_length=16)


def verify_password(password: str, stored_hash: Optional[str]) -> bool:
    if not stored_hash or not password:
        return False
    stored_hash = stored_hash.strip()
    if stored_hash.startswith("pbkdf2:") or stored_hash.startswith("scrypt:"):
        return check_password_hash(stored_hash, password)
    if len(stored_hash) == LEGACY_SHA256_LEN and all(c in "0123456789abcdef" for c in stored_hash.lower()):
        return stored_hash == hashlib.sha256(password.encode("utf-8")).hexdigest()
    return check_password_hash(stored_hash, password)


def _get_fernet() -> Optional[Fernet]:
    if Fernet is None:
        return None
    key = os.environ.get("APP_ENCRYPTION_KEY", "").strip()
    if not key:
        return None
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        return None


def generate_encryption_key() -> str:
    if Fernet is None:
        raise RuntimeError("请先安装 cryptography: pip install cryptography")
    return Fernet.generate_key().decode()


def encrypt_text(plain_text: str) -> str:
    f = _get_fernet()
    if not f:
        raise RuntimeError("未设置 APP_ENCRYPTION_KEY 或未安装 cryptography")
    return f.encrypt(plain_text.encode("utf-8")).decode()


def decrypt_text(cipher_text: str) -> str:
    f = _get_fernet()
    if not f:
        raise RuntimeError("未设置 APP_ENCRYPTION_KEY 或未安装 cryptography")
    try:
        return f.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("解密失败，密文或密钥不正确") from exc


def encrypt_connection_password(plain_password: str) -> str:
    """将数据库明文密码加密后写入配置（可选）。"""
    return encrypt_text(plain_password)


def resolve_db_password(configured: str, *, encrypted: bool = False) -> str:
    if not configured:
        return ""
    if encrypted or configured.startswith("enc:"):
        payload = configured[4:] if configured.startswith("enc:") else configured
        return decrypt_text(payload)
    return configured
