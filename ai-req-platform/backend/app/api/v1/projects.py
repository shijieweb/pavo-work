"""项目相关API路由。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
    ProjectDeleteResponse,
)
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """创建项目。

    Args:
        data: 项目创建数据
        db: 数据库会话

    Returns:
        创建的项目
    """
    service = ProjectService(db)
    project = await service.create_project(
        name=data.name,
        description=data.description,
        target_users=data.target_users,
        core_functions=data.core_functions,
        key_scenarios=data.key_scenarios,
    )

    return _project_to_response(project)


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    search: str = Query(default=None),
    status: str = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """列出项目。

    Args:
        search: 搜索关键词
        status: 状态过滤
        page: 页码
        limit: 每页数量
        db: 数据库会话

    Returns:
        项目列表
    """
    service = ProjectService(db)
    projects, total = await service.list_projects(
        search=search,
        status=status,
        page=page,
        limit=limit,
    )

    return ProjectListResponse(
        total=total,
        items=[_project_to_response(p) for p in projects],
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """获取项目详情。

    Args:
        project_id: 项目ID
        db: 数据库会话

    Returns:
        项目详情
    """
    service = ProjectService(db)
    project = await service.get_project(project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return _project_to_response(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """更新项目。

    Args:
        project_id: 项目ID
        data: 项目更新数据
        db: 数据库会话

    Returns:
        更新后的项目
    """
    service = ProjectService(db)
    project = await service.update_project(
        project_id=project_id,
        name=data.name,
        description=data.description,
        target_users=data.target_users,
        core_functions=data.core_functions,
        key_scenarios=data.key_scenarios,
        status=data.status,
    )

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return _project_to_response(project)


@router.delete("/{project_id}", response_model=ProjectDeleteResponse)
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """软删除项目。

    Args:
        project_id: 项目ID
        db: 数据库会话

    Returns:
        删除结果
    """
    service = ProjectService(db)
    success = await service.delete_project(project_id)

    if not success:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectDeleteResponse(success=True, message="Project deleted successfully")


def _project_to_response(project: Any) -> ProjectResponse:
    """将项目模型转换为响应。"""
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        target_users=project.get_target_users(),
        core_functions=project.get_core_functions(),
        key_scenarios=project.get_key_scenarios(),
        architecture_snapshot=project.get_architecture_snapshot(),
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )
