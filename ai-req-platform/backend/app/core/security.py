"""加密工具模块。

提供Fernet对称加密功能，用于存储敏感配置。
"""

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class EncryptionService:
    """Fernet加密服务。"""

    _fernet: Fernet | None = None

    @classmethod
    def get_fernet(cls) -> Fernet:
        """获取或创建Fernet实例。"""
        if cls._fernet is None:
            key = settings.encryption_key
            cls._fernet = Fernet(key.encode())
        return cls._fernet

    @classmethod
    def encrypt(cls, value: str) -> bytes:
        """加密字符串。

        Args:
            value: 原始字符串

        Returns:
            加密后的字节串
        """
        return cls.get_fernet().encrypt(value.encode())

    @classmethod
    def decrypt(cls, encrypted: bytes) -> str:
        """解密字节串。

        Args:
            encrypted: 加密后的字节串

        Returns:
            解密后的字符串

        Raises:
            InvalidToken: 解密失败
        """
        return cls.get_fernet().decrypt(encrypted).decode()


def encrypt_api_key(key: str) -> bytes:
    """加密API Key。"""
    return EncryptionService.encrypt(key)


def decrypt_api_key(encrypted: bytes) -> str:
    """解密API Key。"""
    return EncryptionService.decrypt(encrypted)
