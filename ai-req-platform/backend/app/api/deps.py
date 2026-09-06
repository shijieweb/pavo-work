"""API依赖注入。"""

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db

security = HTTPBearer(auto_error=False)


async def get_db_session(db: AsyncSession = Depends(get_db)) -> AsyncSession:
    """获取数据库会话。

    Args:
        db: 数据库会话

    Returns:
        数据库会话
    """
    return db


async def verify_token(request: Request) -> None:
    """验证认证令牌。

    简单实现：检查Authorization头中的token是否与配置的AUTH_TOKEN匹配。

    Args:
        request: HTTP请求对象

    Raises:
        HTTPException: 认证失败时抛出
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid auth scheme")

    if token != settings.auth_token:
        raise HTTPException(status_code=401, detail="Invalid token")
