"""AI相关API路由。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.ai import (
    ProjectOptimizeRequest,
    ProjectOptimizeResponse,
    ProjectGenerateRequest,
    ProjectGenerateResponse,
)
from app.services.ai_service import AIService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/optimize-project", response_model=ProjectOptimizeResponse)
async def optimize_project(
    data: ProjectOptimizeRequest,
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """AI优化项目描述。

    Args:
        data: 项目优化请求
        db: 数据库会话

    Returns:
        优化结果
    """
    service = AIService(db)
    result = await service.optimize_project_description(data.project_id)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return ProjectOptimizeResponse(
        success=result["success"],
        message=result["message"],
        optimized_data=result.get("optimized_data"),
    )


@router.post("/generate-description", response_model=ProjectGenerateResponse)
async def generate_description(
    data: ProjectGenerateRequest,
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """根据项目名称生成项目简介。

    Args:
        data: 项目名称和简要描述
        db: 数据库会话

    Returns:
        生成的项目简介
    """
    service = AIService(db)
    result = await service.generate_project_description(
        project_name=data.project_name,
        user_input=data.user_input or "",
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return ProjectGenerateResponse(
        success=result["success"],
        message=result["message"],
        generated_description=result.get("generated_description", ""),
        suggestion=result.get("suggestion", ""),
    )
