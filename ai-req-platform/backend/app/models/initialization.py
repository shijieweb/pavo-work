"""项目初始化模型。"""

from sqlalchemy import ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ProjectInitialization(Base, TimestampMixin):
    """项目初始化表。"""

    __tablename__ = "project_initialization"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    file_tree: Mapped[dict] = mapped_column(JSON, nullable=True)
    readme_content: Mapped[str] = mapped_column(Text, nullable=True)
