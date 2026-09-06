"""认证模块。

提供JWT令牌生成和验证功能。
"""

from datetime import datetime, timedelta
from typing import Any, Optional

from jose import JWTError, jwt

from app.core.config import settings


def create_access_token(subject: Any, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌。

    Args:
        subject: 令牌主题（用户ID或其他标识）
        expires_delta: 过期时间增量，默认为配置值

    Returns:
        JWT字符串
    """
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload = {"sub": str(subject), "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(subject: Any) -> str:
    """创建刷新令牌。

    Args:
        subject: 令牌主题

    Returns:
        JWT字符串
    """
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    payload = {"sub": str(subject), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def verify_token(token: str, token_type: str = "access") -> Optional[dict[str, Any]]:
    """验证令牌。

    Args:
        token: JWT字符串
        token_type: 令牌类型（access/refresh）

    Returns:
        解码后的payload，验证失败返回None
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("type") != token_type:
            return None
        return payload
    except JWTError:
        return None
