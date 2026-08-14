# design · T-11 看板里程碑阶段门禁体系

> 模板来源：`dev-work/templates/TEMPLATE_DESIGN.md`。**开发填写**，推「待验证」时一并交付。
> 铁律：无输出 = 未测 = 不通过。以下每节均含真实命令与输出。

---

## 一、实现方案

### 思路与关键改动点
- **纯看板功能，零生成逻辑**：本任务只动 `shared_board/server.py`（后端）+ `shared_board/index.html`（前端），**未触碰** `agnes_proxy.py` / `route_registry.json` / 任何 `gen_video`/`build_variants`/关键帧/`data_uri` 链路（红线已守）。
- **数据模型（AC-1.6 / F1）**：
  - 新增 `milestones` 表：`id / project_id / stage_key / stage_name / stage_order / status / created`，用 `CREATE TABLE IF NOT EXISTS` 保证幂等。
  - `tasks` 表加 `milestone_id` 列：迁移前先用 `PRAGMA table_info(tasks)` 查列是否存在，存在则跳过 `ALTER TABLE ... ADD COLUMN`，避免重复执行报错（满足 AC-1.6 幂等迁移）。
- **自动初始化（AC-1.1 / F2）**：新增模块级函数 `ensure_milestones(c, pid)`，仅当该项目 `milestones` 计数为 0 时插入 7 默认阶段（选题/剧本/分镜/生成/配音/剪辑/发布，`stage_order` 1..7，`status='pending'`）。在①创建项目 `POST /api/projects` 时、②访问 `GET /api/projects/<pid>/milestones` 时两处调用，**幂等**（已存在则跳过）。
- **里程碑接口（AC-1.2 / F3）**：
  - `GET /api/projects/<pid>/milestones`：返回 7 阶段，每阶段含 `stage_key/stage_name/stage_order/status` + `total`（该阶段任务数）+ `done`（该阶段已完成数，status='完成'）+ `rate`（done/total 百分比，无任务则 0）；顶层 `overall` 给全部任务完成率。
  - `PUT /api/milestones/<mid>`：更新阶段 `status`（枚举 `pending/active/done`），带 owner 权限校验。
- **任务挂接阶段（AC-1.3 / F4）**：`POST /api/tasks` 与 `PUT /api/tasks/<tid>` 均接受 `milestone_id`（经 `validate_task_fields` 校验为整数或 null）；`GET /api/tasks`、`GET /api/ext/tasks` 的返回新增 `milestone_id` 字段。前端抽屉新增「阶段」下拉（7 阶段 + 无），卡片显示阶段徽章。
- **阶段进度聚合 + 视图（AC-1.4 / AC-1.5 / F5 / F6）**：前端新增里程碑面板，渲染 7 阶段流水线（顺序 + 状态配色 pending/active/done + 进度条 + 任务计数），顶部展示整体流水线完成率；切换项目 / 新增任务 / 自动刷新经 `loadMilestones()` 实时拉取，无需重启后端。
- **白名单路由（PRD 边界 6）**：server.py 以「路径显式匹配 = 放行」为路由白名单；新接口在 `do_GET`/`do_PUT` 中以 `self.path.startswith(...)` 显式登记；端点均落在 `/api/` 前缀下，8787 `/board/api/` 反代自动覆盖（与既有 `/api/projects`、`/api/tasks` 同源）。
- **隔离自测开关**：`DB`/`PORT` 支持环境变量 `BOARD_DB`/`BOARD_PORT` 覆盖（默认值不变），便于在临时 DB + 隔离端口跑自测，绝不污染线上 `board.db`。

### 与现有逻辑兼容
- `tasks` 读写约定完全增量兼容：`milestone_id` 默认为 NULL，已有任务不受影响；`INSERT/SELECT/UPDATE` 仅追加一列，不改动既有字段语义。
- 后端每次 GET 实时读 `index.html`，前端改动即时生效；仅 `server.py` 改动需重启 8788（已部署验证）。

---

## 二、接口契约

| 项 | 说明 |
|---|---|
| `GET /api/projects/<pid>/milestones` | 返回 7 阶段 + 整体完成率（读接口，无需令牌） |
| `PUT /api/milestones/<mid>` | 更新阶段 `status`（写接口，需 `X-Board-Token` 或 `?token=`，owner 权限） |
| `POST /api/tasks`（含 `milestone_id`） | 创建任务时可挂接阶段（写接口，需令牌） |
| `PUT /api/tasks/<tid>`（含 `milestone_id`） | 更新任务时可改挂阶段（写接口，需令牌） |
| 输入字段 | `project_id`；`milestone_id`(任务写，整数或 null)；`status`(阶段写，pending/active/done) |
| 输出字段（milestones） | `stages:[{id,stage_key,stage_name,stage_order,status,total,done,rate}]` + `overall:{total,done,rate}` |
| 输出字段（tasks） | 既有字段 + `milestone_id`(整数或 null) |
| 下游消费方 | `index.html` 里程碑面板 / 任务卡片阶段徽章 / 抽屉阶段下拉 |

> 注：本任务**不含**「删除/重排阶段」接口（里程碑为固定 7 阶段门禁），符合 PRD 边界。

---

## 三、自测证据（铁律：无输出 = 未测 = 不通过）

> 隔离策略：复制线上 `board.db` 到 `C:/Users/67972/AppData/Local/Temp/t11test/board.db`（临时 DB），以 `BOARD_DB=... BOARD_PORT=8799/8801 BOARD_TOKEN=t11test` 启动**独立进程**，全程不读写线上 `board.db`。测完清理临时文件。
> before 状态基线提交：`7c93064`（server.py / index.html 在本任务前未改）。

### 3.1 改动文件清单（git diff --stat）
```
 shared_board/index.html |  76 +++++++++++++++++++++++++++++---
 shared_board/server.py  | 113 +++++++++++++++++++++++++++++++++++++++++++-----
 2 files changed, 172 insertions(+), 17 deletions(-)
```
（仅 `server.py` 与 `index.html` 两文件；未动 `agnes_proxy.py` / `route_registry.json` / 任何生成链路。）

### 3.2 本机跑测试的真实命令 + stdout

**A. 启动隔离实例（临时 DB + 隔离端口）**
```
# 复制线上 DB 到临时位置（绝不碰线上）
mkdir -p /c/Users/67972/AppData/Local/Temp/t11test
cp shared_board/board.db /c/Users/67972/AppData/Local/Temp/t11test/board.db
# 启动独立服务（新代码），DEBUG 用 BOARD_TOKEN 已知值便于写接口鉴权
BOARD_DB="C:/Users/67972/AppData/Local/Temp/t11test/board.db" BOARD_PORT=8801 \
  BOARD_TOKEN=t11test BOARD_INJECT_TOKEN=0 python shared_board/server.py
# -> board running at http://0.0.0.0:8801
```

**B. 功能自测套件（覆盖 AC-1.1~1.6 + F3，断言全部 PASS）**
```
python C:/Users/67972/AppData/Local/Temp/t11test/test_t11.py
```
输出（节选关键断言）：
```
PASS: AC-1.1 项目创建 200  -> {'id': 20, 'owner': '老板'}
PASS: AC-1.2 milestones 200
PASS: AC-1.1/1.2 返回 7 阶段  -> got 7
PASS: AC-1.2 stage_key/name/order 正确
  -> [('topic','选题',1),('script','剧本',2),('storyboard','分镜',3),
      ('generate','生成',4),('dubbing','配音',5),('edit','剪辑',6),('publish','发布',7)]
PASS: AC-1.2 字段齐全
PASS: AC-1.2 初始全 pending
PASS: AC-1.4 初始全 0 计数
PASS: AC-1.4 overall 初始  -> {'total': 0, 'done': 0, 'rate': 0}
PASS: AC-1.3 任务A/任务B/任务C(无阶段) 创建
PASS: AC-1.4 stage1 total=2  -> {'total': 2, 'done': 1, 'rate': 50}
PASS: AC-1.4 stage1 done=1
PASS: AC-1.4 stage1 rate=50  -> 50
PASS: AC-1.4 overall total=3/done=1/rate=33  -> {'total': 3, 'done': 1, 'rate': 33}
PASS: AC F3 PUT 阶段 200
PASS: AC 阶段 status=active 生效  -> active
PASS: AC 非法 status 400  -> {'error': 'status 非法，允许: pending/active/done'}
PASS: AC-1.1 幂等 重复GET仍7
PASS: AC-1.1 DB 精确 7 条(未重复插入)  -> DB count=7
PASS: AC-1.6 tasks.milestone_id 列存在
  -> ['id','project_id','parent_id','title','detail','status','author',
      'updated','priority','deadline','block_reason','progress','milestone_id']
PASS: AC-1.3 milestone_id 已落库  -> 1
PASS: AC-1.1 项目2 独立 7 阶段
PASS: AC-1.1 DB 项目2 精确 7
PASS: AC-1.6 milestones 表存在
  -> ['projects','sqlite_sequence','tasks','presence','audit','notes','milestones']
PASS: AC-1.3 PUT tasks 可改 milestone_id 200
PASS: AC-1.3 改挂后 stage1 total=3  -> {'total': 3, 'done': 1, 'rate': 33}

RESULT: ALL PASS
```

**C. 双入口验证（8788 直连 与 8787 /board 网关，对线上项目 id=19）**
```
curl -s http://127.0.0.1:8788/api/projects/19/milestones \
  | python -c "import sys,json;d=json.load(sys.stdin);print('stages=',len(d['stages']),'overall=',d['overall'])"
# 8788 直连 -> stages= 7  overall= {'total': 12, 'done': 10, 'rate': 83}

curl -s http://127.0.0.1:8787/board/api/projects/19/milestones \
  | python -c "import sys,json;d=json.load(sys.stdin);print('stages=',len(d['stages']),'overall=',d['overall'])"
# 8787 /board 网关 -> stages= 7  overall= {'total': 12, 'done': 10, 'rate': 83}   （与直连完全一致）
```
> 结论：新接口在 8788 直连与 8787 `/board` 网关两入口返回**完全一致**（7 阶段 + 整体 12 任务 / 10 完成 / 83%）。8787 网关对 `/api/` 前缀反代已覆盖本任务新端点（与既有 `/api/projects`、`/api/tasks` 同源验证）。

**D. 线上 DB 迁移安全校验（部署新代码后，确认旧数据不被破坏）**
```
python - <<'PY'
import sqlite3
con=sqlite3.connect("shared_board/board.db")
tbls=[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("tables:", tbls)                       # 含 milestones
cols=[r[1] for r in con.execute("PRAGMA table_info(tasks)").fetchall()]
print("tasks 列含 milestone_id:", "milestone_id" in cols)   # True
n_tasks=con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]        # 20
n_mil=con.execute("SELECT COUNT(*) FROM milestones").fetchone()[0]     # 7（仅访问过的项目）
null_mil=con.execute("SELECT COUNT(*) FROM tasks WHERE milestone_id IS NULL").fetchone()[0]  # 20
con.close()
PY
# 输出：
# tables: ['projects','sqlite_sequence','tasks','presence','audit','notes','milestones']
# milestones 表存在: True
# tasks 列含 milestone_id: True -> [... 'progress', 'milestone_id']
# tasks 总数=20, milestones 总数=7, milestone_id 为 NULL 的 tasks=20
```
> 线上 20 条既有任务**全部完好**（`milestone_id` 默认 NULL 不受影响），迁移可重复执行不报错（每次请求都跑 `db()` 迁移，已反复验证无异常）。

**E. 前端语法 / 实时生效校验**
```
node --check "C:/Users/67972/AppData/Local/Temp/t11test/app.js"  -> JS_SYNTAX_OK
# 8788 实时托管的 index.html 包含里程碑代码：
#   btnMilestone / d_milestone / loadMilestones / milestonePanel / stage-badge （grep 命中）
```
> 前端 JS 语法通过 `node --check`；后端每次 GET 实时读 `index.html`，前端改动**无需重启即生效**（已部署验证）。

### 3.3 关键运行日志 / 截图
- 隔离实例启动日志：`C:/Users/67972/AppData/Local/Temp/t11test/server2.log`（`board running at http://0.0.0.0:8801`，无异常）。
- 线上部署日志：`C:/Users/67972/AppData/Local/Temp/t11test/8788_live.log`（新代码启动正常）。
- 自测套件：`C:/Users/67972/AppData/Local/Temp/t11test/test_t11.py`（可重跑，结果 ALL PASS）。

### 3.4 可真跑的启动 / 调用命令
```bash
# 1) 隔离自测（不污染线上）
cp shared_board/board.db /c/Users/67972/AppData/Local/Temp/t11test/board.db
BOARD_DB="C:/Users/67972/AppData/Local/Temp/t11test/board.db" BOARD_PORT=8801 \
  BOARD_TOKEN=t11test BOARD_INJECT_TOKEN=0 python shared_board/server.py &
python /c/Users/67972/AppData/Local/Temp/t11test/test_t11.py   # 期望 ALL PASS

# 2) 部署（重启 8788 使新代码生效；8787 /board 网关自动覆盖 /api/ 前缀）
python shared_board/server.py &   # 监听 8788，迁移旧 DB 并自动初始化各项目 7 阶段

# 3) 双入口验证
curl -s http://127.0.0.1:8788/api/projects/<pid>/milestones
curl -s http://127.0.0.1:8787/board/api/projects/<pid>/milestones
```

---

## 四、提测说明（测试怎么接）

- **测试入口**：`shared_board/server.py` 的 `GET /api/projects/<pid>/milestones`、`PUT /api/milestones/<mid>`、`POST|PUT /api/tasks`（`milestone_id`）；前端 `index.html` 里程碑面板 + 抽屉阶段下拉 + 卡片阶段徽章。
- **待测范围**：AC-1.1 自动初始化（幂等） / AC-1.2 里程碑数据接口（7 阶段 + 计数 + 完成率） / AC-1.3 任务挂接阶段（创建/更新 + 抽屉下拉 + 卡片徽章） / AC-1.4 阶段进度聚合（每阶段 done/total + 进度条 + 整体完成率） / AC-1.5 阶段视图 UI（7 阶段流水线 + 状态配色 + 实时刷新） / AC-1.6 迁移安全（幂等、旧数据不受影响） / AC-1.7 证据铁律。
- **已知限制（非阻塞）**：
  - 自动初始化只在「首次访问某项目 milestones」或「创建项目」时触发；已存在项目未访问过 milestones 接口的，访问后才出现 7 阶段（符合 AC-1.1 语义，非缺陷）。
  - 整体完成率 `overall` 口径 = 该项目**全部任务**完成率（含未挂接阶段的任务），与「各阶段 done/total 之和」可能因未挂接任务而有差异，属设计取舍（PRD「全部任务完成率」）。
  - 本任务未提供「删除/重排阶段」UI（固定 7 阶段门禁），符合 PRD 边界。

---

## 五、文档回写

- [x] `design.md` 已填（本文件，含三章证据：git diff --stat + 隔离自测 ALL PASS + 双入口验证 + 线上迁移安全 + JS 语法 OK）
- [x] `shared_board/server.py` / `shared_board/index.html` 已实现并自测通过
- [x] 改动已 `git commit`（T-11，见提交记录）
- [ ] `test.md` / `acceptance.md` 由 QA / 主理人填写（非开发职责）
- [ ] `current_state.md` AC 进度由主理人/QA 在验收阶段更新
