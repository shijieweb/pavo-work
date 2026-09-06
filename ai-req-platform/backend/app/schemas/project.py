"""项目相关Schema。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """创建项目请求。"""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None)
    target_users: Optional[list[str]] = None
    core_functions: Optional[list[str]] = None
    key_scenarios: Optional[list[str]] = None


class ProjectUpdate(BaseModel):
    """更新项目请求。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    target_users: Optional[list[str]] = None
    core_functions: Optional[list[str]] = None
    key_scenarios: Optional[list[str]] = None
    status: Optional[str] = Field(default=None, pattern=r"^(draft|in_progress|completed|archived)$")


class ProjectResponse(BaseModel):
    """项目响应。"""

    id: int
    name: str
    description: Optional[str] = None
    target_users: list[str]
    core_functions: list[str]
    key_scenarios: list[str]
    architecture_snapshot: dict
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    """项目列表响应。"""

    total: int
    items: list[ProjectResponse]


class ProjectDeleteResponse(BaseModel):
    """删除项目响应。"""

    success: bool
    message: str
