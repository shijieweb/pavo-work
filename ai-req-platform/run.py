"""启动脚本 - 同时启动前后端开发服务器。"""

import os
import subprocess
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent

# 后端端口
BACKEND_PORT = 8800


def start_frontend():
    """启动前端开发服务器。"""
    frontend_dir = PROJECT_ROOT / "frontend"
    os.chdir(frontend_dir)

    print("Starting frontend dev server...")
    subprocess.run([sys.executable, "-m", "npm", "run", "dev"], check=True)


def start_backend():
    """启动后端服务。"""
    backend_dir = PROJECT_ROOT / "backend"
    os.chdir(backend_dir)

    print("Starting backend server...")
    cmd = [
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", "127.0.0.1",
        "--port", str(BACKEND_PORT),
        "--reload",
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    print("=" * 60)
    print("AI驱动需求管理与研发协作平台")
    print("=" * 60)
    print()

    print(f"访问地址: http://127.0.0.1:{BACKEND_PORT}")
    print(f"API文档:  http://127.0.0.1:{BACKEND_PORT}/docs")
    print()

    # 先初始化数据库
    print("Initializing database...")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                   cwd=PROJECT_ROOT / "backend", check=True)
    print("Database initialized.")
    print()

    # 启动后端（阻塞）
    start_backend()
