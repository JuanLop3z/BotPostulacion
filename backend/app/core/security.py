import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import get_settings


def encrypt_document(content: bytes) -> bytes:
    key = base64.urlsafe_b64encode(hashlib.sha256(get_settings().secret_key.encode()).digest())
    return Fernet(key).encrypt(content)


def decrypt_document(content: bytes) -> bytes:
    key = base64.urlsafe_b64encode(hashlib.sha256(get_settings().secret_key.encode()).digest())
    return Fernet(key).decrypt(content)
