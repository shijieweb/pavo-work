"""AI相关Schema。"""

from typing import Optional

from pydantic import BaseModel, Field


class ProjectOptimizeRequest(BaseModel):
    """项目优化请求。"""

    project_id: int = Field(..., gt=0)


class ProjectOptimizeResponse(BaseModel):
    """项目优化响应。"""

    success: bool
    message: str
    optimized_data: Optional[dict] = None


class ProjectGenerateRequest(BaseModel):
    """AI生成项目简介请求。"""

    project_name: str = Field(..., min_length=2, max_length=50)
    user_input: Optional[str] = Field(None, max_length=200)


class ProjectGenerateResponse(BaseModel):
    """AI生成项目简介响应。"""

    success: bool
    message: str
    generated_description: Optional[str] = None
    suggestion: Optional[str] = None

