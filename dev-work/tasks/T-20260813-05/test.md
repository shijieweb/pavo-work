# T-20260813-05 测试文档（test.md）· 看板外部指导 API（/ext/*）+ 状态对齐

> 分层：L1 真跑（本地 127.0.0.1 真实服务探测，零 AGNES 额度）；L0 仅做实现前基线核验 + 静态代码核验。
> 状态：**测试文档先行**（新流程）——本文档只描述计划/用例/判定，不执行任何改动；主理人审过后才进入测试执行。
> 铁律：本文档撰写阶段禁止写代码、禁止改文件、禁止重启服务；仅允许只读探测（已完成，见基线快照）。
> 契约来源：PRD `PRD.md` + 方案 v2 `dev-work/看板改造方案_20260813.md` + 开发设计 `design.md`（同目录，接口契约 §2 为准）。

---

## 〇、基线快照（2026-08-13 实现前 · QA 只读实测）

| 探测项 | 结果 | 说明 |
|---|---|---|
| `8787 /`、`/board` | 200 / 200 | 8787 网关在跑（schtasks AgnesPortal 托管） |
| `8788 /`、`/api/projects` | 200 / 200 | board 后端在跑 |
| `8787 /api/projects` | 200 | 现有工作台 API 路由正常（回归基线） |
| `8787 /ext/status`、`/ext/notes` | 404 | **/ext/* 未实现**（本次 AC 的起点，实现后应变 200） |
| `8788 /api/ext/status` | 404 | board 端 /api/ext/* 未实现（同上） |
| board.db 项目 | id 4 / 18 / 19 | 19 = 短剧自动化工作流（owner 阿编） |
| 项目 19 任务状态 | **8 done + 4 todo + 0 doing** | 与方案 v2 §2.1「现状失真」一致；#26 仍 todo（AC-1.5 待补标 done） |
| 任务 #26 | `l1_smoke.py固化进回归套件+KEY守卫assert` = todo | 对应 T-20260813-01（已闭环 commit 32fb6e8） |
| audit 表 | 共 19 条，项目 19 有记录 | /ext/status 取「最近 8 条」有足够数据 |
| presence 表 | 阿编 / 2026-08-13 00:29 | 非空 |
| `shared_board/.env`（BOARD_TOKEN） | **存在（已配置）** | ⚠️ 关键：board 写闸会 401；**8787 代理须注入 X-Board-Token**（design §1.1 flags.board_token_inject）才能零 token 直达 |

---

## 一、测试计划

### 1.1 分层选择

- **本任务全部 AC 为本地 HTTP 接口探测（curl 127.0.0.1），零 AGNES 额度 → 选 L1 真跑**。
- L0 dry-run 用途（实现完成后、真跑前先做，静态核验不依赖服务）：
  1. `route_registry.json` 已含 `/ext` 路由行（prefix=`/ext`，target=`http://127.0.0.1:8788/api/ext`，kind=generic，flags.board_token_inject=true），且 `python -m json.tool` 校验通过；
  2. `shared_board/server.py` 已含：`db()` 的 `notes` 表、`do_GET` 的 6 个 `/api/ext/*` 读端点、`do_POST` 的 `/api/ext/notes`（仍位于 `board_token_ok` 闸之后，依赖代理注入 token）；
  3. `shared_board/index.html` 现有审计流渲染 `#audit`（`[ts] agent action target`）——AC-1.3「前端可见」的最小闭环载体；
  4. 状态对齐：board #26 已补标 done（可先直连 8788 查库/查接口确认，作为 AC-1.5 前置）。
- 执行顺序：L0 静态核验 → 确认 8787/8788 在跑 → L1 真跑 5 组 AC + 回归 → 汇总判定。

### 1.2 环境准备

- **前置**：8787 网关 + 8788 board 均在跑（基线已确认）。若执行阶段服务掉线，需主理人/开发按工程铁律干净重启（杀残留 PID → 起新 PID 核实），QA 不自行重启。注意 design §3.4：**改注册表/改 server.py 后必须干净重启对应端口才生效**（`_ROUTE_REGISTRY` 模块导入时一次性加载）。
- **探测命令（PowerShell 注意）**：Windows PowerShell 中 `curl` 是 `Invoke-WebRequest` 别名，必须用 `curl.exe` 或 python urllib，避免误用别名导致输出格式异常。

```powershell
# 服务在位探测（L1 前必跑）
curl.exe -s -o NUL -w "8787=%{http_code}" http://127.0.0.1:8787/
curl.exe -s -o NUL -w "8788=%{http_code}" http://127.0.0.1:8788/
```

- **测试数据**：复用现有项目 id=19（短剧自动化工作流）；audit 现有 19 条足够支撑「最近 8 条」断言。
- **写测试的副作用处理**：AC-1.3 的 POST /ext/notes 会真实写库（notes + audit）。测试用**唯一标记文本**（如 `QA-TEST-<时间戳> 远程指导留言`），测后不删除（留审计铁证），并在 current_state 交接区注明该条为测试留言，避免前端误读。

### 1.3 测试工具

| 工具 | 用途 |
|---|---|
| curl.exe | 接口探测（GET/POST，含 -w 输出状态码） |
| python（标准库 urllib / sqlite3） | JSON 字段断言、只读查库佐证 |
| `short_drama_workflow/scripts/route_diff_test.py` | 回归（注册表全路由 GET/PUT/DELETE） |

---

## 二、逐 AC 测试用例

> 字段名以 design.md §2 接口契约为准（非编造）：/ext/status 返回 `projects / in_flight_tasks / recent_audit / generated_at`；/ext/projects、/ext/tasks、/ext/audit、/ext/presence 复用现有 /api/* 字段；错误统一 `{"error":"..."}`。

### AC-1.1 `GET /ext/status` → 200：全部项目 + 在途任务 + 最近审计 8 条

| 项 | 内容 |
|---|---|
| 命令 | `curl.exe -s -w "\nHTTP:%{http_code}" http://127.0.0.1:8787/ext/status`<br>隔离验证（区分 board 端 vs 代理端改写）：`curl.exe -s -w "\nHTTP:%{http_code}" http://127.0.0.1:8788/api/ext/status` |
| 期望 | HTTP 200；JSON 含 `projects`（全部项目数组）、`in_flight_tasks`（在途 = status!=done，跨全部项目，按 priority 排序）、`recent_audit`（最近 8 条，倒序）、`generated_at`（时间戳）；`projects` 含 id=19 |
| 判定标准 | **PASS**：8787 与 8788 均 200 + 四个字段齐全 + projects 含 id=19 + recent_audit 长度 == 8（若审计总数 <8 则 ≤8）且倒序。<br>**FAIL**：任一非 200；8787 200 但 8788 404（代理未把 `/ext/status` 改写为 `8788/api/ext/status`，转发到 8788 `/status` 兜底 404）；缺字段；recent_audit 非 8 条。<br>**WARN**：in_flight_tasks 语义与 status!=done 不符（见 §五 WARN-2） |

### AC-1.2 `GET /ext/projects`、`/ext/tasks?project_id=N`、`/ext/audit?project_id=N`、`/ext/presence` → 200 正确数据（含错误路径）

| 用例 | 命令 | 期望 | 判定标准 |
|---|---|---|---|
| T-1.2-1 /ext/projects | `curl.exe -s -w "\nHTTP:%{http_code}" http://127.0.0.1:8787/ext/projects` | 200；数组，元素含 `id/name/owner/created`；含 id=19 | PASS=200+字段齐全+含19；FAIL=非200/缺字段/非数组 |
| T-1.2-2 /ext/tasks?project_id=19 | `curl.exe -s -w "\nHTTP:%{http_code}" "http://127.0.0.1:8787/ext/tasks?project_id=19"` | 200；数组，元素含 `id/parent_id/title/detail/status/priority`；含 #26；树形保留（parent_id 关联 #27/28/29→22） | PASS=200+字段齐全+含#26；FAIL=非200/缺字段/#26缺失 |
| T-1.2-2b /ext/tasks 缺 project_id（错误路径） | `curl.exe -s -w "\nHTTP:%{http_code}" http://127.0.0.1:8787/ext/tasks` | 400 + `{"error":"…"}`（design §2.3：缺失/非法 → 400） | PASS=400+error JSON；FAIL=200/500/非 JSON 错误 |
| T-1.2-3 /ext/audit?project_id=19 | `curl.exe -s -w "\nHTTP:%{http_code}" "http://127.0.0.1:8787/ext/audit?project_id=19"` | 200；数组，元素含 `ts/agent/action/target`；倒序（最新在前，LIMIT 20） | PASS=200+字段齐全+倒序；FAIL=非200/缺字段/顺序错 |
| T-1.2-4 /ext/presence | `curl.exe -s -w "\nHTTP:%{http_code}" http://127.0.0.1:8787/ext/presence` | 200；数组，元素含 `agent/last_seen` | PASS=200+字段齐全；FAIL=非200/缺字段 |

### AC-1.3 `POST /ext/notes` → 写库 + 审计 `agent=远程指导` + 前端可见

| 项 | 内容 |
|---|---|
| 命令 | ① `curl.exe -s -w "\nHTTP:%{http_code}" -X POST http://127.0.0.1:8787/ext/notes -H "Content-Type: application/json" -d "{\"project_id\":19,\"text\":\"QA-TEST-<时间戳> 远程指导留言\"}"`（**不带 X-Agent**，验证默认署名）<br>② 写库佐证：`curl.exe -s -w "\nHTTP:%{http_code}" "http://127.0.0.1:8787/ext/notes?project_id=19"`（design §2.7 配套读，最新在前）<br>③ 审计佐证：`curl.exe -s "http://127.0.0.1:8787/ext/audit?project_id=19"`（及直连 `8788/api/audit?project_id=19`）<br>④ 错误路径：空 text → 400；`project_id` 不存在（如 9999）→ 404 |
| 期望 | ① POST 200 返回 `{"ok":true,"id":N}`；② `/ext/notes` 可读回该留言（含 text/agent/ts）；③ 审计出现新记录 `agent=="远程指导"`、action 含「指导留言」；④ 空 text → 400、项目不存在 → 404 |
| 判定标准 | **必过（PASS 前提）**：① POST 200（经 8787 零 token，非 401）；② 读回留言存在且 text 匹配；③ 审计新记录 `agent=="远程指导"`。<br>**前端可见（最小闭环）**：index.html 现有审计流渲染 `#audit`（`[ts] agent action target`）→ 留言以「操作日志」形式可见；L0 grep 确认 `#audit` 渲染逻辑仍在即可。若主理人要求本次必须出独立「指导留言」栏（design §5 可选跟进项），则另加 index.html 含独立栏渲染钩子的断言（缺则 FAIL）。<br>**FAIL**：POST 非 200；读回缺失；审计无 `agent=="远程指导"`；错误路径未按契约返回 400/404。<br>**WARN**：X-Agent 头存在时审计署名为该 agent 而非「远程指导」（design §2.6：默认/有 X-Agent 用 X-Agent）——测试不带 X-Agent，遇此差异记 WARN。 |

### AC-1.4 无 token 直达 `/ext/*` → 200（不 401）；不污染现有 `/api/*` 路由

| 项 | 内容 |
|---|---|
| 命令 | 无 token GET：`curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8787/ext/status`<br>无 token POST：`curl.exe -s -o NUL -w "%{http_code}" -X POST http://127.0.0.1:8787/ext/notes -H "Content-Type: application/json" -d "{\"project_id\":19,\"text\":\"QA-TEST-token-<ts>\"}"`<br>不污染验证：`curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8787/api/projects`、`http://127.0.0.1:8787/board`、`http://127.0.0.1:8787/studio` |
| 期望 | 经 8787 的所有 `/ext/*` 请求**不带任何鉴权头**均 200（GET 与 POST 都是——代理注入 X-Board-Token 满足 board 写闸）；现有 `/api/projects`、`/board`、`/studio` 保持 200 |
| 判定标准 | **PASS**：8787 /ext/* 无 token 全 200（尤其 POST 不 401）+ 现有 3 路由 200。<br>**FAIL**：8787 /ext/* 任一 401（= 代理 flags.board_token_inject 未生效，board 写闸拦截——design §3 已预警）；现有路由被 /ext 前缀劫持（行为变化）。<br>**预期内（不判 FAIL）**：直连 `8788/api/ext/notes` 无 token → 401（design §1.3C：不改现状，与现有写接口一致；AC-1.4 验收路径是 8787 `/ext/notes`）。<br>**WARN**：prefix=`/ext`（无尾斜杠）对 `/external` 类未来路径的 startswith 误匹配隐患（当前注册表无此类路径，见 §五 WARN-4） |

### AC-1.5 状态对齐：board 已闭环任务补标 done

| 项 | 内容 |
|---|---|
| 命令 | `curl.exe -s "http://127.0.0.1:8787/ext/tasks?project_id=19"`（或直连 `8788/api/tasks?project_id=19`），python 解析任务 #26 状态；佐证查库（只读）：sqlite3 只读打开 board.db 核对 `tasks.status` |
| 期望 | 任务 **#26**（l1_smoke.py 固化进回归套件+KEY守卫assert，对应已闭环 T-20260813-01）status == **done**，detail 指向 `dev-work/tasks/T-20260813-01/`；#22（O4 board 机械闸门）保持 done 不回退；项目 19 分布由 8done+4todo → **9done+3todo**（+0 doing） |
| 判定标准 | **PASS**：#26 == done（含 detail 指向）且 #22 == done（不回退）；分布为 9done+3todo。<br>**FAIL**：#26 仍 todo（AC-1.5 未落实）；#22 被误回退；未闭环任务（#23 P0-2 / #24 P0-4 / #25 S4 warning）被误标 done（过度对齐）。<br>**WARN**：其余已闭环任务按 current_state.md 清单核对——若有其他已闭环卡仍未补标，记 WARN 交主理人裁决是否纳入本次补标范围 |

---

## 三、回归项（/ext/* 新增不影响现有路由）

| 项 | 命令 | 期望 | 判定 |
|---|---|---|---|
| 注册表全路由回归 | `python short_drama_workflow/scripts/route_diff_test.py --base http://127.0.0.1:8787` | 全部路由 PASS=0 FAIL，**exit 0**（含新增 `/ext` 行；柔性断言对 200/404 均认可） | PASS=全 PASS exit 0；FAIL=任一 FAIL |
| 手动回归 · 门户 | `curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8787/studio` | 200 | PASS=200 |
| 手动回归 · 看板 | `curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8787/board` | 200（HTML 含 /board/api/ 改写） | PASS=200 |
| 手动回归 · 工作台 API | `curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8787/api/projects` | 200 | PASS=200 |
| 前缀冲突校验 | `python -m json.tool route_registry.json` + 依赖 route_diff_test.py 加载时校验 | `/ext` 与既有 33 前缀无相等/互为路径前缀冲突；`_load_route_registry` 不抛 RouteRegistryError | PASS=加载成功；FAIL=抛冲突（注意：切勿同时注册 `/ext` 与 `/ext/`） |

> 回归结论红线：**route_diff_test.py 任一 FAIL 或 /studio /board /api/projects 任一非 200 → 整体 FAIL（源码 bug，退回 Engineer）**，即使 AC-1.1~1.5 全过。

---

## 四、判定矩阵

| 等级 | 定义 | 处置 |
|---|---|---|
| **PASS** | 该 AC 全部必过断言满足，无 FAIL 项 | 勾选 AC；进入下一 AC |
| **FAIL** | 任一必过断言不满足（期望按 PRD/方案 v2/design.md §2 契约，非测试自身错误） | 记 `[BUG][S|P]`（复现/期望/实际/环境），**路由→ Engineer（源码 bug）**；修复后进 Round 2 回归 |
| **WARN** | 非阻断观察项：语义/实现选择与契约细节不一致但行为正确；测试数据副作用；主理人待裁决项 | 记录并报主理人裁决，不阻塞放行；若主理人裁定影响验收则升级 |
| **N/A** | 实现未提供某可选能力（如独立「指导留言」栏）且契约标注为跟进项 | 跳过并注明，不计 FAIL |

**缺陷路由规则（QA 职责）**：
- 断言期望正确（对照 PRD/方案/design）但实际输出不符 → **源码 bug → Send to Engineer**。
- 断言本身写错（期望与契约不符）→ **测试 bug → QA 自修**（不派 Engineer）。

**轮次控制（STRICT · 最多 2 轮）**：
- Round 1：写用例→真跑→分析。全 PASS → 退出（报主理人）。
- Round 2（Engineer 修复后或 QA 自修后）：回归重跑。全 PASS → 退出；仍有 FAIL → **立即退出，剩余问题记为 Known Issues 交主理人**，不进入 Round 3。

---

## 五、风险与已知边界（预登记 WARN）

1. **WARN-1 /ext/status 字段契约**：wrapper 键名以 design.md §2.1 为准 = `projects / in_flight_tasks / recent_audit / generated_at`。实现若偏离此契约（如用 `tasks`/`audit`）→ FAIL（契约已钉死）；若在契约字段之外**多返回**字段 → 不判 FAIL，记 WARN。
2. **WARN-2 「在途任务」定义已钉死**：= `status != 'done'`（design §2.1），当前库含 todo/doing，未来 review/verify 自动纳入。若实现用别的过滤（如仅 doing）→ FAIL（与契约不符）。
3. **WARN-3 前端「指导留言」可见形态**：最小闭环 = 留言写入 audit（action=指导留言），现有审计流（index.html #audit 渲染）可见（design §1.5）。独立长文本「指导留言」栏为**可选跟进项**（需主理人拍板是否纳入本次）——若拍板纳入，则 index.html 须含独立栏渲染钩子，缺则 FAIL；若不纳入，以审计流可见为 AC-1.3 前端可见的满足证据。
4. **WARN-4 prefix=`/ext`（无尾斜杠）startswith 隐患**：`_route_matches` 对非 board 路由是 `path.startswith(prefix)`（agnes_proxy.py:210）→ `/external` 等未来路径会被误转发到 `8788/api/ext/ernal` → 404。当前注册表无此类路径，**不阻塞**；若实现改为带尾斜杠会与 `/ext` 冲突报错（design §1.1 已注明），故维持 `/ext`，仅登记为未来路径命名纪律（新路径避免以 `/ext` 开头）。
5. **WARN-5 测试写库副作用**：AC-1.3 会在 board 留下测试留言与审计记录；已约定用唯一标记文本并在 current_state 注明，不影响验收真实性。
6. **WARN-6 零 token 直达依赖代理注入**：board 写闸（`board_token_ok`）已配置（BOARD_TOKEN 存在于 shared_board/.env）→ 8787 `/ext/notes` 能零 token 200 全靠代理 `flags.board_token_inject=true` 注入。L0 静态核验注册表该 flag；真跑遇 401 直接判 FAIL（源码/配置 bug）。**直连 8788 无 token 401 属预期**（design §1.3C），不判 FAIL。
7. **WARN-7 服务重启依赖**：改注册表/改 server.py 后须干净重启 8787/8788 才生效（design §3.1/§3.4）。执行阶段若服务未按新配置重启（如 /ext 仍 404）→ 先确认重启事实，避免误判为源码 bug。

---

## 六、执行产物（测试执行阶段产出，本阶段不产出）

- 本文件勾选版（逐 AC 标 PASS/FAIL/WARN）
- 真跑命令输出存档（curl 状态码 + JSON 摘录 + route_diff_test.py 汇总行）
- 缺陷清单（`[BUG][S|P]` 格式，如有）
- 汇总判定 → 经 SendMessage 回传主理人

---

## 七、验收结果（Round 1 · 2026-08-13 QA 独立验收 · 只验证+记录，零改动源码）

> 环境：8787(PID 19632) / 8788(PID 25660) 已干净重启加载 cc00088；全部探测 127.0.0.1，零 AGNES 额度。
> 结论：**AC-1.1 ~ AC-1.5 全 PASS；回归 35/35 PASS exit 0；无 [BUG]；2 项 WARN（均非阻塞）。建议放行。**

| 验收项 | 结果 | 实际证据（摘录） |
|---|---|---|
| L0-1 注册表 /ext 条目 | ✅ PASS | `route_registry.json:248` prefix=`/ext`, target=`http://127.0.0.1:8788/api/ext`, kind=generic, flags.board_token_inject=true |
| L0-2 server.py notes 表 + 6 端点 | ✅ PASS | `server.py:99` notes 表；do_GET 6 端点（status/projects/tasks/audit/presence/notes）；do_POST `/api/ext/notes`（400/404 校验、agent 默认「远程指导」、audit action=指导留言） |
| L0-3 index.html #audit 渲染 | ✅ PASS | `index.html:71` `<div id="audit">` + `:240` renderAudit + `:226` /api/audit 轮询 → 前端审计流可见最小闭环成立 |
| L0-4 agnes_proxy.py 零改动 | ✅ PASS | `git show cc00088 --stat`：仅 route_registry.json(+9)/board.db/ server.py(+76)，无 agnes_proxy.py |
| AC-1.1 /ext/status | ✅ PASS | 8787 与 8788 均 200；四字段 projects(含id=19)/in_flight_tasks/recent_audit(8条倒序)/generated_at 齐全 |
| AC-1.2 四端点 + 错误路径 | ✅ PASS | projects/tasks?pid=19(12条)/audit(20条倒序)/presence 全 200 字段齐全；tasks 缺 project_id→400；notes 空 text→400、project_id 非整数→400、项目9999→404 |
| AC-1.3 POST /ext/notes | ✅ PASS | 无 token 无 X-Agent POST `QA-TEST-184119-远程指导验收留言` → 200 `{"ok":true,"id":2}`；/ext/notes 读回精确匹配（UTF-8 无损）；审计新增 agent=`远程指导` action=`指导留言`；前端审计流可见 |
| AC-1.4 无 token 直达 + 零污染 | ✅ PASS | 6 个 GET + 1 个 POST 无 token 全 200（代理注入 X-Board-Token 过写闸）；/api/projects /board /studio 全 200；直连 8788 无 token POST→401（设计预期，不判 FAIL） |
| AC-1.5 状态对齐 | ✅ PASS | 项目19 = **10 done + 2 todo**；#26 done(detail→T-20260813-01)、#23 done(detail→T-20260813-06 闭环)、#22 done 不回退、#24/#25 todo 未过度对齐 |
| 回归 route_diff_test.py | ✅ PASS | **35 路由, PASS=35, FAIL=0, exit 0**；/board GET 200 [board rewrite 生效]、/ext 转发生效（bare /ext→404 属未知路径，正常） |
| 手动回归 3 路由 | ✅ PASS | /studio=200、/board=200、/api/projects=200 |

### 缺陷清单（Round 1）

- 无 `[BUG]`。

### WARN 记录（非阻塞）

1. **WARN-A（主理人侧测试数据编码）**：审计/notes 中 `id=1` 留言文本 `QA-TEST-1839 ????????`——主理人 18:39 经 PowerShell 发的中文被客户端转成 `?`（PowerShell 非 ASCII 发送缺陷）。**非服务端 bug**：QA 用 curl.exe UTF-8 重测中文无损往返（id=2 精确匹配）。若在意该条显示，可用 curl.exe 重发覆盖。
2. **WARN-B（测试写库副作用）**：本次验收在 board.db 留下测试留言 `id=2`（QA-TEST-184119-远程指导验收留言）与 `id=3`（QA-TEST-AC14-non-token）及对应审计/presence 记录——唯一标记文本可追溯，按协议不删除；已在回报主理人中注明。
3. **WARN-C（观察项）**：`GET /ext`（裸前缀）→ 404（board 兜底）属正常（无该端点定义），转发生效证据为 8788 应答而非门户 unknown path。
