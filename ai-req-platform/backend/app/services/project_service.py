"""项目服务。"""

from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project


class ProjectService:
    """项目服务。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_project(
        self,
        name: str,
        description: Optional[str] = None,
        target_users: Optional[list[str]] = None,
        core_functions: Optional[list[str]] = None,
        key_scenarios: Optional[list[str]] = None,
    ) -> Project:
        """创建项目。

        Args:
            name: 项目名称
            description: 项目描述
            target_users: 目标用户列表
            core_functions: 核心功能列表
            key_scenarios: 关键场景列表

        Returns:
            创建的项目对象
        """
        project = Project(
            name=name,
            description=description,
            status="draft",
        )
        if target_users:
            project.set_target_users(target_users)
        if core_functions:
            project.set_core_functions(core_functions)
        if key_scenarios:
            project.set_key_scenarios(key_scenarios)

        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def list_projects(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Project], int]:
        """列出项目。

        Args:
            search: 搜索关键词
            status: 状态过滤
            page: 页码
            limit: 每页数量

        Returns:
            (项目列表, 总数)
        """
        query = select(Project).where(Project.deleted_at.is_(None))

        if search:
            query = query.where(Project.name.contains(search))
        if status:
            query = query.where(Project.status == status)

        # 获取总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # 分页查询
        query = query.order_by(Project.created_at.desc()).offset((page - 1) * limit).limit(limit)
        result = await self.db.execute(query)
        projects = result.scalars().all()

        return list(projects), total

    async def get_project(self, project_id: int) -> Optional[Project]:
        """获取项目详情。

        Args:
            project_id: 项目ID

        Returns:
            项目对象或None
        """
        result = await self.db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def update_project(
        self,
        project_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        target_users: Optional[list[str]] = None,
        core_functions: Optional[list[str]] = None,
        key_scenarios: Optional[list[str]] = None,
        status: Optional[str] = None,
    ) -> Optional[Project]:
        """更新项目。

        Args:
            project_id: 项目ID
            name: 项目名称
            description: 项目描述
            target_users: 目标用户列表
            core_functions: 核心功能列表
            key_scenarios: 关键场景列表
            status: 状态

        Returns:
            更新后的项目对象或None
        """
        project = await self.get_project(project_id)
        if project is None:
            return None

        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        if target_users is not None:
            project.set_target_users(target_users)
        if core_functions is not None:
            project.set_core_functions(core_functions)
        if key_scenarios is not None:
            project.set_key_scenarios(key_scenarios)
        if status is not None:
            project.status = status

        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def delete_project(self, project_id: int) -> bool:
        """软删除项目。

        Args:
            project_id: 项目ID

        Returns:
            是否删除成功
        """
        project = await self.get_project(project_id)
        if project is None:
            return False

        project.deleted_at = func.now()
        await self.db.commit()
        return True
