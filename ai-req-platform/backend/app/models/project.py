"""项目模型。"""

import json
from datetime import datetime
from typing import Any

from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Project(Base, TimestampMixin):
    """项目表。"""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    target_users: Mapped[str] = mapped_column(Text, nullable=True)  # JSON字符串
    core_functions: Mapped[str] = mapped_column(Text, nullable=True)  # JSON字符串
    key_scenarios: Mapped[str] = mapped_column(Text, nullable=True)  # JSON字符串
    architecture_snapshot: Mapped[str] = mapped_column(Text, nullable=True)  # JSON字符串
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def get_target_users(self) -> list[str]:
        """获取目标用户列表。"""
        if not self.target_users:
            return []
        return json.loads(self.target_users)

    def set_target_users(self, users: list[str]) -> None:
        """设置目标用户列表。"""
        self.target_users = json.dumps(users, ensure_ascii=False)

    def get_core_functions(self) -> list[str]:
        """获取核心功能列表。"""
        if not self.core_functions:
            return []
        return json.loads(self.core_functions)

    def set_core_functions(self, functions: list[str]) -> None:
        """设置核心功能列表。"""
        self.core_functions = json.dumps(functions, ensure_ascii=False)

    def get_key_scenarios(self) -> list[str]:
        """获取关键场景列表。"""
        if not self.key_scenarios:
            return []
        return json.loads(self.key_scenarios)

    def set_key_scenarios(self, scenarios: list[str]) -> None:
        """设置关键场景列表。"""
        self.key_scenarios = json.dumps(scenarios, ensure_ascii=False)

    def get_architecture_snapshot(self) -> dict[str, Any]:
        """获取架构快照。"""
        if not self.architecture_snapshot:
            return {}
        return json.loads(self.architecture_snapshot)

    def set_architecture_snapshot(self, snapshot: dict[str, Any]) -> None:
        """设置架构快照。"""
        self.architecture_snapshot = json.dumps(snapshot, ensure_ascii=False)
