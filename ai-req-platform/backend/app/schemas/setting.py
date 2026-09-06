"""设置相关Schema。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SettingResponse(BaseModel):
    """全局设置响应。"""

    id: int
    ai_api_url: Optional[str] = None
    ai_model_name: Optional[str] = None
    token: Optional[str] = None
    has_api_key: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AIModelUpdate(BaseModel):
    """AI模型配置更新。"""

    ai_api_url: str = Field(..., min_length=1, max_length=500)
    ai_api_key: str = Field(..., min_length=1)
    ai_model_name: str = Field(default="gpt-4o-mini", max_length=100)
    token: Optional[str] = Field(default=None, max_length=255)


class AIModelTest(BaseModel):
    """AI连接测试结果。"""

    success: bool
    message: str
    model_used: Optional[str] = None


class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: str
