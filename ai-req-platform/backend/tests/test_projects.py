"""测试项目相关API。"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.db.base import Base
from app.db.session import get_db


@pytest.fixture
async def client():
    """为每个测试创建独立的数据库和客户端。"""
    # 为每个测试创建独立引擎
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    
    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as c:
        yield c
    
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """测试健康检查端点。"""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient):
    """测试创建项目。"""
    response = await client.post("/api/v1/projects", json={
        "name": "测试项目",
        "description": "这是一个测试项目",
        "target_users": ["用户A", "用户B"],
        "core_functions": ["功能1", "功能2"],
        "key_scenarios": ["场景1"],
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "测试项目"
    assert data["status"] == "draft"
    assert len(data["target_users"]) == 2


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient):
    """测试列表项目。"""
    # 先创建几个项目
    for i in range(3):
        await client.post("/api/v1/projects", json={
            "name": f"项目{i+1}",
        })

    # 测试列表
    response = await client.get("/api/v1/projects")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


@pytest.mark.asyncio
async def test_get_project(client: AsyncClient):
    """测试获取项目详情。"""
    # 创建项目
    create_response = await client.post("/api/v1/projects", json={
        "name": "详情测试项目",
    })
    project_id = create_response.json()["id"]

    # 获取详情
    response = await client.get(f"/api/v1/projects/{project_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "详情测试项目"


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient):
    """测试更新项目。"""
    # 创建项目
    create_response = await client.post("/api/v1/projects", json={
        "name": "更新测试项目",
    })
    project_id = create_response.json()["id"]

    # 更新项目
    response = await client.put(f"/api/v1/projects/{project_id}", json={
        "name": "更新后的名称",
        "status": "in_progress",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "更新后的名称"
    assert data["status"] == "in_progress"


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient):
    """测试删除项目。"""
    # 创建项目
    create_response = await client.post("/api/v1/projects", json={
        "name": "删除测试项目",
    })
    project_id = create_response.json()["id"]

    # 删除项目
    response = await client.delete(f"/api/v1/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["success"] is True

    # 验证已删除
    get_response = await client.get(f"/api/v1/projects/{project_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_search_projects(client: AsyncClient):
    """测试搜索项目。"""
    # 创建项目
    await client.post("/api/v1/projects", json={"name": "任务管理系统"})
    await client.post("/api/v1/projects", json={"name": "数据分析平台"})

    # 搜索
    response = await client.get("/api/v1/projects?search=任务")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "任务管理系统"


@pytest.mark.asyncio
async def test_filter_by_status(client: AsyncClient):
    """测试按状态过滤。"""
    # 创建不同状态的项目
    await client.post("/api/v1/projects", json={"name": "草稿项目"})
    response1 = await client.post("/api/v1/projects", json={"name": "进行中项目"})
    project_id = response1.json()["id"]
    await client.put(f"/api/v1/projects/{project_id}", json={"status": "in_progress"})

    # 过滤
    response = await client.get("/api/v1/projects?status=in_progress")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "in_progress"
