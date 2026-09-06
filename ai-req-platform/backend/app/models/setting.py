"""全局设置模型。"""

from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class GlobalSetting(Base, TimestampMixin):
    """全局设置表。"""

    __tablename__ = "global_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ai_api_url: Mapped[str] = mapped_column(String(500), nullable=True)
    ai_api_key: Mapped[str] = mapped_column(Text, nullable=True)  # 加密存储
    ai_model_name: Mapped[str] = mapped_column(String(100), nullable=True, default="gpt-4o-mini")
    token: Mapped[str] = mapped_column(String(255), nullable=True)
