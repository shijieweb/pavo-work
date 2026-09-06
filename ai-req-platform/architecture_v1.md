# AI驱动需求管理与研发协作平台 - 架构文档

## 一、技术选型结论

### 已锁定技术栈

| 层级 | 选型 | 版本 | 锁定原因 |
|------|------|------|----------|
| 前端框架 | React | 18.3+ | 生态成熟，与Vite/Tailwind集成好 |
| 构建工具 | Vite | 7.0+ | 开发体验好，热更新快 |
| 类型系统 | TypeScript | 5.7+ | 类型安全，减少运行时错误 |
| CSS框架 | Tailwind CSS | 3.4+ | 原子化CSS，快速开发 |
| UI组件 | shadcn/ui | latest | 基于Radix UI，可定制 |
| **图标库** | **lucide-react** | **0.469.0** | **P0锁定，统一描边SVG** |
| 状态管理 | Zustand | 5.0+ | 轻量，无 boilerplate |
| 表单验证 | react-hook-form + zod | 7.54+ / 3.24+ | 类型安全表单 |
| HTTP客户端 | axios | 1.7+ | 拦截器支持认证 |
| 后端框架 | FastAPI | 0.115+ | Python async，自动文档 |
| ORM | SQLAlchemy | 2.0+ | 声明式风格，类型安全 |
| 迁移工具 | Alembic | 1.14+ | SQLAlchemy官方迁移 |
| 数据库 | SQLite | - | 本地文件，零运维 |
| AI SDK | openai | 5.0+ | OpenAI兼容格式 |
| 认证 | python-jose | 3.3+ | JWT生成/验证 |

---

## 二、分层架构

```
前端 (React + Vite)
├── pages/              # 页面组件
├── components/         # UI组件
├── services/           # API服务层
├── store/              # Zustand全局状态
└── types/              # TypeScript类型定义

后端 (FastAPI)
├── main.py             # 应用入口，挂载静态文件和路由
├── api/
│   ├── v1/
│   │   ├── settings.py # 设置相关接口
│   │   ├── projects.py # 项目相关接口
│   │   └── ai.py       # AI相关接口
│   └── deps.py         # 依赖注入
├── core/
│   ├── config.py       # 配置管理
│   ├── security.py     # 安全（JWT、加密）
│   └── auth.py         # 认证中间件
├── models/             # SQLAlchemy ORM模型
├── schemas/            # Pydantic请求/响应模型
├── services/           # 业务逻辑层
│   ├── ai_service.py   # AI调用服务
│   └── project_service.py
└── db/
    ├── session.py      # 数据库会话
    └── base.py         # ORM基类
```

**依赖方向约束：**
- pages → components → services → stores
- api → services → models
- 禁止：services import api, models import services

**文件组织硬规则：**
- 单文件 ≤ 300 行
- 入口文件 ≤ 100 行
- Controller 不直连 DB
- Service 不 import req/res

---

## 三、数据库Schema

### 表1：global_settings（全局设置）

```sql
CREATE TABLE global_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ai_api_url VARCHAR(500),
    ai_api_key VARCHAR(500),  -- 加密存储
    ai_model_name VARCHAR(100),
    frontend_stack TEXT,
    backend_stack TEXT,
    database_stack TEXT,
    testing_stack TEXT,
    deployment_stack TEXT,
    directory_tree TEXT,      -- JSON
    token VARCHAR(255),       -- 全局认证Token
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 表2：projects（项目）

```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    target_users TEXT,        -- JSON数组字符串
    core_functions TEXT,      -- JSON数组字符串
    key_scenarios TEXT,       -- JSON数组字符串
    architecture_snapshot TEXT, -- JSON
    status VARCHAR(50) DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME       -- 软删除
);

CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_created ON projects(created_at DESC);
```

### 表3：prompt_templates（提示词模板）

```sql
CREATE TABLE prompt_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL UNIQUE,
    purpose VARCHAR(500),
    content TEXT NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 表4：project_initialization（项目初始化快照）

```sql
CREATE TABLE project_initialization (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    file_tree TEXT,           -- JSON
    readme_content TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX idx_init_project ON project_initialization(project_id);
```

---

## 四、API端点清单

### 4.1 认证（全局Token）

| Method | Path | 说明 |
|--------|------|------|
| GET | /api/v1/health | 健康检查 |

认证方式：请求头 `Authorization: Bearer <token>`

### 4.2 全局设置

| Method | Path | 说明 | 请求体 |
|--------|------|------|--------|
| GET | /api/v1/settings | 获取设置 | - |
| PUT | /api/v1/settings/ai-model | 更新AI配置 | `{api_url, api_key, model_name}` |
| POST | /api/v1/settings/ai-model/test | 测试连接 | - |

### 4.3 项目管理

| Method | Path | 说明 | 请求体 |
|--------|------|------|--------|
| POST | /api/v1/projects | 创建项目 | `{name, description}` |
| GET | /api/v1/projects | 列表（支持?search=&status=） | - |
| GET | /api/v1/projects/{id} | 详情 | - |
| PUT | /api/v1/projects/{id} | 更新 | `{name?, description?, status?}` |
| DELETE | /api/v1/projects/{id} | 删除（软删除） | - |

### 4.4 AI辅助

| Method | Path | 说明 | 请求体 |
|--------|------|------|--------|
| POST | /api/v1/ai/optimize-project | AI优化描述 | `{project_id}` |
| POST | /api/v1/ai/chat | AI对话（SSE流式） | `{messages, project_id?}` |

### 4.5 提示词模板

| Method | Path | 说明 |
|--------|------|------|
| GET | /api/v1/prompts | 列表 |
| GET | /api/v1/prompts/{id} | 详情 |
| POST | /api/v1/prompts | 创建 |
| PUT | /api/v1/prompts/{id} | 更新 |
| DELETE | /api/v1/prompts/{id} | 删除 |

---

## 五、AI调用设计

### 5.1 调用流程

```
前端 → POST /api/v1/ai/optimize-project
      ↓
后端 → 读取global_settings中的AI配置
      ↓
后端 → 调用OpenAI兼容API（async stream）
      ↓
后端 → SSE流式返回优化结果
      ↓
前端 → 实时显示优化内容
```

### 5.2 Prompt模板

```markdown
你是一位资深产品经理。请帮助用户优化项目描述，使其更专业、结构化。

【项目基本信息】
名称：{project_name}
当前描述：{current_description}

【优化要求】
1. 保持原意，提升表达清晰度
2. 使用结构化格式（目标用户、核心功能、关键场景）
3. 语言简洁专业，避免空泛描述
4. 输出JSON格式：{"description": "...", "target_users": [...], "core_functions": [...], "key_scenarios": [...]}
```

---

## 六、安全设计

### 6.1 API密钥加密

- 使用Fernet对称加密存储API Key
- 密钥存储于环境变量或配置文件
- 数据库中仅存密文

### 6.2 全局Token认证

- 首次启动生成随机Token
- Token存储于global_settings表
- 请求头携带Token进行认证
- 后续可升级为JWT

---

## 七、目录结构

```
ai-req-platform/
├── frontend/                    # 前端源码
│   ├── src/
│   │   ├── api/                # API请求封装
│   │   ├── components/         # 通用组件
│   │   ├── pages/              # 页面组件
│   │   │   ├── ProjectList.tsx
│   │   │   ├── ProjectForm.tsx
│   │   │   ├── ProjectDetail.tsx
│   │   │   └── Settings.tsx
│   │   ├── services/           # 业务服务
│   │   ├── store/              # Zustand状态
│   │   ├── types/              # TS类型
│   │   ├── hooks/              # 自定义Hooks
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── tsconfig.json
├── backend/                     # 后端源码
│   ├── app/
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── settings.py
│   │   │   │   ├── projects.py
│   │   │   │   ├── ai.py
│   │   │   │   └── prompts.py
│   │   │   └── deps.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── auth.py
│   │   ├── models/
│   │   │   ├── setting.py
│   │   │   ├── project.py
│   │   │   └── prompt.py
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── ai_service.py
│   │   │   └── project_service.py
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   └── base.py
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   ├── requirements.txt
│   └── .env
├── run.py                       # 启动脚本
├── spec_v1.md                   # 规格文档
├── prd_v1.md                    # PRD文档
└── README.md
```

---

## 八、关键决策记录

| 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|
| 图标库 | lucide-react / heroicons / phicons | **lucide-react** | 生态最成熟，与shadcn/ui配套，Tree-shaking友好 |
| 状态管理 | Redux / MobX / Zustand | **Zustand** | 轻量，无boilerplate，TypeScript支持好 |
| 表单方案 | Formik / React Final Form / react-hook-form | **react-hook-form + zod** | 性能好，类型安全，与TypeScript集成好 |
| HTTP客户端 | fetch / axios / ky | **axios** | 拦截器支持好，易于添加认证头 |
| AI SDK | openai / anthropic / langchain | **openai** | 兼容格式，可切换后端（DeepSeek/Claude等） |
| 认证方案 | JWT / Session / 全局Token | **全局Token** | MVP阶段单机使用，简单有效 |

---

## 九、已知坑提醒

> 从项目记忆拉取，当前为全新项目，无历史坑记录。

| 坑 | 技术栈指纹 | 根因 | 修法 |
|----|------------|------|------|
| — | — | — | — |

---

*架构文档版本：v1.0*
*撰写人：高见远（首席架构师）*
*日期：2026-08-23*
