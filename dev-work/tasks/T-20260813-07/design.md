# T-20260813-07 开发设计 · 看板 5 态中文 + /docs 说明页 + 校验 400 + 注册表热加载

- **版本**：v1 ｜ 2026-08-13 ｜ 开发（寇豆码）出稿，待主理人双审
- **依据**：`PRD.md`（AC-1.1~1.7，老板 18:52 签闸）+ `看板改造方案_20260813.md`（v3 §2.3/2.5/2.6/2.7）
- **性质**：**设计稿，只读调研结论 + 改动设计，不含业务代码实现**；实现阶段由开发按本设计落地。
- **调研基线**：git HEAD `aadb6e8`（T-05 验收闭环）；`git status` 现存未提交变更 = `board.db`（T-05 AC-1.5 补标 done 的残留）+ 方案/README 文档改动——实现前先 `git commit before` 留档（见 §7）。

---

## 0. 设计结论一句话

把 board 状态从「英文 4 态」一次性迁移为「中文 5 态 + 阻塞旁路」：**先备份迁移存量 → 再上服务端校验（400）→ 前端/脚本/技能全中文化 → 新增 GET /docs 说明页 → 8787 注册表改为 mtime 惰性热加载（冲突拒绝沿用旧路由）**，一次干净重启生效，不破坏既有 /ext、/studio、/board 功能。

---

## 1. 背景与目标

- 现状：board 状态为英文 `todo/doing/blocked/done`，与 dev-work 验收链中文语义不对齐；`/ext/status` 在途过滤 `!= 'done'`（`server.py:177`）在迁移中文后将**恒真**，在途统计全量爆表（K1）。
- 目标（对应 PRD 四块）：
  1. 状态机统一**中文 5 态**（待办/进行中/待验证/已验证/完成，阻塞=旁路），存量一次迁移；
  2. **GET /docs** 网页 API 说明页（本地 8788 + 外部经 8787）；
  3. **服务端校验 400**（title 非空、priority/status 枚举），防脏数据回潮；
  4. **8787 注册表热加载**（mtime 惰性重载，冲突拒绝沿用旧路由）。
- 约束：只动 PRD 产出路径文件；不碰生成链 / studio 业务逻辑 / /ext 端点语义（status 返回中文即可）；不引入新依赖；迁移前备份；改 server.py/agnes_proxy.py 前 git commit before。

---

## 2. 现状核查（只读调研 · 全部基于真实代码行号）

### 2.1 `shared_board/server.py`（8788 board 后端，329 行）

| 位置 | 现状 | 与本任务关系 |
|---|---|---|
| L80 | `status TEXT DEFAULT 'todo'`（tasks 建表默认） | 改 `'待办'`（仅对新建表生效；存量靠迁移 §3.4） |
| L131-143 | `do_GET` 处理 `/`、`/index.html`（读文件 + 注入令牌） | 在此分支后新增 `GET /docs` 分支（§3.1-D） |
| L156-159 | `GET /api/tasks?project_id=` 直接返回 db 原始 status | **无需改**：迁移后自然返回中文（AC-1.1） |
| L174-185 | `GET /api/ext/status`；L176-178 `in_flight` 查询 **`WHERE status<>'done'`** | **K1 必改**（§3.1-C） |
| L186-225 | `/api/ext/projects|tasks|audit|presence|notes`（T-05 新增） | **不动**（边界） |
| L241-251 | `POST /api/tasks`：L245 `pri=d.get("priority") or "中"`；L247 插入 `d.get("status","todo")` | 新增校验 + 默认值改 `'待办'`（§3.1-B） |
| L290-302 | `PUT /api/tasks/<id>`：L294-296 字段白名单 `title/detail/status/author/priority` | 新增部分字段校验（§3.1-B） |
| L119-121 | `body()` 解析 JSON | 校验函数建议插在 L121 之后、`class H`（L123）之前 |

### 2.2 `shared_board/index.html`（K4 前端 status 全引用点）

全文件核查（grep `status|todo|doing|done|blocked`）：**index.html 没有状态过滤下拉、没有状态统计栏**——"过滤/统计"引用点在 `check_wip.ps1` 与 `/ext/status`（另述）。本文件需改的引用点共 **5 处**：

| 行号 | 现状 | 改法 |
|---|---|---|
| L24-27 | CSS `.todo/.doing/.blocked/.done` 四种徽章配色 | 改为按中文状态配色的属性选择器（§3.3-A） |
| L78-80 | 抽屉状态下拉：`<option value="todo">待办</option>…`（4 项英文 value） | 6 项中文 value（5 态 + 阻塞）（§3.3-B） |
| L102 | `const ST={todo:"待办",doing:"进行中",blocked:"阻塞",done:"完成"};`（英文→中文映射层） | **删除**（映射层移除）（§3.3-C） |
| L168 / L176 | `saveDrawer` 取 `d_status.value`；`openDrawer` 回填 `curTask.status` | **零改动自动适配**（下拉 value 改中文后闭环） |
| L193 | `build()` 徽章：`b.className="badge "+t.status; b.textContent=ST[t.status]` | 改为 `textContent=t.status` 直显中文 + data-status 配色（§3.3-D） |

### 2.3 `short_drama_workflow/ops/check_wip.ps1`（72 行）

| 位置 | 现状 | 改法 |
|---|---|---|
| L1 | 注释「统计 board 项目 doing 任务数」 | 改「在途 = 进行中+待验证+已验证」 |
| L57-61 | `$doing = @($tasks | Where-Object { $_.status -eq "doing" … })` | 改为三态集合匹配（§3.5） |
| L64-71 | 判定/输出用 `$doing` / `$n` | 变量改名 `$wip`（保持退出码 0/1 语义不变） |
| L6 注释 | 「文件必须保存为 UTF-8 with BOM」 | **实现时保持 BOM**（PowerShell 5.1 无 BOM 中文乱码，铁律） |

### 2.4 `agnes_proxy.py`（8787 网关，846 行）

| 位置 | 现状 | 与本任务关系 |
|---|---|---|
| L63-86 | `_BOARD_TOKEN_CACHE` + `_board_token()`：**mtime 惰性读取先例**（stat→一致直接返回→不一致重读→缓存 val+mtime） | **热加载照抄此模式**（§5） |
| L142 | `ROUTE_REGISTRY_FILE = route_registry.json` | 不变 |
| L144-156 | `RouteRegistryError` + `_find_prefix_conflict`（路径段感知前缀冲突检测） | 复用 |
| L158-198 | `_load_route_registry()`：读文件→校验结构→全量校验前缀冲突→返回 routes 或 None/抛错 | 复用 |
| L200-203 | **模块顶层只读一次**：`_ROUTE_REGISTRY = _load_route_registry()`；冲突 `raise SystemExit`（启动即报错） | 保留启动 fail-fast；新增运行时惰性 getter（§5） |
| L212-219 | `_route_for()` 引用全局 `_ROUTE_REGISTRY` | 改调 `_get_route_registry()` |
| L377-397 | `_route_dispatch()` 引用 `_ROUTE_REGISTRY is not None` | 改调 `_get_route_registry()` |
| L818-821 | `__main__` 打印路由数引用 `_ROUTE_REGISTRY` | 改调 getter（或保留启动值，等价） |

### 2.5 `~/.workbuddy/skills/board/SKILL.md`（39 行）

| 位置 | 现状 | 改法 |
|---|---|---|
| L34 | `- 状态：todo 待办 / doing 进行中 / blocked 阻塞 / done 完成` | 改中文 5 态 + 阻塞旁路 + 在途三态口径（§3.6） |
| L17-18 | 建任务/改状态动词示例（`{"status":, …}`） | 补中文 status 示例（如 `"status":"进行中"`） |
| L36 | 派单标准动作「用 PUT 更新状态」 | 状态值改中文；补校验规则提示（非法 400） |

### 2.6 `shared_board/board.db` 存量实测（只读查询）

```
tasks 表：20 行 = 'todo' 10 + 'done' 10；NULL status 0；无 doing/blocked
project 19（短剧自动化工作流/阿编）= 12 行：'done' 10 + 'todo' 2
projects：id4 看板项目(kanban) / id18 测试项目(老板) / id19 短剧自动化工作流(阿编)
notes：3 条；audit：24 条
```

- 迁移影响面 = **20 行**（todo→待办 10，done→完成 10；doing/blocked 当前为 0，但迁移 SQL 仍全量覆盖以防将来残留）。
- 迁移后 AC-1.1 期望：`GET /api/tasks?project_id=19` 返回 12 行，status 全为中文（完成 10 + 待办 2）。

### 2.7 影响面扫描 + `/ext/docs` 路径澄清（重要）

**A. 英文 status 消费方全量扫描**（仓库内 `*.{py,ps1,js,ts,html,md}`）：

| 消费方 | 位置 | 处置 |
|---|---|---|
| board `/ext/status` 在途过滤 | `server.py:177` | **K1 必改**（§3.1-C） |
| board 前端下拉/映射/徽章 | `index.html:79-80/102/193` | 改中文（§3.3） |
| check_wip 统计 | `check_wip.ps1:59` | 改三态（§3.5） |
| studio.html `s.status==='done'`（L857/1118/1752/2503/2591） | **工作台 job/shots 状态（pending/running/done）**，与 board tasks 状态是**两个独立域** | **不碰**（边界；本次迁移仅 board tasks 表） |
| T-05 文档（test.md L148 / design.md L141）钉死 `in_flight = status != 'done'` | 历史验收契约 | **被本任务显式取代**（K1 破例理由，§3.1-C 与 §9） |

除上述外**无其它代码消费 board 英文 status**——迁移 + 校验上线后影响面封闭。

**B. `/ext/docs` 不可达（PRD 表述修正）**：
- 现有注册表 `/ext` 路由（`route_registry.json:247-255`，target=`8788/api/ext`）：`/ext/docs` → 改写为 `8788/api/ext/docs` → board 无此端点 → **404**。
- 现有 `/board` 路由（`route_registry.json:229-238`）：`_proxy_board`（`agnes_proxy.py:535-538`）对 `/board/docs` 取 `raw[len("/board"):]="/docs"` → 转发 `8788/docs` → **200 ✅**。
- **设计决定：外部 /docs 规范路径 = `/board/docs`（零新增注册表条目）**；`/ext/docs` 不实现、不承诺（避免污染 /ext 语义）。AC-1.3 按本地 `8788/docs` + 外部 `8787/board/docs` 验收。此为本设计对 PRD「或 /ext/docs 可达」表述的**事实澄清**，非能力新增。

---

## 3. 改动点清单（文件 × 位置 × 改法）

### 3.1 `shared_board/server.py`

**A. 枚举常量**（建议插在 L37 `def now()` 前，与其它模块常量并列）：
```python
STATUS_ENUM = {"待办", "进行中", "待验证", "已验证", "完成", "阻塞"}   # 阻塞=旁路态，可提交
PRIORITY_ENUM = {"紧急", "高", "中", "低"}
```

**B. 校验函数 + 接入 POST/PUT**（校验函数建议插在 L121 `body()` 之后、`class H`（L123）之前）：
```python
def validate_task_fields(d, partial=False):
    """POST(partial=False)：title 必填；PUT(partial=True)：仅校验请求中出现的字段。
    返回 None（通过）或中文错误串；调用方包成 400 {"error": <串>}。"""
    if "title" in d or not partial:
        if not isinstance(d.get("title"), str) or not d.get("title", "").strip():
            return "title 不能为空"
    if "priority" in d and d["priority"] not in PRIORITY_ENUM:
        return "priority 非法，允许: 紧急/高/中/低"
    if "status" in d and d["status"] not in STATUS_ENUM:
        return "status 非法，允许: 待办/进行中/待验证/已验证/完成/阻塞"
    return None
```
- **POST `/api/tasks`（L241-251）**：在 `allowed` 检查后、INSERT 前插入：
  ```python
  err = validate_task_fields(d, partial=False)
  if err: send(self, 400, {"error": err}); c.close(); return
  ```
  且 L247 `d.get("status", "todo")` → `d.get("status", "待办")`。
- **PUT `/api/tasks/<id>`（L290-302）**：在字段白名单组装前插入：
  ```python
  err = validate_task_fields(d, partial=True)
  if err: send(self, 400, {"error": err}); c.close(); return
  ```
- 其它写端点（POST /api/projects、POST /api/ext/notes、PUT /api/projects、DELETE）**不新增校验**（超出 PRD 范围）。

**C. K1 · `/ext/status` 在途过滤**（L176-178）：
```python
# 改前（L177）：
FROM tasks WHERE status<>'done'
# 改后：
FROM tasks WHERE status IN ('进行中','待验证','已验证')
```
- **破例理由（对 PRD「不碰 /ext 语义」边界的必要破例）**：
  1. 迁移后所有 status 均为中文，`<>'done'` 对任何值恒真 → in_flight 变成「全量任务」，统计爆表——不改则 /ext/status 语义**实质性损坏**；
  2. T-05 契约（`test.md:148` WARN-2）当初以「未来 review/verify 态自动纳入」假设 `!= 'done'`，中文迁移使该假设失效（`完成` ≠ `'done'`），**契约前提已被 PRD 本身推翻**（老板 18:52 已签含 §2.3 在途三态的完整方案）；
  3. 新口径与 `check_wip.ps1` 在途三态（进行中+待验证+已验证）**完全一致**，排除「待办（未开工）」与「阻塞（旁路）」，语义更准确。
- 改的是**过滤字符串**，不动端点集合 / 响应结构 / 字段名——对 /ext 的侵入最小化。

**D. `GET /docs` 路由**（`do_GET`，插在 L133-143 index.html 分支之后、`c = db()`（L144）之前）：
```python
if self.path in ("/docs", "/docs.html"):
    with open(os.path.join(HERE, "docs.html"), "rb") as f:
        html = f.read()
    self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
    self.send_header("Cache-Control", "no-store")
    self.end_headers(); self.wfile.write(html); return
```
- 只读 GET，无需令牌、无需注入 `__BOARD_TOKEN__`。
- **E. 默认值**：L80 `status TEXT DEFAULT 'todo'` → `'待办'`（新建库生效）；L247 同（见 B）。

### 3.2 `shared_board/docs.html`（新增）

- 纯静态中文 HTML，**零 JS API 依赖**（示例放 `<pre>` 文本，不做可点击 API 链接，避免 8787 经 /board/docs 时 `/api/` 不被代理改写导致指向 studio 8777 的歧义）。
- 内容清单见 §6。实现后本地 `8788/docs`、外部 `8787/board/docs` 均 200。

### 3.3 `shared_board/index.html`

- **A（L24-27 CSS 配色）**：删除 `.todo/.doing/.blocked/.done`，改为属性选择器（避免中文类名在 CSS 标识符的边界风险，同时彻底移除映射层）：
  ```css
  .badge[data-status="待办"]{background:#f3f4f6;color:#6b7280}
  .badge[data-status="进行中"]{background:#dbeafe;color:#1d4ed8}
  .badge[data-status="待验证"]{background:#fef9c3;color:#a16207}
  .badge[data-status="已验证"]{background:#e0e7ff;color:#4338ca}
  .badge[data-status="完成"]{background:#dcfce7;color:#16a34a}
  .badge[data-status="阻塞"]{background:#fee2e2;color:#dc2626}
  ```
- **B（L78-80 下拉）**：6 项，value 即中文：
  ```html
  <option value="待办">待办</option><option value="进行中">进行中</option>
  <option value="待验证">待验证</option><option value="已验证">已验证</option>
  <option value="完成">完成</option><option value="阻塞">阻塞</option>
  ```
- **C（L102）**：删除 `const ST={...}` 整行。
- **D（L193）**：`b.className="badge "+t.status; b.textContent=ST[t.status];` →
  ```js
  const b=document.createElement("span"); b.className="badge"; b.dataset.status=t.status; b.textContent=t.status;
  ```
- L168/L176 自动适配（value 中文 ↔ status 中文），**零改动**。

### 3.4 `shared_board/board.db` 存量迁移（K3）

- **备份路径**：`shared_board/board.db.bak-YYYYMMDD-HHMMSS`（同目录、带时间戳；实现时取实际执行时刻，如 `board.db.bak-20260813-213000`）。
- **迁移工具**：新增一次性幂等脚本 `shared_board/migrate_status_zh.py`（纯 sqlite3 标准库；属 board.db 迁移配套运维工具，非业务代码；幂等可重跑，作为证据留档）。若主理人希望严格卡 PRD 产出路径，可改用文档化 `python -c` 内联执行——**推荐前者**（可重复、可留证）。
- **SQL 映射**：
  ```sql
  UPDATE tasks SET status='待办' WHERE status='todo';
  UPDATE tasks SET status='进行中' WHERE status='doing';
  UPDATE tasks SET status='阻塞' WHERE status='blocked';
  UPDATE tasks SET status='完成' WHERE status='done';
  -- 兜底：任何非 5 态(+阻塞) 残留（含历史乱值/NULL）归位待办
  UPDATE tasks SET status='待办' WHERE status IS NULL OR status NOT IN ('待办','进行中','待验证','已验证','完成','阻塞');
  ```
- **迁移后验证**：`SELECT status, COUNT(*) FROM tasks GROUP BY status` → 期望全中文（当前基数：待办 10 / 完成 10）。
- **顺序**：见 §7（备份→迁移→验证→再上校验）。

### 3.5 `short_drama_workflow/ops/check_wip.ps1`

```powershell
# L1 注释改：WIP 机械检查：统计 board 项目在途任务数（进行中+待验证+已验证），超阈值红卡拦截
# L57-61 改：
$wipStates = @("进行中", "待验证", "已验证")
$wip = @($tasks | Where-Object {
    $wipStates -contains $_.status -and ($Owner -eq "" -or $_.author -eq $Owner)
})
$n = $wip.Count
```
- L64-71 的 `$doing` 输出块同步改名 `$wip`（退出码 0/1 语义不变；PowerShell 5.1 支持 `-contains`）。
- **保存必须保持 UTF-8 with BOM**（PowerShell 5.1 按 ANSI 解析无 BOM 文件会中文乱码——L6 注释已警示）。

### 3.6 `~/.workbuddy/skills/board/SKILL.md`

- L34 改：
  ```
  - 状态（中文 5 态 + 阻塞旁路）：待办 / 进行中 / 待验证 / 已验证 / 完成；阻塞（旁路态，可提交）。
  - 在途口径（check_wip 统计）：进行中 + 待验证 + 已验证。
  - 服务端校验（非法 400）：title 非空；priority ∈ {紧急,高,中,低}；status ∈ 上述枚举。提交英文/乱值会被 400 拒绝。
  ```
- L17-18 示例补中文 status（如 `PUT /api/tasks/<id> {"status":"进行中",...}`）。
- L36 标准动作措辞同步（状态值全中文）。

### 3.7 `agnes_proxy.py`（热加载，详见 §5）

- 新增 `_ROUTE_REGISTRY_CACHE` + `_get_route_registry()`（照抄 `_BOARD_TOKEN_CACHE` L63-86 模式）；`_route_for`（L212）、`_route_dispatch`（L377）、`__main__` 打印（L818）改调 getter；模块顶层 L200-203 启动 fail-fast 保留并**播种缓存**（避免首请求重复读）。

---

## 4. 5 态枚举与校验规则设计

### 4.1 枚举（最终态）

| 状态 | 含义 | 在途？ |
|---|---|---|
| 待办 | 已建卡未开工 | 否 |
| 进行中 | 正在执行 | **是** |
| 待验证 | 产出待独立验证（对齐 dev-work 验收链） | **是** |
| 已验证 | 验证通过待收尾 | **是** |
| 完成 | 已闭环 | 否 |
| 阻塞（旁路） | 卡点挂起，可提交 | 否 |

### 4.2 校验规则

| 接口 | 字段 | 规则 | 违规响应 |
|---|---|---|---|
| POST `/api/tasks` | title | 必填，非空字符串（strip 后） | 400 `{"error":"title 不能为空"}` |
| | priority | ∈ {紧急,高,中,低}；缺省 `中` | 400 `{"error":"priority 非法，允许: 紧急/高/中/低"}` |
| | status | ∈ 5 态+阻塞；缺省 `待办` | 400 `{"error":"status 非法，允许: 待办/进行中/待验证/已验证/完成/阻塞"}` |
| PUT `/api/tasks/<id>` | title/priority/status | **仅校验请求中出现的字段**（部分更新） | 同上（按出现字段） |

- 校验顺序：`allowed`(403) → `validate_task_fields`(400) → 写库；校验失败不写库、不记审计。

### 4.3 错误信息

- 全部中文、给出允许枚举，客户端可自查修正（PRD 要求"错误信息明确"）。

---

## 5. 热加载设计（agnes_proxy.py）

### 5.1 mtime 惰性重载（照抄 `_BOARD_TOKEN_CACHE` 模式，L63-86）

```python
# 新增（放在 _load_route_registry 定义 L198 之后）：
_ROUTE_REGISTRY_CACHE = {"val": None, "mtime": None, "error": None}

def _get_route_registry():
    """mtime 惰性重载 route_registry.json（照抄 _board_token L63-86）：
    - 每次调用 stat mtime，与缓存一致直接返回（stat 一次，开销可忽略，秒级生效）；
    - 不一致才重新 _load_route_registry()；
    - 冲突(RouteRegistryError) → 拒绝加载、沿用旧路由（原子性：要么全新要么全旧）；
    - 解析失败/空 routes → 返回 None（回退硬编码白名单，兼容不崩）。"""
    try:
        mt = os.path.getmtime(ROUTE_REGISTRY_FILE)
    except OSError:
        return _ROUTE_REGISTRY_CACHE["val"]
    if _ROUTE_REGISTRY_CACHE["mtime"] == mt:
        return _ROUTE_REGISTRY_CACHE["val"]
    try:
        routes = _load_route_registry()
    except RouteRegistryError as e:
        if _ROUTE_REGISTRY_CACHE["error"] != str(e):
            print("[route_registry] 热加载冲突，沿用旧路由：%s" % e)   # 只打一次防刷屏
        _ROUTE_REGISTRY_CACHE["error"] = str(e)
        _ROUTE_REGISTRY_CACHE["mtime"] = mt
        return _ROUTE_REGISTRY_CACHE["val"]                            # 旧路由继续可用
    _ROUTE_REGISTRY_CACHE["val"] = routes
    _ROUTE_REGISTRY_CACHE["mtime"] = mt
    _ROUTE_REGISTRY_CACHE["error"] = None
    if routes is not None:
        print("[route_registry] 热重载成功：%d 条路由" % len(routes))
    return routes
```

- **引用点替换**：`_route_for`（L212-219）首行改 `reg = _get_route_registry(); if reg is None: return None` 后遍历 `reg`；`_route_dispatch`（L377）改 `if _get_route_registry() is not None:`（避免重复 get，可先取局部变量）；`__main__` L818 改调 getter。
- **启动播种**：保留 L200-203 模块顶层加载（冲突仍 fail-fast SystemExit，维持现行为）；成功后将 `_ROUTE_REGISTRY` 播种进 `_ROUTE_REGISTRY_CACHE`（val+mtime），首请求零重读。

### 5.2 冲突拒绝 + 原子性

- 冲突检测复用 `_find_prefix_conflict`（L147-156，路径段感知：`/api` 与 `/api/spec` 冲突；`/api/log` 与 `/api/logs` 不冲突）。
- **原子性保证**：`_load_route_registry()` 先**全量**解析 + 校验，成功才返回完整 routes 列表；`_get_route_registry` 仅在成功后一次性赋值 `_ROUTE_REGISTRY_CACHE["val"]`（单 dict 字段赋值，Python GIL 下原子）。任何失败（冲突/解析/空）→ 缓存保持旧值 → **要么全新要么全旧，不存在半套路由**。
- 单个请求在 `_route_dispatch` 入口取一次 registry，请求内一致；并发请求各自取，旧请求用旧、新请求用新，无跨请求撕裂。

### 5.3 边界

- 热加载只覆盖**声明式路由变更**（route_registry.json 加/改 prefix+target+kind+flags）；**代码逻辑变更仍走干净重启**（工程铁律，PRD §四）。
- 秒级缓存说明：`os.path.getmtime` 每请求一次 stat，改文件后下一次请求即生效（毫秒~秒级）；同秒内连续两次改写可能漏检（写入 mtime 相同），属可容忍精度（PRD「缓存秒级」）。

### 5.4 AC-1.6 测试路由生命周期（K2 用后即删）

1. **加入**：`route_registry.json` routes 数组临时加一条：
   ```json
   {"prefix": "/hotreload-test", "target": "http://127.0.0.1:9", "kind": "generic", "flags": {}, "note": "AC-1.6 热加载验收用，验收后必须移除"}
   ```
2. **生效验证**（不重启 8787）：保存后 ≤5 秒内 `curl -s -o NUL -w "%{http_code}" http://127.0.0.1:8787/hotreload-test` 由 **404**（未命中注册表→兜底 unknown path）变为 **502/503**（命中注册表→转发 127.0.0.1:9 不可达→`_proxy_route` 抛 503「路由目标不可达」）——状态码变化即热加载生效证据。
3. **冲突验证**：临时把该条目 prefix 改成 `/board`（与现有 /board 冲突）→ 保存 → 8787 **不崩**、`/board` 仍 200（旧路由沿用）、日志出现「热加载冲突」。
4. **K2 移除**：验收通过后**立即删除测试路由**，恢复 route_registry.json 至提交态；验证 `git diff route_registry.json` 干净（无残留废路由），并留证据。

---

## 6. /docs 页面内容清单

`docs.html`（静态中文 HTML）应包含：

1. **页头**：看板 API 说明页 · 访问路径（本地 `http://<IP>:8788/docs`；外部经网关 `http://agnes.owen1.de5.net/board/docs`）。
2. **状态枚举**：待办 / 进行中 / 待验证 / 已验证 / 完成；阻塞（旁路，可提交）；附「在途 = 进行中+待验证+已验证」。
3. **优先级枚举**：紧急 / 高 / 中 / 低。
4. **校验规则**：title 非空、priority/status 枚举；非法 → 400 + 错误信息示例（同 §4.3）。
5. **端点表**（本地路径 + 网关路径双列）：

   | 方法 | 本地（8788） | 网关（8787） | 说明 | 必带 |
   |---|---|---|---|---|
   | GET | `/api/projects[?owner=]` | `/board/api/projects` | 项目列表 | - |
   | GET | `/api/tasks?project_id=N` | `/board/api/tasks?project_id=N` | 任务树 | project_id |
   | GET | `/api/presence` | `/board/api/presence` | 在线状态 | - |
   | GET | `/api/audit[?project_id=N]` | `/board/api/audit` | 操作日志 | - |
   | GET | `/api/ext/status` | `/ext/status` | 总览（全部项目+在途+最近审计8条） | - |
   | GET | `/api/ext/projects` | `/ext/projects` | 项目列表 | - |
   | GET | `/api/ext/tasks?project_id=N` | `/ext/tasks?project_id=N` | 任务树 | project_id |
   | GET | `/api/ext/audit[?project_id=N]` | `/ext/audit` | 操作日志 | - |
   | GET | `/api/ext/presence` | `/ext/presence` | 在线状态 | - |
   | GET | `/api/ext/notes[?project_id=N]` | `/ext/notes` | 指导留言列表 | - |
   | POST | `/api/tasks` | `/board/api/tasks` | 建任务 | title, priority, project_id |
   | PUT | `/api/tasks/<id>` | `/board/api/tasks/<id>` | 改任务 | 至少一个字段 |
   | DELETE | `/api/tasks/<id>` | `/board/api/tasks/<id>` | 删任务 | - |
   | POST | `/api/ext/notes` | `/ext/notes` | 远程留言 | project_id, text |
   | POST | `/api/projects` | `/board/api/projects` | 建项目 | name |

6. **curl 示例**（三种身份路径，示例为文本 `<pre>`，不做可点击链接）：
   - 本地写（带 `X-Agent` + `X-Board-Token`）：
     ```
     curl.exe -H "X-Agent: 阿编" -H "X-Board-Token: <TOKEN>" -X POST http://127.0.0.1:8788/api/tasks -H "Content-Type: application/json" -d "{\"project_id\":19,\"title\":\"新任务\",\"priority\":\"高\",\"status\":\"待办\"}"
     ```
   - 本地读（GET 免 token）：`curl.exe http://127.0.0.1:8788/api/tasks?project_id=19`
   - 经网关看板路径（代理自动注入 token）：`curl.exe -H "X-Agent: 阿编" http://127.0.0.1:8787/board/api/tasks?project_id=19`
   - 外部指导（`/ext` 免鉴权）：`curl.exe http://127.0.0.1:8787/ext/status`
   - 令牌来源：`shared_board/.env` 的 `BOARD_TOKEN`。
7. **身份与规则**：`X-Agent` 身份头；owner 写锁（改他人项目 → 403）；审计自动记录（带 X-Agent 的读写留痕）；老板豁免；外部经 8787 代理自动注入 token。

---

## 7. 实施顺序（K3：备份→迁移存量→再上校验）

```
[0] git commit before：先提交当前未提交变更（board.db 的 T-05 残留 + 文档），
    使迁移前 board.db 状态进入 git 历史；再开始本任务改动。
[1] 停 8788（干净停：Get-CimInstance Win32_Process 按 CommandLine 杀残留，确认无 LISTEN）
[2] 备份 board.db → board.db.bak-<YYYYMMDD-HHMMSS>（校验文件存在且大小>0）
[3] 跑 migrate_status_zh.py（§3.4 SQL 映射 + 兜底）
[4] 验证：SELECT status,COUNT(*) GROUP BY status → 全中文，英文 0 残留
[5] 部署 server.py（校验+默认值+/docs）+ docs.html + index.html
[6] 起 8788（新 PID 绑定核实）→ 自测：/docs 200、/api/tasks 中文、非法 POST→400、合法→200
[7] 部署 agnes_proxy.py（热加载）→ 停 8787 → 起 8787（新 PID 绑定核实）
[8] AC-1.6 热加载验收：加测试路由→生效→冲突→拒绝→【移除测试路由】→ git diff 干净
[9] AC-1.7 回归：/ext 6 端点、/studio、/board、/board/docs、根路径全 200
[10] 证据收集：git diff 文件清单 + py_compile 三文件 + 自测命令输出 + 备份文件 + 热加载 dry-run
```

- 为什么校验上线（步骤 5-6）必须在迁移（步骤 3-4）之后：若先上校验，存量英文数据在迁移前仍躺在库里，而任何尝试以英文状态写库的新请求会被 400 挡——虽然迁移本身是直连 SQL 不受 API 校验影响，但按 K3 明确顺序执行可保证**边界上不存在英文数据与校验共存窗口**，且避免「迁移未跑、校验已开」的中间态混乱。

---

## 8. AC 映射（AC-1.1 ~ 1.7）

| AC | 验收点 | 本设计如何满足 |
|---|---|---|
| AC-1.1 | `GET /api/tasks?project_id=19` 全部 status 中文 5 态（无英文残留） | §3.4 存量迁移（todo→待办/doing→进行中/done→完成/blocked→阻塞 + 兜底归位）＋ §3.1-A/E 枚举与默认值 `'待办'`（新增数据天然中文）＋ §3.1-B 校验（英文/乱值 400，防回潮）。期望：12 行 = 完成 10 + 待办 2（§2.6 实测基数） |
| AC-1.2 | POST 非法 status（如 `todo`）/缺 title → 400 且错误明确；合法 → 200 | §4 校验函数：缺 title → `{"error":"title 不能为空"}`；status=`todo` → `{"error":"status 非法，允许: 待办/进行中/待验证/已验证/完成/阻塞"}`；合法提交 → 200（写库 + 审计） |
| AC-1.3 | `GET /docs` 本地 + 外部（`/board/docs`）均 200，页面含枚举/端点/示例/规则 | §3.1-D 路由（`/docs`、`/docs.html`）+ §3.2 docs.html + §6 内容清单。外部路径按 §2.7-B 修正为 `/board/docs`（`/ext/docs` 不成立，已澄清） |
| AC-1.4 | check_wip.ps1 对「进行中/待验证/已验证」计数正确 | §3.5 三态集合匹配。QA 构造样例：N×进行中 + M×待验证 + K×已验证 → 计数 = N+M+K；doing 旧值不计数 |
| AC-1.5 | 存量迁移后 db 英文 0 残留；迁移前有备份 | §3.4：备份 `board.db.bak-<ts>` + SQL 映射 + 兜底；§7 步骤 2-4 顺序与验证查询。证据：备份文件 + 迁移前后 `GROUP BY status` 输出 |
| AC-1.6 | 注册表热加载：加测试路由 → 不重启 8787 → 5 秒生效；冲突 → 拒绝且旧路由继续可用 | §5 全部 + §5.4 测试路由生命周期。K2：测试路由**验收后移除**（§5.4-4），防残留废路由 |
| AC-1.7 | 回归：现有 /ext 6 端点、/studio、/board、根路径全 200 | §9 回归清单；K1 的 /ext/status 仅收窄 in_flight 内容（语义修正），端点/响应结构/200 不变；/studio、/board、根路径零改动 |

---

## 9. 风险与回滚

### 9.1 迁移失败回滚
- **回滚方案**：停 8788 → `Copy-Item board.db.bak-<ts> board.db -Force` 恢复 → 起 8788 → 复查 `GROUP BY status`。
- 迁移 SQL 幂等且只改已知英文值，失败概率低；步骤 2 强制校验备份存在（大小 >0）后才执行步骤 3。
- 代码回滚：改动前 `git commit before`（§7-0），`git checkout -- server.py / agnes_proxy.py / index.html` 可整文件回退。

### 9.2 热加载竞态风险
- **同秒双写漏检**：`getmtime` 秒级精度，同秒内文件被写两次且首读读到中间态 → 可能沿用旧路由直到下次 mtime 变化。缓解：编辑器保存通常产生新 mtime；冲突/解析失败已缓存 mtime 防刷屏，下次改动即重试。已登记为可容忍精度（PRD「缓存秒级」）。
- **解析失败窗口**：文件被非原子写坏 → `_load_route_registry` 返回 None → 回退硬编码白名单（board/studio 仍可用）→ 新注册表路由暂失效，直到文件修复后 mtime 变化触发重载。属兼容不崩设计（现状 L200 亦如此）。
- **并发一致性**：单请求取一次 registry，请求内一致；dict 赋值原子 → 无半套路由。

### 9.3 K1 `/ext` 在途过滤改动的影响面
- 语义变化：`in_flight_tasks` 从「非完成（含待办/阻塞）」收窄为「进行中+待验证+已验证」。
- 影响对象：远程指导总览（`/ext/status`）——**内容变少是预期正确行为**（当前存量在途 = 0，总览在途为空属正确；未来任务推进到进行中才出现）。
- 已扫描确认：除 T-05 验收文档外**无程序化消费者**依赖 `!= 'done'` 语义（§2.7-A）。
- 契约取代：T-05 `test.md:148` WARN-2 钉死的 `status != 'done'` 被本任务**显式取代**，理由见 §3.1-C（老板已签完整方案）。

### 9.4 校验上线对旧调用方的影响
- 仍以英文/乱值写 status 的旧客户端（未更新的 agent 记忆、旧脚本）会收到 400。缓解：SKILL.md（§3.6）同步中文约定 + /docs 页面公开校验规则；400 错误信息自带允许枚举，客户端可自查。属预期行为变化，风险登记。

### 9.5 中文编码风险
- `check_wip.ps1` 必须保持 **UTF-8 with BOM**（PowerShell 5.1）；`server.py`/`index.html`/`docs.html` 保持 UTF-8（现已是）。
- CSS 中文标识符风险 → 用 `data-status` 属性选择器规避（§3.3-A）。

### 9.6 干净重启纪律
- 8787/8788 均须杀残留 PID（`Get-CimInstance Win32_Process` 按 CommandLine 过滤）确认无 LISTEN 再起，核实新 PID 绑定（PRD 证据要求，防脏双进程 S1P0）。

### 9.7 回归清单（AC-1.7）
```
GET 8787/ext/status, /ext/projects, /ext/tasks?project_id=19, /ext/audit, /ext/presence → 200
POST 8787/ext/notes {"project_id":19,"text":"回归"} → 200（写库+审计可见）
GET 8787/studio, /studio/ → 200
GET 8787/board, /board/docs → 200
GET 8787/ (导航首页), /console → 200
GET 8788/docs, /api/tasks?project_id=19 → 200（status 全中文）
```

---

## 10. 坑覆盖自查（主理人审视 K1~K4）

| 坑 | 覆盖位置 |
|---|---|
| K1 `/ext/status` 在途过滤 `!= 'done'` 恒真 | §3.1-C 改为 `IN ('进行中','待验证','已验证')`；破例理由三条（§3.1-C / §9.3）；AC-1.1/AC-1.7 体现见 §8 |
| K2 热加载测试路由用后即删 | §5.4-4：验收后移除 + `git diff route_registry.json` 干净留证 |
| K3 迁移前备份 + 顺序（备份→迁移→再上校验） | §3.4 备份路径 `board.db.bak-<ts>`；§7 实施顺序 0-10；理由见 §7 尾注 |
| K4 前端全引用点 | §2.2 全文件核查 5 处（CSS L24-27 / 下拉 L78-80 / ST 映射 L102 / 抽屉 L168·176 / 徽章 L193）+ §3.3 逐一改法；并如实说明 index.html **无**过滤/统计引用点（在 check_wip 与 /ext/status） |

---

## 11. 自测与证据计划（实现阶段交付物）

- `py_compile` 三文件：`server.py`、`agnes_proxy.py`、（可选）`migrate_status_zh.py`。
- 迁移证据：`board.db.bak-<ts>` 备份文件 + 迁移前后 `SELECT status,COUNT(*)` 输出（英文 0 残留）。
- 校验自测：非法 POST（缺 title / status=todo / priority=乱值）→ 400 输出；合法 POST → 200。
- /docs 自测：`curl -s -o NUL -w "%{http_code}" http://127.0.0.1:8788/docs` 与 `http://127.0.0.1:8787/board/docs` → 200。
- check_wip 自测：构造 进行中/待验证/已验证 样例 → 计数正确（QA 独立构造亦可）。
- 热加载 dry-run：测试路由 404→503 → 冲突拒绝 → 移除测试路由 → `git diff route_registry.json` 干净。
- 回归：§9.7 清单全部 200。

---

## 12. 边界遵守与偏差记录

- **遵守**：只动 PRD 产出路径文件（server.py / docs.html 新增 / index.html / board.db+备份 / check_wip.ps1 / SKILL.md / agnes_proxy.py）；不碰生成链 / studio 业务逻辑 / /ext 端点集合与响应结构；不引入新依赖。
- **偏差/澄清**：
  1. **/ext/docs 不成立**（§2.7-B）：外部 docs 规范路径 = `/board/docs`，AC-1.3 按此验收——对 PRD「/board/docs 或 /ext/docs」表述的事实修正。
  2. **/ext/status 在途过滤必改**（§3.1-C）：对 PRD「不碰 /ext 语义」边界的必要破例，理由已列明（迁移使 `!= 'done'` 失效；口径与 check_wip 三态对齐）。
  3. **迁移工具文件**（§3.4）：新增 `migrate_status_zh.py` 一次性运维脚本（幂等），属 board.db 迁移配套；若主理人要求严格零新增文件，可改为内联 `python -c` 执行（设计已给 SQL，二选一）。
