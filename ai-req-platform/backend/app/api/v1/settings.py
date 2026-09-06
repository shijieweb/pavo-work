"""设置相关API路由。"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.setting import (
    SettingResponse,
    AIModelUpdate,
    AIModelTest,
    HealthResponse,
)
from app.services.setting_service import SettingService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> dict[str, str]:
    """健康检查。

    Returns:
        健康状态
    """
    return {"status": "ok"}


@router.get("", response_model=SettingResponse)
async def get_setting(
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """获取全局设置。

    Args:
        db: 数据库会话

    Returns:
        全局设置
    """
    service = SettingService(db)
    setting = await service.get_setting()

    if setting is None:
        return SettingResponse(
            id=0,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    return SettingResponse(
        id=setting.id,
        ai_api_url=setting.ai_api_url,
        ai_model_name=setting.ai_model_name,
        token=setting.token,
        has_api_key=setting.ai_api_key is not None,
        created_at=setting.created_at,
        updated_at=setting.updated_at,
    )


@router.put("/ai-model", response_model=SettingResponse)
async def update_ai_model(
    data: AIModelUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """更新AI配置。

    Args:
        data: AI配置更新数据
        db: 数据库会话

    Returns:
        更新后的设置
    """
    service = SettingService(db)
    setting = await service.update_ai_config(
        ai_api_url=data.ai_api_url,
        ai_api_key=data.ai_api_key,
        ai_model_name=data.ai_model_name,
        token=data.token,
    )

    return SettingResponse(
        id=setting.id,
        ai_api_url=setting.ai_api_url,
        ai_model_name=setting.ai_model_name,
        token=setting.token,
        has_api_key=True,
        created_at=setting.created_at,
        updated_at=setting.updated_at,
    )


@router.post("/ai-model/test", response_model=AIModelTest)
async def test_ai_connection(
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """测试AI连接。

    Args:
        db: 数据库会话

    Returns:
        测试结果
    """
    service = SettingService(db)
    result = await service.test_ai_connection()

    return AIModelTest(**result)
