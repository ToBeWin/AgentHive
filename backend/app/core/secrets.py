import base64
from hashlib import sha256

from cryptography.fernet import Fernet

from app.core.config import settings


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(sha256(settings.secret_key.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_secret(encrypted_secret: str) -> str:
    return _fernet().decrypt(encrypted_secret.encode("utf-8")).decode("utf-8")


def mask_secret(secret: str) -> str:
    if len(secret) <= 8:
        return "****"
    return f"{secret[:4]}...{secret[-4:]}"
