"""后端配置文件。

所有配置通过环境变量加载，禁止硬编码敏感值。
"""

from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用设置。"""

    # 应用基础配置
    app_name: str = "AI Requirement Platform"
    debug: bool = False

    # 数据库配置
    database_url: str = "sqlite+aiosqlite:///./ai_req_platform.db"

    # JWT认证配置
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # AI配置（加密存储）
    ai_api_url: Optional[str] = None
    ai_api_key: Optional[str] = None
    ai_model_name: str = "gpt-4o-mini"
    ai_token: Optional[str] = None

    # 认证Token
    auth_token: str = "dev-token-change-in-production"

    # 加密密钥（Fernet）
    encryption_key: str = "YourFernetKeyHere1234567890ABCD="

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
