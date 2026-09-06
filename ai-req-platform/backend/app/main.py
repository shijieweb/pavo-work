"""FastAPI入口。

仅负责挂载中间件、路由和启动配置，零业务逻辑。
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import settings as settings_router
from app.api.v1 import projects as projects_router
from app.api.v1 import ai as ai_router
from app.db.session import init_db

# 前端构建产物路径
FRONTEND_DIST = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    # 启动时初始化数据库
    await init_db()
    yield
    # 关闭时清理资源（如有需要）


app = FastAPI(
    title="AI Requirement Platform",
    description="AI驱动需求管理与研发协作平台",
    version="1.0.0",
    lifespan=lifespan,
)

# 挂载前端静态文件
app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


@app.get("/")
async def root():
    """返回前端index.html。"""
    return FileResponse(str(FRONTEND_DIST / "index.html"))


@app.get("/health")
async def health() -> dict[str, str]:
    """健康检查端点。"""
    return {"status": "ok"}

# 挂载路由
app.include_router(settings_router.router, prefix="/api/v1")
app.include_router(projects_router.router, prefix="/api/v1")
app.include_router(ai_router.router, prefix="/api/v1")
