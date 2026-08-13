# T-20260813-05 开发设计 · 看板外部指导 API（/ext/*）+ 状态对齐

- **任务**：T-20260813-05（远程指导角色经 8787 网关 `/ext/*` 读看板进度 + 留指导意见；顺带修 board 状态对齐）
- **蓝本**：`dev-work/看板改造方案_20260813.md`（v2，老板已批"按推荐来"）；PRD 见本目录 `PRD.md`
- **阶段**：本文档为**开发设计（先于代码）**，主理人审过才进入实现；本阶段不写代码、不改任何业务文件、不重启服务
- **核心设计一句话**：`route_registry.json` 加一条 `/ext` 路由（`kind=generic` + `target=http://127.0.0.1:8788/api/ext` + `flags.board_token_inject=true`），复用现有 `_proxy_route` 完成 `/ext/`→`/api/ext/` 改写与 X-Board-Token 注入，**`agnes_proxy.py` 零代码改动**；`shared_board/server.py` 新增 `notes` 表 + `/api/ext/*` 6 个端点（只读 + 留言）。

---

## 0. 现状核实（基于真实代码，非臆造）

| 事实 | 证据（文件:行） |
|---|---|
| 8787 路由已注册表化，`route_registry.json` 是单一事实源；无注册表/解析失败回退硬编码 | `agnes_proxy.py:137-219`（`_load_route_registry`/`_route_for`）；`route_registry.json:3` |
| 注册表驱动分发：`kind=board→_proxy_board`、`kind=studio→_proxy_studio`、其余→`_proxy_route`（generic） | `agnes_proxy.py:377-397`（`_route_dispatch`） |
| generic 转发 `_proxy_route`：去掉挂载前缀后的子路径 `sub` 拼到 `target`；可选 `flags.board_token_inject`（自动注入 X-Board-Token）；自动透传 `X-Agent` 头；超时 300s | `agnes_proxy.py:399-452`（尤其 407-413 拼 target、419-422 token、423-425 X-Agent） |
| 注册表加载是**模块导入时一次性**执行 → 改注册表后必须重启 8787 才生效 | `agnes_proxy.py:200-203` |
| 现有 `/board` 路由条目的 flags 写法（board_token_inject + rewrite_html_api）可参照 | `route_registry.json:222-231` |
| 8788 board 库表：`projects(id,name,created,owner)`、`tasks(id,project_id,parent_id,title,detail,status,author,updated,priority)`、`presence(agent,last_seen)`、`audit(id,ts,agent,action,target,project_id)` | `shared_board/server.py:73-98`（`db()`） |
| **现有库中没有 notes/留言表**（只有上面 4 张）→ POST /ext/notes 需**新增 notes 表** | `shared_board/server.py:73-98` 全表清单 |
| 写接口统一在 `do_POST` 顶部过 `board_token_ok` 闸（POST/PUT/DELETE 都要） | `shared_board/server.py:169-172`（do_POST）、195-198、230-233 |
| GET 只读端点：`/api/projects`、`/api/tasks?`、`/api/presence`、`/api/audit`（LIMIT 20） | `shared_board/server.py:139-165` |
| 可复用 helper：`now()`、`touch(c,agent)`、`audit(c,agent,action,target,project_id)`、`proj_owner(c,pid)`、`allowed(agent,owner)`、`agent_of(self)`、`board_token_ok(self)`、`send(h,code,obj)`、`body(h)` | `shared_board/server.py:37-114` |
| 前端已有审计流渲染 `#audit`（`[ts] agent action target`，5s 轮询）→ 写入 audit 的「指导留言」**无需改前端即可见** | `shared_board/index.html:225-226, 240-245` |
| 门户自启：8787 启动时 `_launch_board()` 复用/拉起 8788 | `agnes_proxy.py:123-129, 823-832` |
| AC-1.5 数据源：current_state.md 已闭环清单（T-01/02/03/04 完成）vs board #26 仍标 todo | `dev-work/current_state.md:339-346`；方案 v2 §2.1 |

---

## 1. 改动点清单（精确到文件 + 位置）

### 1.1 `route_registry.json` —— 加 1 条路由（配置，非代码）

在 `routes` 数组末尾（`/demo` 条目之后，`examples` 之前）新增：

```json
{
  "prefix": "/ext",
  "target": "http://127.0.0.1:8788/api/ext",
  "kind": "generic",
  "flags": {
    "board_token_inject": true
  },
  "note": "外部指导 API（T-20260813-05）：/ext/* 改写为 8788 /api/ext/*；无鉴权直达（老板决策），代理自动注入 X-Board-Token 过 board 写闸"
}
```

**改写机制（关键，已验证）**：`_proxy_route` 把 `target + sub` 拼接（`agnes_proxy.py:407-414`）。`target` 以 `/api/ext` 结尾（注册表加载时会 `rstrip("/")`，`agnes_proxy.py:188`），因此：
- `GET /ext/status` → sub=`/status` → `http://127.0.0.1:8788/api/ext/status` ✅
- `POST /ext/notes` → sub=`/notes` → `http://127.0.0.1:8788/api/ext/notes` ✅
- 查询串 `?project_id=19` 由 `_proxy_route` 原样保留（`agnes_proxy.py:413`）✅

**flags 复用说明**：
- `board_token_inject: true` → 复用现有自动注入逻辑（`agnes_proxy.py:419-422`），board 的 `do_POST` 写闸（`server.py:171`）被满足，**外部客户端零 token 直达**（满足 AC-1.4 无鉴权）——与 `/board` 同一机制。
- `rewrite_html_api` **不需要**（/ext 只出 JSON，不出 HTML）。

**注意**：不要加尾斜杠前缀 `/ext/`（会与 `/ext` 触发 `_find_prefix_conflict` 报错，`agnes_proxy.py:147-156,194-198`）；只加这一条即可。

### 1.2 `agnes_proxy.py` —— **零代码改动（核实结论）**

- 已核实 `_proxy_route` 完整支持本次所需：前缀剥离 + 子路径拼 target（实现 `/ext/`→`/api/ext/` 改写）、`board_token_inject` token 注入、`X-Agent` 透传（`agnes_proxy.py:399-452`）。
- 注册表驱动分发 `_route_dispatch` 对 `kind=generic` 自动走 `_proxy_route`（`agnes_proxy.py:386-387`），无需新增分支。
- **因此本任务不动 `agnes_proxy.py` 任何代码**；「加白名单」即注册表加行，非代码加前缀。

### 1.3 `shared_board/server.py` —— 唯一代码改动（新增，不改既有逻辑）

**A. `db()` 新增 notes 表**（位置：`server.py:93` audit 表 CREATE 之后，`c.commit()` 之前）：

```sql
CREATE TABLE IF NOT EXISTS notes(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER,
  text TEXT,
  agent TEXT,
  ts TEXT)
```
- 旧库自动补表（`IF NOT EXISTS`），无需迁移脚本；不手动改 board.db。

**B. `do_GET` 新增 6 个读端点**（位置：`server.py:165` `/api/audit` 分支之后、`404` 之前，均复用现有查询逻辑）：

| 端点 | 实现要点（复用哪个现有查询） |
|---|---|
| `GET /api/ext/status` | 汇总：①全部项目（复用 `/api/projects` 查询，`server.py:147`）；②在途任务 = `status != 'done'`（跨全部项目，按 priority 排序，复用 `/api/tasks?` 排序逻辑 `server.py:151`）；③最近审计 8 条（`ORDER BY id DESC LIMIT 8`，复用 `server.py:162` 结构）。`generated_at=now()` |
| `GET /api/ext/projects` | 与 `/api/projects` 完全一致（支持可选 `?owner=`） |
| `GET /api/ext/tasks?project_id=N` | 与 `/api/tasks?` 完全一致（`project_id` 必填，非法返回 400） |
| `GET /api/ext/audit?project_id=N` | 与 `/api/audit` 完全一致（可选 `?project_id=`，无则全局，LIMIT 20） |
| `GET /api/ext/presence` | 与 `/api/presence` 完全一致 |
| `GET /api/ext/notes?project_id=N` | 读 notes 表（可选 `?project_id=` 过滤；`ORDER BY id DESC LIMIT 100`）——供前端「指导留言」栏（跟进项）与远程角色回读留言 |

- 说明：`do_GET` 顶部已有 `touch(c, raw)`（`server.py:138`），带 `X-Agent` 访问 /ext/* 会自动刷新 presence，与现有行为一致，无需额外处理。

**C. `do_POST` 新增 `POST /api/ext/notes`**（位置：`server.py:191` `/api/tasks` 分支之后、`404` 之前；仍位于 `board_token_ok` 闸之后）：

写库逻辑（复用现有 helper）：
1. `d = body(self)`；`agent = agent_of(self) or "远程指导"`（无 X-Agent 时固定为"远程指导"，满足 AC-1.3 审计署名）。
2. 校验：`project_id` 必须为整数且 `proj_owner(c, pid)` 存在，否则 404 `{"error":"项目不存在: N"}`；`text` 必须为非空字符串，否则 400 `{"error":"text 不能为空"}`。
3. `INSERT INTO notes(project_id,text,agent,ts) VALUES(?,?,?,now())`。
4. `audit(c, agent, "指导留言", f"项目{pid}/留言：{text[:30]}", pid)` —— **复用现有 `audit()` helper（`server.py:42`）**；因现有前端审计流会渲染 `[ts] agent action target`（`index.html:244`），该条留言在「操作日志」中直接可见，**无需改前端即满足"前端可见"**。
5. `touch(c, agent)` 更新在线状态。
6. 返回 `{"ok": true, "id": lastrowid}`。

- 鉴权说明：`/api/ext/notes` 走 8787 时由代理自动注入 X-Board-Token，客户端零 token；若有人直接打 8788 `/api/ext/notes` 且不带 token，仍会被现有写闸 401（与现有写接口一致，不破坏现状）。AC-1.3 的验收路径是 8787 `/ext/notes`，不受影响。

### 1.4 状态对齐（AC-1.5）—— 数据修正，非代码

- 不动 schema、不动代码；在实现阶段用**现有写接口或一次性 SQL**把 board.db 中已闭环任务补标 `done`：
  - 至少：`#26`（T-20260813-01 状态校准，commit `32fb6e8`，方案 v2 §2.1）→ `status='done'`，detail 指向 `dev-work/tasks/T-20260813-01/`。
  - 其余以 `current_state.md` 已闭环清单（T-01/02/03/04 等）为基准，逐条核对 board 实际数据后补标，避免误标。
- 推荐方式：经 8787 `PUT /board/api/tasks/26`（或直连 `PUT /api/tasks/26`，带 token）`{"status":"done","detail":"..."}` —— 走现有审计链路，自动记审计。

### 1.5 前端「指导留言」栏（可选跟进，不阻塞 AC-1.3）

- 本任务**最小闭环**：留言写入 audit（action=指导留言），现有审计流已可见 → AC-1.3 的"前端可见"成立。
- 独立长文本「指导留言」栏（渲染 `GET /api/ext/notes`）需改 `shared_board/index.html`，列为跟进项（见 §5「不能动」之外的可选动作）。

---

## 2. 接口契约（请求 / 响应 JSON Schema）

> 全部经 8787 对外路径为 `/ext/*`；board 内部实现路径为 `/api/ext/*`。除 POST /ext/notes 外均为只读。错误统一为 JSON `{"error": "..."}`。

### 2.1 `GET /ext/status` → 200
请求：无参。
```json
{
  "projects": [
    {"id": 19, "name": "看板改造", "owner": "老板", "created": "2026-08-13 10:00"}
  ],
  "in_flight_tasks": [
    {"id": 26, "project_id": 19, "parent_id": null, "title": "T-20260813-01 状态校准",
     "detail": "…", "status": "doing", "author": "阿编", "updated": "2026-08-13 16:20",
     "priority": "高"}
  ],
  "recent_audit": [
    {"ts": "2026-08-13 18:20", "agent": "远程指导", "action": "指导留言", "target": "项目19/留言：…"}
  ],
  "generated_at": "2026-08-13 18:30"
}
```
- `projects`：全部项目（id/name/owner/created）。
- `in_flight_tasks`：**在途 = `status != 'done'`**（当前库只含 todo/doing，未来 review/verify 态自动纳入），跨全部项目，按 priority（紧急>高>中>低）再 id 排序。
- `recent_audit`：最近 8 条（`ORDER BY id DESC LIMIT 8`）。

### 2.2 `GET /ext/projects` → 200
请求：可选 `?owner=老板`。
```json
[{"id": 19, "name": "看板改造", "owner": "老板", "created": "2026-08-13 10:00"}]
```

### 2.3 `GET /ext/tasks?project_id=N` → 200
请求：`project_id` 必填（整数）。缺失/非法 → 400。
```json
[{"id": 26, "parent_id": null, "title": "T-20260813-01 状态校准", "detail": "…",
  "status": "doing", "author": "阿编", "updated": "2026-08-13 16:20", "priority": "高"}]
```
- 任务树由 `parent_id` 表达（根为 null）；字段与现有 `/api/tasks?` 完全一致。

### 2.4 `GET /ext/audit?project_id=N` → 200
请求：可选 `?project_id=`（无则全局）。
```json
[{"ts": "2026-08-13 18:20", "agent": "远程指导", "action": "指导留言", "target": "项目19/留言：…"}]
```
- 最新在前，LIMIT 20（与现有 `/api/audit` 一致）。

### 2.5 `GET /ext/presence` → 200
请求：无参。
```json
[{"agent": "远程指导", "last_seen": "2026-08-13 18:20"}]
```

### 2.6 `POST /ext/notes` → 200
请求体（JSON）：
```json
{"project_id": 19, "text": "请先修复状态对齐，再开始外部 API 实现"}
```
成功 200：
```json
{"ok": true, "id": 12}
```
错误：
- 400 `{"error": "text 不能为空"}`（text 缺失/空）
- 400 `{"error": "project_id 必填且为整数"}`（缺失/非法）
- 404 `{"error": "项目不存在: 19"}`（项目不存在）

副作用：写 `notes` 表 + 审计 `agent=远程指导（默认）/X-Agent`、`action=指导留言` + 刷新 presence。

### 2.7 `GET /ext/notes?project_id=N` → 200（配套读，供留言栏/回读）
请求：可选 `?project_id=`。
```json
[{"id": 12, "project_id": 19, "text": "请先修复状态对齐…", "agent": "远程指导",
  "ts": "2026-08-13 18:20"}]
```
- 最新在前，LIMIT 100。

---

## 3. 风险点与注意

1. **改注册表 → 8787 必须重启才生效**：`_ROUTE_REGISTRY` 模块导入时一次性加载（`agnes_proxy.py:200-203`）。重启遵循工程铁律：杀残留 PID → 起新 → 核新 PID。8787 启动会 `_launch_board()` 复用/拉起 8788（`agnes_proxy.py:823-832`），故重启 8787 不会丢 8788。
2. **注册表损坏/缺失 → 回退硬编码 → /ext 不可达**：硬编码回退（`STUDIO_PREFIXES` + `_is_board`）不含 `/ext`。风险低（T-02 已稳定 33 路由）；实施时改注册表前先 `python -m json.tool route_registry.json` 校验，且建议先 `git commit before:`。
3. **前缀冲突校验**：`_find_prefix_conflict` 对相等或互为路径前缀的路由**启动即报错**（`agnes_proxy.py:147-156,194-198`）。`/ext` 与现有 33 条无冲突；切勿误加 `/ext/` 尾斜杠前缀。
4. **改 server.py → 8788 干净重启**：杀残留 PID 再起核新 PID；board.db 落盘不丢；重启窗口 `/board` 与 `/ext` 均短暂 503。注意 `_proxy_route`/`_proxy_board` **无自愈拉起**（与现状一致）：运行中 8788 挂掉，/ext 返回 503 提示，需手动重启 8788（或重启 8787 触发自启）。
5. **notes 表兼容性**：`db()` 每次连接 `CREATE TABLE IF NOT EXISTS` → 旧库自动补表，无迁移风险；SQLite 单写进程模式不变，无并发写锁新风险。
6. **鉴权后置（挂账不阻塞）**：/ext 公网开放，可读全部项目/任务/审计/presence，可写留言；写面仅 notes（非任务增删改），风险面 < 现有 `/studio` 与 `/api/*`。统一鉴权层 backlog 触发点不变（VPS 上线/商用前必做）。
7. **「前端可见」依赖审计流**：不做前端时留言经「操作日志」可见；独立留言栏需动 index.html（跟进项）。若主理人要求本次必须出独立栏，则把 index.html 纳入本次改动范围（见 §5）。
8. **AC-1.5 数据对齐是数据修正**：直接改 board.db 或走 PUT 接口补标 done；实施时须与 current_state.md 已闭环清单逐条核对，避免把未闭环任务误标 done。

---

## 4. AC 映射

| AC | 验收点 | design 如何满足 |
|---|---|---|
| AC-1.1 | `GET /ext/status` → 200：全部项目 + 在途任务 + 最近审计 8 条 | §1.1 注册表 `/ext`→`/api/ext` 改写 + §1.3B `/api/ext/status` 聚合端点（projects 全部 + in_flight=`status!='done'` + recent_audit LIMIT 8） |
| AC-1.2 | `GET /ext/projects`、`/ext/tasks?project_id=N`、`/ext/audit?project_id=N`、`/ext/presence` → 200 正确数据 | §1.3B 四个端点全部**复用现有查询逻辑**（`server.py:139-165`），契约见 §2.2~2.5 |
| AC-1.3 | `POST /ext/notes`（`{"project_id":N,"text":"..."}`）→ 写看板留言 + 审计 `agent=远程指导`，前端「指导留言」栏可见 | §1.3C 新增 `notes` 表 + POST 处理器（agent 默认"远程指导"、复用 `audit()` 记 `action=指导留言`）；现有审计流（`index.html:240-245`）即展示 → 前端可见；独立留言栏为跟进项 |
| AC-1.4 | 无 token 直达；`/ext/*` 不污染现有 `/api/*` 路由 | §1.1 `board_token_inject` 由代理注入，客户端零 token（老板决策不做鉴权）；`/ext` 仅映射 8788 `/api/ext/*`，与 8777 `/api/*` 命名空间隔离；`_route_for` 首条命中且无前缀冲突，现有 33 条路由不动 |
| AC-1.5 | 状态对齐：board 已闭环任务补标 done（现状 8done+4todo+0doing 失真） | §1.4 数据修正（非代码）：`#26` 补标 done，其余以 current_state.md 清单核对补标；走现有 PUT 接口以保留审计 |

---

## 5. 文件动作矩阵（要动 / 不能动 / 可选）

### 要动（实现阶段）
1. `route_registry.json` —— 加 1 条 `/ext` 路由（配置）。
2. `shared_board/server.py` —— `db()` 加 notes 表；`do_GET` 加 6 个 `/api/ext/*` 读端点；`do_POST` 加 `/api/ext/notes`。**唯一代码改动，只增不改既有分支**。
3. `shared_board/board.db` —— AC-1.5 状态补标 done（数据，经 PUT 接口或一次性 SQL）。

### 不能动
1. **`agnes_proxy.py`** —— 零代码改动（已核实 `_proxy_route` 支持 /ext/→/api/ext/ 改写 + token 注入 + X-Agent 透传）。
2. `short_drama_workflow/*`（生成链/云API）、`hub.html`/门户首页 —— 边界外，不碰。
3. 现有 `/api/*` 处理分支与注册表既有 33 条路由 —— 只增不改。
4. 不新增端口；不新增鉴权代码（老板决策统一后置）。

### 可选（跟进项，需主理人拍板）
- `shared_board/index.html` —— 独立「指导留言」栏（渲染 `GET /api/ext/notes`）；不做则 AC-1.3 由现有审计流满足。
- 门户首页 `/api/hub/status` 卡片显示 /ext 状态 —— 本任务不需要。

---

## 6. 实现阶段执行清单（供后续参考，非本阶段动作）

1. `git commit before:`（动 server.py / route_registry.json 前留档）。
2. `route_registry.json` 加 `/ext` 条目 → `python -m json.tool` 校验 → 干净重启 8787（杀残留 PID、核新 PID）。
3. `shared_board/server.py`：`db()` 加 notes 表；`do_GET`/`do_POST` 加端点 → 干净重启 8788（杀残留 PID、核新 PID）。
4. 冒烟（curl 8787）：`/ext/status`、`/ext/projects`、`/ext/tasks?project_id=19`、`/ext/audit`、`/ext/presence`、`POST /ext/notes`（无 token）→ 全部 200；再验证 `/ext/notes` 写库 + 审计流可见。
5. AC-1.5：按 current_state.md 清单补标 board 任务 done（至少 #26）。
6. 回归：确认 `/board`、`/studio`、`/api/*` 现有路径不受影响。
