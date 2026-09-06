# AI驱动需求管理与研发协作平台 - 启动指南

## 快速启动

### 开发模式（推荐）

```bash
# 方式1：使用启动脚本
python run.py

# 方式2：分别启动前后端
# 终端1 - 后端
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8800 --reload

# 终端2 - 前端
cd frontend
npm run dev
```

### 生产模式

```bash
# 构建前端
cd frontend && npm run build

# 复制静态文件
cp -r dist/* ../backend/app/static/

# 启动后端
cd ../backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8800
```

## 访问地址

- **主页**: <http://127.0.0.1:8800>
- **API文档**: <http://127.0.0.1:8800/docs>
- **健康检查**: <http://127.0.0.1:8800/health>

## 技术栈

| 层次  | 技术                                          |
| --- | ------------------------------------------- |
| 前端  | React 18 + TypeScript + Vite + Tailwind CSS |
| 图标  | lucide-react 0.469.0（P0锁定）                  |
| 后端  | FastAPI + SQLAlchemy 2.0                    |
| 数据库 | SQLite（本地文件）                                |

## MVP功能清单

- [x] 项目CRUD
- [x] AI辅助优化项目描述
- [x] AI模型配置
- [x] 项目搜索与筛选
- [ ] 提示词模板管理（MVP后第一期）
- [ ] 项目看板视图（MVP后第二期）

## 依赖安装

```bash
# 后端
cd backend
pip install -r requirements.txt

# 前端
cd frontend
npm install
```

## 测试

```bash
# 后端单元测试
cd backend
pytest tests/ -v --asyncio-mode=auto

# 前端构建检查
cd frontend
npm run build
```

## 项目结构

```
ai-req-platform/
├── frontend/                 # React前端
│   ├── src/
│   │   ├── pages/           # 页面组件
│   │   ├── components/      # UI组件
│   │   ├── store/           # Zustand状态
│   │   └── api/             # API封装
│   └── dist/                # 构建产物
├── backend/                  # FastAPI后端
│   ├── app/
│   │   ├── api/v1/         # API路由
│   │   ├── models/          # ORM模型
│   │   ├── schemas/         # Pydantic模型
│   │   ├── services/        # 业务逻辑
│   │   └── static/          # 静态文件
│   └── tests/               # 测试
└── run.py                   # 启动脚本
```
