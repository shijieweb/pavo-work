# Spec - AI驱动需求管理与研发协作平台 v1.0

> 生成日期：2026-08-23
> 基于：PRD v1.0 + 架构文档 v1.0 + UIUX文档 v1.0
> 状态：待确认

---

## 1. 产品定义
- **一句话描述**：本地优先的AI驱动需求管理与研发协作工具，数据不出设备，无订阅费
- **目标用户**：5-20人中小研发团队、独立开发者、合规敏感型行业IT部门
- **核心问题**：云端竞品数据外泄风险高、订阅费压力大、AI能力碎片化

---

## 2. MVP范围（锁定）

| 优先级 | 功能 | 验收标准摘要 | RICE评分 |
|--------|------|-------------|----------|
| P0 | 项目CRUD | 创建/读取/更新/删除项目，支持名称、描述、状态字段 | 10.0 |
| P0 | AI辅助优化项目描述 | 调用配置的AI模型优化项目描述，支持应用/放弃优化结果 | 4.8 |
| P1 | 项目搜索与筛选 | 按名称/描述关键词搜索，按状态筛选，实时过滤 | 4.0 |
| P1 | AI模型配置 | 配置API端点、API Key、模型名称，支持测试连接 | 3.7 |

---

## 3. 明确不做（Out-of-Scope）

| 不做的功能 | 原因 | 何时考虑 |
|------------|------|----------|
| 提示词模板管理 | MVP后第一期迭代（Score: 3.0） | MVP验证后 |
| 项目看板视图 | 可视化视图增加复杂度（Score: 1.75） | MVP后第二期 |
| 项目导出CSV/JSON | 数据迁移需求可延后（Score: 3.4） | MVP后第二期 |
| 团队协作（多用户） | SQLite写入锁限制并发（Score: 1.2） | 长期规划 |
| WebSocket实时通信 | MVP阶段轮询足够（架构师建议） | 后续迭代 |

---

## 4. 技术架构（锁定）

| 层 | 技术 | 实际版本 | 锁定原因 |
|----|------|----------|----------|
| 前端框架 | React | 18.3+ | 生态成熟，与Vite/Tailwind集成好 |
| 构建工具 | Vite | 7.0+ | 开发体验好，热更新快 |
| 类型系统 | TypeScript | 5.7+ | 类型安全，减少运行时错误 |
| UI框架 | Tailwind CSS | 3.4+ | 原子化CSS，快速开发 |
| 组件库 | shadcn/ui | latest | 基于Radix UI，可定制 |
| 图标库 | lucide-react | 0.469.0 | **P0锁定**，统一描边SVG |
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

## 5. API端点清单（锁定）

| Method | Path | 功能 | 认证 | 请求体 | 响应体 |
|--------|------|------|------|--------|--------|
| GET | /api/v1/settings | 获取全局设置 | Token | - | {ok, settings} |
| PUT | /api/v1/settings/ai-model | 更新AI模型配置 | Token | {api_url, api_key, model_name} | {ok} |
| POST | /api/v1/settings/ai-model/test | 测试AI模型连接 | Token | - | {ok, connected} |
| POST | /api/v1/projects | 创建项目 | Token | {name, description} | {ok, project} |
| GET | /api/v1/projects | 获取项目列表 | Token | ?search=&status= | {ok, projects} |
| GET | /api/v1/projects/{id} | 获取项目详情 | Token | - | {ok, project} |
| PUT | /api/v1/projects/{id} | 更新项目信息 | Token | {name?, description?, status?} | {ok} |
| DELETE | /api/v1/projects/{id} | 删除项目 | Token | - | {ok} |
| POST | /api/v1/ai/optimize-project | AI优化项目描述 | Token | {project_id} | {ok, optimized_description} |

---

## 6. 数据库表清单（锁定）

| 表名 | 核心字段 | 索引 | 关联 |
|------|----------|------|------|
| global_settings | id, ai_api_url, ai_api_key, ai_model_name, frontend_stack, backend_stack, database_stack, created_at, updated_at | PK(id) | - |
| projects | id, name, description, target_users(JSON), core_functions(JSON), key_scenarios(JSON), architecture_snapshot(JSON), status, created_at, updated_at | PK(id), INDEX(status), INDEX(created_at) | - |
| prompt_templates | id, name, purpose, content, enabled, created_at, updated_at | PK(id), UNIQUE(name) | - |
| project_initialization | id, project_id(FK), file_tree(JSON), readme_content, created_at | PK(id), INDEX(project_id) | FK→projects.id |

---

## 7. 页面清单（锁定）

| 页面 | 路由 | 核心组件 | 对应API | 设计Token主题 |
|------|------|----------|---------|---------------|
| 项目列表 | / | ProjectList, SearchBar, Filter, EmptyState | GET /projects | light/dark |
| 新建项目 | /new | ProjectForm, AI Optimize Button | POST /projects, POST /ai/optimize-project | light/dark |
| 项目详情 | /projects/:id | ProjectDetail, EditForm | GET/PUT/DELETE /projects/:id | light/dark |
| 设置 | /settings | AISettingsCard, PromptTemplatesList | GET/PUT /settings/* | light/dark |

---

## 8. 设计Token（锁定）

> 设计师**必须**同时产出 `design-tokens.json` + `design-tokens.css`

- **主色**：Slate Blue `#4F46E5`（品牌强调色）
- **字体**：
  - 标题：Inter, Noto Sans SC, sans-serif
  - 正文：Inter, Noto Sans SC, sans-serif
  - 代码：JetBrains Mono, Fira Code, monospace
- **图标库**：**lucide-react 0.469.0**（P0锁定）
- **主题**：浅色（默认）+ 深色（可选）
- **对标品牌**：Linear, Notion, Stripe Dashboard
- **三轴**：Variance=5, Motion=4, Density=6

---

## 9. 验收标准（锁定）

| 编号 | 功能 | EARS格式验收标准 | 优先级 |
|------|------|------------------|--------|
| AC-01 | 创建项目 | While 用户填写合法项目名称，系统必须创建项目并返回列表 | P0 |
| AC-02 | 创建项目 | If 项目名称为空，系统必须显示错误提示"项目名称不能为空" | P0 |
| AC-03 | AI优化 | When 用户点击AI优化按钮且AI已配置，系统必须调用AI并返回优化结果 | P0 |
| AC-04 | AI优化 | If AI未配置，系统必须提示"请先配置AI模型" | P0 |
| AC-05 | 搜索 | When 用户在搜索框输入关键词，系统必须实时过滤项目列表 | P1 |
| AC-06 | 测试连接 | When 用户点击测试连接，系统必须验证配置有效性并显示结果 | P1 |

---

## 10. 边界与约束
- 不支持IE浏览器（现代浏览器即可）
- 响应式断点：xs<640px / sm≥640px / md≥768px / lg≥1024px / xl≥1280px
- 性能目标：首屏加载<2s，AI响应<10s
- SQLite WAL模式开启提升并发读取性能
- 单机使用，无多用户并发写入限制（MVP阶段）

---

## 11. 内嵌已知坑
> 从项目记忆拉取，当前为全新项目，无历史坑记录

| 坑 | 技术栈指纹 | 根因 | 修法 |
|----|------------|------|------|
| — | — | — | — |

---

## 12. 端到端验证步骤

```bash
# 1. 初始化后端
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head

# 2. 启动后端
uvicorn app.main:app --reload --port 8000

# 3. 初始化前端
cd ../frontend
npm install

# 4. 启动前端开发服务器
npm run dev

# 5. 访问 http://localhost:5173

# 6. 核心流程验证
# - 进入设置页，配置AI模型（API URL、Key、模型名）
# - 测试连接，确认成功
# - 创建项目，填写名称和描述
# - 点击AI优化，确认调用成功
# - 在项目列表搜索，确认过滤正常
```

---

## 13. 变更记录
| 日期 | 变更内容 | 原因 | 影响范围 |
|------|----------|------|----------|
| 2026-08-23 | 初始版本 | 基于需求文档和三方调研生成 | 全量 |

---

## 附录A：P0绝对规则确认

- ✅ 图标库已锁定：**lucide-react 0.469.0**，禁止任何emoji作为功能图标
- ✅ 主色已锁定：**Slate Blue #4F46E5**，禁止紫色→粉色渐变
- ✅ 无AI模板味文案，使用产品特定描述

## 附录B：关键决策日志

```
[22:40] Phase 0 - 用户确认技术决策 - 认证用全局Token，AI用OpenAI兼容，数据本地SQLite，部署本地 - 影响：简化架构，跳过用户系统开发
[22:42] Phase 1 - 锁定图标库为lucide-react - 理由：生态成熟、Tree-shaking友好、与shadcn/ui配套 - 影响：前端依赖锁定
[22:42] Phase 1 - 锁定设计风格为Swiss Minimalism - 理由：SaaS工具类标杆是Linear/Notion - 影响：设计Token全部按此风格输出
```
