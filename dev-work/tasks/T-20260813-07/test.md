# T-20260813-07 测试文档（test.md）· 看板 5 态中文 + /docs + 校验 400 + 注册表热加载

> 分层：**L0 离线静态**（不依赖服务，grep/代码核验）｜**L1-隔离实例**（8799 临时 board 实例 + 临时 DB 副本，校验/构造样例/迁移重跑）｜**L1-线上**（8787+8788 只读断言 + /docs 可达 + 热加载 K2 sanctioned 流程 + 回归）。
> 状态：**测试文档先行**（老板 18:09 新流程）——本文档只描述计划/用例/判定，不执行任何改动；主理人审过后才进入测试执行。
> 铁律：本阶段禁止写代码、禁止改文件、禁止重启服务；仅允许只读探测（已完成，见基线快照）。执行阶段同样**不动线上 board.db 做破坏性测试**——迁移/校验/构造样例一律在临时副本 + 临时实例上跑，线上只做只读断言。
> 契约来源：PRD `PRD.md`（AC-1.1~1.7）+ 方案 v3 `dev-work/看板改造方案_20260813.md`（§2.3/2.5/2.6/2.7）+ 现状代码（server.py / agnes_proxy.py / route_registry.json / index.html / check_wip.ps1 均已只读核对）。
> 主理人审视坑位：**K1 /ext/status 在途过滤**（迁移后 `!= 'done'` 恒真→爆表）、**K2 热加载测试路由用后即删**、**K3 迁移顺序（先备份后迁移）**、**K4 前端中文化无英文映射残留**——四坑均有专项用例，缺一即退回。

---

## 〇、基线快照（2026-08-13 实现前 · QA 只读实测）

| 探测项 | 结果 | 说明 |
|---|---|---|
| `8787 /`、`/board`、`/ext/status` | 200 / 200 / 200 | 8787 网关在跑（PID **19632** = agnes_proxy.py） |
| `8788 /`、`/api/projects` | 200 / 200 | board 后端在跑 |
| `8787 /qa-hot-xxx/status`（未知路径） | 404 `{"error":"unknown path"}` | 热加载「生效判别」基准（route_diff_test.py 的 PORTAL_UNKNOWN） |
| `8788 /docs`、`8787 /board/docs` | 404 / 404 | **AC-1.3 起点**：/docs 未实现 |
| `shared_board/docs.html` | **不存在** | 实现后应新增 |
| board.db 状态分布 | **todo×10 + done×10（0 doing/blocked）** | 迁移前全英文态；总任务 20 |
| `status<>'done'`（现过滤口径） | 10 | 迁移后若过滤未改中文，会变恒真 → 全 20 入在途（K1 判据） |
| 项目 19 任务 | 12 条：10 done + 2 todo（#24/#25 todo；#18-23/26-29 done） | 迁移后应为 10 完成 + 2 待办 |
| route_registry.json | **35 条路由**（含 /board、/ext、/demo），json.tool 通过 | /docs 走 board kind 子路径，**无需新增注册表行**（/board/docs → 8788/docs） |
| agnes_proxy.py 路由加载 | **模块顶层一次性**（`agnes_proxy.py:200-203`） | 热加载实现前现状：改注册表需重启（AC-1.6 起点） |
| agnes_proxy.py 令牌缓存先例 | `_BOARD_TOKEN_CACHE` mtime 惰性（:63-85） | 热加载应照此模式（方案 §2.5） |
| server.py 写接口 | 无 status/priority/title 校验；status 默认 `'todo'`；`/api/ext/status` 过滤 `status<>'done'` | AC-1.1/1.2 起点 |
| index.html | `ST={todo:"待办",doing:"进行中",blocked:"阻塞",done:"完成"}` 映射 + `<option value="todo">` + `.todo/.doing/.blocked/.done` CSS 类 | **K4 起点**：英文映射展示层残留待清 |
| check_wip.ps1 | 只统计 `status -eq "doing"`（:58-60） | AC-1.4 起点：应升级三态（进行中+待验证+已验证） |
| `~/.workbuddy/skills/board/SKILL.md` | 状态约定仍为英文（`:34 todo 待办 / doing 进行中…`） | AC-1.5 产出范围：应改中文 5 态 |
| git status | `shared_board/board.db` 已 M（T-05 遗留），无本任务改动 | 热加载回归清场以「字节还原 + git diff」核验 |

---

## 一、测试计划

### 1.1 分层选择

| 层 | 范围 | 依赖 | 污染面 |
|---|---|---|---|
| **L0 离线静态** | 代码核验：server.py 校验集//docs 路由/K1 过滤、index.html K4 无英文残留、check_wip 三态、agnes_proxy.py 热加载实现、SKILL.md 中文 5 态、route_registry.json 合法 | 无服务 | 零 |
| **L1-隔离实例** | 起 8799 临时 board 实例 + 临时 DB 副本：AC-1.2 校验 400/200 全套、AC-1.4 check_wip 构造样例、AC-1.5 迁移映射重跑 | 本地 python | 仅 $env:TEMP 临时文件，零污染线上 |
| **L1-线上** | 8787+8788 只读断言：AC-1.1 全中文 + K1 in_flight、AC-1.3 /docs 可达、AC-1.5 线上 0 残留（sqlite 只读）、AC-1.6 热加载（注册表临时改动，K2 sanctioned）、AC-1.7 回归 | 8787/8788 在跑 | 仅 route_registry.json 临时改动（用后字节还原） |

**执行顺序**：L0 静态 → L1-隔离实例（临时起停）→ L1-线上（只读 + /docs + 热加载 + 回归）→ 汇总判定。

### 1.2 铁律（执行阶段强制）

1. **迁移/校验/构造样例写测试一律在临时副本 DB + 临时实例（8799）上跑**；线上 board.db 只允许 sqlite **只读**打开（`file:...?mode=ro`）。
2. 写路径测试（含被 400 拒绝的非法请求）**一律不碰线上**——即使 400 拒绝理论上零副作用，为绝对遵守「线上只做只读断言」，写路径全部走隔离实例。
3. 热加载测试改 `route_registry.json`：改动前**字节备份**到 $env:TEMP，用毕**字节还原**并 `git diff --exit-code route_registry.json` 验净（K2 防残留）。
4. 全程**不重启** 8787/8788：PID 前后一致是「热加载零重启生效」的成立证据；若服务掉线，交主理人/开发按工程铁律干净重启，QA 不自行重启。
5. PowerShell 中 `curl` 是 `Invoke-WebRequest` 别名，一律用 **`curl.exe`**；JSON/中文输出用 python 或 `curl.exe -s` 落盘按 UTF-8 读，避免 GBK 乱码误判。

### 1.3 环境准备

```powershell
# 服务在位探测（L1 前必跑）
curl.exe -s -o NUL -w "8787=%{http_code}\n" http://127.0.0.1:8787/
curl.exe -s -o NUL -w "8788=%{http_code}\n" http://127.0.0.1:8788/
# 记录 8787 PID（热加载「零重启」证据）
Get-NetTCPConnection -LocalPort 8787 -State Listen | Select-Object LocalPort,OwningProcess
```

**临时实例起停（L1-隔离实例，QA 执行阶段用，非源码改动）**：

```powershell
# 1) 造临时 DB 副本（AC-1.2/1.4 用当前结构副本；AC-1.5 用迁移前备份副本）
$ts = Get-Date -Format "HHmmss"
Copy-Item shared_board\board.db "$env:TEMP\qa_board_$ts.db" -Force
# 2) 起临时实例 8799：进程级覆写 server.DB（模块 db() 运行时取全局 DB，可覆写；PORT 硬编码仅在 __main__，不起冲突）
#    以 .env 同一 BOARD_TOKEN 注入环境变量，避免模块级自动生成令牌写回真实 .env
$tok = (Select-String -Path shared_board\.env -Pattern '^BOARD_TOKEN=(.+)$').Matches[0].Groups[1].Value.Trim()
$env:BOARD_TOKEN = $tok
Start-Process -WindowStyle Hidden -FilePath python -ArgumentList @(
  '-c', "import sys; sys.path.insert(0, r'C:\Users\67972\WorkBuddy\workbuddy\shared_board'); import server; server.DB = r'$env:TEMP\qa_board_$ts.db'; from http.server import HTTPServer; HTTPServer(('127.0.0.1', 8799), server.H).serve_forever()")
# 3) 就绪探测（重复至 200，最多 5s）
curl.exe -s -o NUL -w "8799=%{http_code}\n" http://127.0.0.1:8799/api/projects
# 4) 用毕杀临时实例（按 8799 端口找 PID）
$p = Get-NetTCPConnection -LocalPort 8799 -State Listen | Select-Object -ExpandProperty OwningProcess
Stop-Process -Id $p -Force; Remove-Item "$env:TEMP\qa_board_$ts.db" -Force
```

> 说明：临时实例与线上跑**同一份 server.py**，校验结果可迁移；写测试只落在临时 DB 副本，跑完即杀即删，零污染线上。

### 1.4 测试工具

| 工具 | 用途 |
|---|---|
| curl.exe | 接口探测（GET/POST/PUT，含 -w 状态码；中文 JSON 落盘按 UTF-8 读） |
| python（标准库 urllib / sqlite3） | JSON 字段断言、只读查库佐证、临时实例起停 |
| `short_drama_workflow/scripts/route_diff_test.py` | 回归（注册表全路由 GET/PUT/DELETE，`PYTHONIOENCODING=utf-8`） |
| 临时副本 check_wip.ps1（$env:TEMP，sed 8788→8799） | AC-1.4 构造样例计数（测试工件，非源码改动） |

---

## 二、逐 AC 测试用例

> 状态枚举（契约钉死）：`STATUS_OK = {待办, 进行中, 待验证, 已验证, 完成, 阻塞}`（阻塞为旁路态）；英文残留集 `EN_BAD = {todo, doing, blocked, done, review, verify}`。
> 优先级枚举：`PRI_OK = {紧急, 高, 中, 低}`。

### AC-1.1 全部 status 为中文 5 态（无英文残留）+ **K1** 在途过滤

| 用例 | 命令 | 期望 | 判定标准 |
|---|---|---|---|
| **T-1.1-1**（L1-线上）项目 19 全中文 | ① `curl.exe -s -w "\nHTTP:%{http_code}" "http://127.0.0.1:8788/api/tasks?project_id=19"`<br>② 隔离验证代理改写：`curl.exe -s -w "\nHTTP:%{http_code}" "http://127.0.0.1:8787/board/api/tasks?project_id=19"` | 两路均 200；JSON 每条 `status ∈ STATUS_OK`；`EN_BAD` 计数 0；项目 19 = 10 完成 + 2 待办 | **PASS**：两路 200 + 全中文 + 0 英文。<br>**FAIL**：任一非 200；存在 status ∉ STATUS_OK（英文残留→迁移未完成）；项目 19 分布异常（如仍 10 done+2 todo） |
| **T-1.1-2**（L1-线上 · **K1 专项**）`/ext/status` 在途不含「完成」 | `curl.exe -s -w "\nHTTP:%{http_code}" http://127.0.0.1:8787/ext/status`<br>交叉核对（只读 sqlite）：`SELECT COUNT(*) FROM tasks WHERE status IN ('进行中','待验证','已验证')` | 200；`in_flight_tasks` 每条 `status ≠ '完成'`，集合 ⊆ **{进行中, 待验证, 已验证}**（design §3.1-C/§9.3：T-07 将在途收窄为三态，与 check_wip 口径一致，为对 T-05「在途=非完成」契约的必要破例）；`len(in_flight_tasks) == sqlite(三态)` | **PASS**：`in_flight_tasks` 无「完成」+ 集合 ⊆ 三态 + 数量与 sqlite 一致（迁移后存量三态 = 0，总览为空属预期正确行为）。<br>**FAIL（K1 命中）**：`in_flight_tasks` 出现 status==`完成` 或数量 > sqlite(三态) → 说明服务端过滤仍是 `status<>'done'`（迁移中文后恒真爆表）或误把待办/完成计入 → **源码 bug → Engineer** |
| **T-1.1-3**（L0-静态）过滤/默认值代码核验 | grep server.py：`CREATE TABLE tasks` 默认值、`POST /api/tasks` 的 `d.get("status", ...)`、`/api/ext/status` 的 SQL WHERE | status 默认 `'待办'`；`/ext/status` 过滤为 `status<>'完成'`；无 `<>'done'` / `'todo'` 残留于这三处 | **PASS**：三处均为中文。<br>**FAIL**：默认值仍 `'todo'` 或 `/ext/status` 仍 `<>'done'`（K1 静态面） |
| **T-1.1-4**（L0-静态 · **K4 前端中文化专项**）index.html 无英文状态映射残留 | grep index.html 展示层：① `ST=` 映射对象（当前 `ST={todo:"待办",...}`）；② `<option value="todo"/"doing"/"blocked"/"done"`；③ `.todo{`/`.doing{`/`.blocked{`/`.done{` CSS 规则；④ 徽标渲染 `ST[t.status]`（当前 `b.className="badge "+t.status; b.textContent=ST[t.status]`） | ① 无 `ST=` 英文键映射（删除英文→中文映射层，PRD §2.6-2）；② 状态下拉 option 值为中文（`value="待办"` 等 5 态+阻塞）；③ 无英文状态 CSS 类残留；④ 徽标直接用中文 status 或经中文→样式类映射（如 `classMap={待办:'todo'}` 仅作样式映射、非显示文本映射） | **PASS**：①③无残留 + ②④中文直显。<br>**FAIL（K4 命中）**：`ST=` 英文键映射仍在 / `<option value="todo">` 仍在 / 英文状态 CSS 类仍用于展示 → 前端仍走英文映射，中文化未落地 → 源码 bug → Engineer。<br>**WARN**：若用 `classMap`（中文→样式类）映射但显示文本为中文，属合规实现，记通过；仅当**显示文本**仍经英文键取值才判 FAIL |

### AC-1.2 POST 非法 status / 缺 title → 400 明确错误；合法提交 → 200

> **全部用例走 L1-隔离实例（8799 + 临时 DB 副本）**，线上零写路径。错误信息契约（PRD §三）：status 非法示例 `{"error":"status 非法，允许: 待办/进行中/待验证/已验证/完成/阻塞"}`；title/priority 同理中文明确。

| 用例 | 命令（临时实例 8799，带 `X-Board-Token` 或 `?token=`） | 期望 | 判定标准 |
|---|---|---|---|
| **T-1.2-1**（L0-静态）校验分支存在 | grep server.py：`do_POST /api/tasks` 与 `do_PUT /api/tasks/<id>` 含 title 非空 + status ∈ STATUS_OK + priority ∈ PRI_OK 校验 → 400 | POST 与 PUT 均有校验分支；400 响应体为中文 error | PASS=两写接口均有校验；FAIL=任一缺失（无校验→脏数据可入） |
| **T-1.2-2** 非法 status='todo' | `curl.exe -s -w "\nHTTP:%{http_code}" -X POST http://127.0.0.1:8799/api/tasks -H "Content-Type: application/json" -H "X-Board-Token: <tok>" -d "{\"project_id\":19,\"title\":\"QA-TEST-AC12-bad-status\",\"priority\":\"中\",\"status\":\"todo\"}"` | **400** + error 含「status 非法」+ 含完整允许串「待办/进行中/待验证/已验证/完成/阻塞」 | PASS=400+错误信息明确含枚举串；FAIL=200/500/信息不含枚举 |
| **T-1.2-3** 缺 title | `... -d "{\"project_id\":19,\"priority\":\"中\"}"` | **400** + error 含 title 或「标题」 | PASS=400+明确提示；FAIL=200 落库/500/提示不明 |
| **T-1.2-4** 非法 priority='最高' | `... -d "{\"project_id\":19,\"title\":\"QA-TEST-AC12-bad-pri\",\"priority\":\"最高\"}"` | **400** + error 含 priority 或「优先级」+ 含允许串「紧急/高/中/低」 | PASS=400+明确；FAIL=200/500 |
| **T-1.2-5** 合法提交 + 默认中文状态 | `... -d "{\"project_id\":19,\"title\":\"QA-TEST-AC12-ok-<ts>\",\"priority\":\"中\"}"`（**不带 status**）→ 记返回 id；`curl.exe -s "http://127.0.0.1:8799/api/tasks?project_id=19"` | 首次 **200** `{"id":N}`；GET 回读该任务 status == **`待办`**（默认值中文） | PASS=200 + 默认待办；FAIL=非 200 / 默认仍 todo |
| **T-1.2-6** PUT 校验对称 | 对 T-1.2-5 新建任务：`curl.exe -s -w "\nHTTP:%{http_code}" -X PUT http://127.0.0.1:8799/api/tasks/<id> -H "Content-Type: application/json" -H "X-Board-Token: <tok>" -d "{\"status\":\"todo\"}"`；再 `-d "{\"status\":\"完成\"}"` | 非法 status → **400**；合法 status=`完成` → **200** | PASS=400/200 对称；FAIL=PUT 无校验（200 接受 todo） |

### AC-1.3 `GET /docs` 本地 8788 + 外部 `/board/docs` 均 200，页面含枚举/端点/示例/规则

| 用例 | 命令 | 期望 | 判定标准 |
|---|---|---|---|
| **T-1.3-1**（L1-线上）本地 /docs | `curl.exe -s -o NUL -w "%{http_code} %{content_type}" http://127.0.0.1:8788/docs` | **200** + `text/html` | PASS=200+html；FAIL=404/非 html |
| **T-1.3-2**（L1-线上）外部 /board/docs | `curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8787/board/docs` | **200**（board kind 路由把 `/board/docs` 改写转发到 8788 `/docs`，见 `_proxy_board` :538） | PASS=200；FAIL=404/非 200（代理改写未覆盖子路径→源码 bug） |
| **T-1.3-3**（L1-线上）内容断言 | `curl.exe -s http://127.0.0.1:8787/board/docs -o "$env:TEMP\qa_docs.html"`，python 按 UTF-8 读并逐关键词断言 | 页面含：① 状态枚举「待办/进行中/待验证/已验证/完成/阻塞」；② 优先级「紧急/高/中/低」；③ 端点表（`/api/tasks`、`/ext/`、`/docs`）；④ 必带字段（title、priority）；⑤ curl 示例（`X-Agent`、`X-Board-Token`）；⑥ 身份与写锁规则（`403` 或「写锁」或「owner」） | **PASS**：六类关键词全命中。<br>**FAIL**：任一缺失（页面不完整→按 PRD §二 内容清单逐项核对缺哪类）。<br>**WARN**：页面无 `/ext/*` 端点或示例（docs 是外部角色接入规范载体，缺则记 WARN 报主理人） |
| **T-1.3-4**（L1-线上）可选 /ext/docs | `curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8787/ext/docs` | PRD AC-1.3 只要求 `/board/docs`；若实现 `/ext/docs` 别名 → **200** 同内容；未实现 → 404 | 实现则 PASS=200；未实现记 **N/A**（不判 FAIL，契约标注可选） |
| **T-1.3-5**（L0-静态）文件/路由存在 | `ls shared_board/docs.html`；grep server.py `do_GET` 含 `/docs` | docs.html 存在；server.py 有 `GET /docs` → 返回 docs.html | PASS=两者齐；FAIL=缺一 |

### AC-1.4 check_wip.ps1 对「进行中/待验证/已验证」计数正确（构造样例验证）

| 用例 | 命令 | 期望 | 判定标准 |
|---|---|---|---|
| **T-1.4-1**（L0-静态）三态过滤 | grep check_wip.ps1 统计段 | 过滤条件含「进行中」且含「待验证」且含「已验证」（三态并集）；**无 `-eq "doing"` 残留** | PASS=三态齐+无 doing；FAIL=仍只数 doing（AC-1.4 未落实） |
| **T-1.4-2**（L1-线上只读）原脚本对迁移后中文库正常 | `powershell -NoProfile -ExecutionPolicy Bypass -File short_drama_workflow\ops\check_wip.ps1 -ProjectId 19 -Limit 3` | exit 0，输出 `[OK] WIP PASS (n/3)`（n=线上在途三态数，迁移后应为 0 或实际值）；无 ERROR/乱码 | PASS=exit 0+格式正常；FAIL=exit 1/ERROR/乱码（脚本未适配中文状态） |
| **T-1.4-3**（L1-隔离 · 构造样例判别）三态计数 | ① 临时实例 8799 建 4 任务（同 author「阿编」）：A `进行中`、B `待验证`、C `已验证`、D `完成`<br>② 临时副本脚本（`Get-Content -Raw` 后 `-replace '8788','8799'`、并把 `$RepoRoot = Split-Path...` 行替换为 `$RepoRoot = "C:\Users\67972\WorkBuddy\workbuddy"`，写 $env:TEMP\qa_check_wip.ps1——**测试工件非源码**）<br>③ `powershell -File $env:TEMP\qa_check_wip.ps1 -ProjectId 19 -Limit 3`<br>④ 同脚本 `-Limit 2` | ③ **exit 0** `[OK] WIP PASS (3/3)`（完成 D 不计）；④ **exit 1** `[FAIL] WIP 超限 (3/2)` | **PASS**：③ 数到 3（三态全计）且 ④ 超限红卡。<br>**FAIL**：③ 数 1（只数进行中→旧口径）或 D 被计入（把完成当在途）；④ 未红卡 → **源码 bug → Engineer** |

### AC-1.5 存量迁移：0 英文残留 + 迁移前有备份（**K3**）

| 用例 | 命令 | 期望 | 判定标准 |
|---|---|---|---|
| **T-1.5-1**（L1-线上 · **K3 备份存在**） | `ls shared_board/` 找迁移前备份（glob `board.db*.bak` / `board.db.<ts>.bak` / `board.db.bak`）；python 只读打开该备份：`SELECT DISTINCT status FROM tasks` | 存在**非 board.db 本体**的备份文件；其内容**含英文状态**（todo/done 等）→ 证明是**迁移前**快照 | **PASS**：备份存在 + 内容为英文（迁移前）。<br>**FAIL**：无备份（K3 违反→迁移不可回滚）；备份内容已是中文（= 迁移后才备份，顺序错） |
| **T-1.5-2**（L1-隔离 · 迁移映射重跑） | 把 T-1.5-1 备份复制到 $env:TEMP，在**副本**上执行与实现同一迁移 SQL：`todo→待办, doing→进行中, blocked→阻塞, done→完成`；断言：① `SELECT COUNT(*) FROM tasks WHERE status IN ('todo','doing','blocked','done')`==0；② `SELECT COUNT(*) FROM tasks WHERE status NOT IN STATUS_OK`==0；③ 抽查原 done→完成、todo→待办 映射正确 | 副本上迁移后：英文 0 残留；全值 ∈ STATUS_OK；映射正确 | **PASS**：三断言全过。<br>**FAIL**：有英文残留/有非法值/映射错位 → 迁移 SQL bug → Engineer |
| **T-1.5-3**（L1-线上只读）线上已迁移 | sqlite **只读**打开线上 board.db：`SELECT COUNT(*) FROM tasks WHERE status IN EN_BAD`；`GET /api/tasks?project_id=19` | 线上英文残留 **0**；接口全中文（与 T-1.1-1 互证） | PASS=0 残留+全中文；FAIL=有英文（线上迁移未执行/未完成） |
| **T-1.5-4**（L0-静态）SKILL.md 约定中文 5 态 | grep `~/.workbuddy/skills/board/SKILL.md` 状态段 | 状态约定为「待办/进行中/待验证/已验证/完成（+阻塞）」；无「todo 待办 / doing 进行中…」英文键行 | PASS=中文 5 态；FAIL=仍英文约定 |

### AC-1.6 注册表热加载（**K2** 流程：加测试路由→生效→删路由→回归）

> 全程**不重启 8787**；`route_registry.json` 改动前字节备份、用毕字节还原。测试路由前缀用唯一 `qa-hot-<ts>`，target=`http://127.0.0.1:8788/api/ext`，kind=generic，flags={}——探测 `GET /qa-hot-<ts>/status`（generic 子路径拼 target → `8788/api/ext/status` → 200 JSON）；未加载时该路径为门户 404 `unknown path`（判别基准已实测）。

| 用例 | 命令 | 期望 | 判定标准 |
|---|---|---|---|
| **T-1.6-0**（前置）测试路由未加载 | `curl.exe -s -w "\nHTTP:%{http_code}" http://127.0.0.1:8787/qa-hot-<ts>/status` | 404 + body 含 `unknown path` | PASS=404 unknown path；FAIL=非此形态（异常基线，先查环境） |
| **T-1.6-1**（K2 主流程 · 加→生效） | ① `Copy-Item route_registry.json $env:TEMP\route_registry.pre-qa-hot.json -Force`（字节备份）<br>② python 读注册表，`routes` 末尾 append 测试路由行（prefix=`/qa-hot-<ts>`，target=`http://127.0.0.1:8788/api/ext`，kind=`generic`，flags={}），原子写回<br>③ **立即**（不重启）每秒探测一次 `GET /qa-hot-<ts>/status`，最多 5s | **≤5 秒内**该路径由 404 → **200** JSON（含 `projects/in_flight_tasks/recent_audit/generated_at`） | **PASS**：≤5s 变 200（mtime 惰性重载生效）。<br>**FAIL**：5s 后仍 404 unknown path（热加载未实现/未按 mtime 重载）→ 源码 bug → Engineer |
| **T-1.6-2**（零重启证据） | 全程多次 `Get-NetTCPConnection -LocalPort 8787 -State Listen \| Select OwningProcess` | 8787 PID 始终 = **19632**（基线值），与热加载前一致 | PASS=PID 不变；FAIL=PID 变化（被重启，则 T-1.6-1 的 200 不构成「热加载」证据） |
| **T-1.6-3**（冲突注册表 → 拒绝、沿用旧路由） | ① 在当前含测试路由的注册表上再 append 一条冲突行（prefix=`/api`，target=`http://127.0.0.1:9999`——与既有 `/api/projects` 等互为路径前缀，`_find_prefix_conflict` 必命中），原子写回<br>② 等 ≤5s 后探测：`GET /qa-hot-<ts>/status`、`GET /board`、`GET /ext/status` | 网关**不因冲突崩溃**；旧路由（含上一版已加载的测试路由 `/qa-hot-<ts>`、`/board`、`/ext`）**继续可用**；冲突行 `/api` 未生效 | **PASS**：三探测均 200 且 8787 仍响应（冲突被拒、沿用旧路由）。<br>**FAIL**：8787 崩溃/500/测试路由消失（实现把冲突注册表整表替换而非保留旧路由）→ 源码 bug → Engineer |
| **T-1.6-4**（K2 删路由 → 回归） | ① `Copy-Item $env:TEMP\route_registry.pre-qa-hot.json route_registry.json -Force`（**字节还原**原始注册表）<br>② 等 ≤5s：`GET /qa-hot-<ts>/status` → 应回 404 unknown path；`GET /board`、`GET /ext/status` → 200<br>③ `git diff --exit-code route_registry.json` | 测试路由**回归消失**（404）；既有路由不受影响；注册表与测试前**字节一致**（git 净） | **PASS**：404 回归 + /board /ext 200 + git diff 净（K2 防残留达成）。<br>**FAIL**：测试路由仍 200（残留）/git diff 有差异（未还原干净）→ 测试执行问题，QA 自修还原后再判 |

### AC-1.7 回归：现有 /ext 6 端点、/studio、/board、根路径全 200

| 用例 | 命令 | 期望 | 判定标准 |
|---|---|---|---|
| **T-1.7-1** /ext 6 端点 | `curl.exe -s -o NUL -w "%{http_code}\n"` 依次：`/ext/status`、`/ext/projects`、`/ext/tasks?project_id=19`、`/ext/audit?project_id=19`、`/ext/presence`、`/ext/notes?project_id=19`（均经 8787） | 6 个全 **200**（GET 只读） | PASS=6×200；FAIL=任一非 200（/ext 被破坏→源码 bug） |
| **T-1.7-2** 门户/看板/根 | `curl.exe -s -o NUL -w "%{http_code}\n"`：`http://127.0.0.1:8787/studio`、`http://127.0.0.1:8787/board`、`http://127.0.0.1:8787/`、`http://127.0.0.1:8788/` | 全 **200** | PASS=4×200；FAIL=任一非 200 |
| **T-1.7-3** 注册表全路由回归 | `$env:PYTHONIOENCODING="utf-8"; python short_drama_workflow\scripts\route_diff_test.py --base http://127.0.0.1:8787` | 全部路由 PASS、FAIL=0、**exit 0**（注册表 35 条，/docs 不经注册表故计数不变） | PASS=FAIL 0 + exit 0；FAIL=任一 FAIL → 整体 FAIL 退回 Engineer |
| **T-1.7-4** /ext 语义不破坏 | python 解析 `/ext/status`：wrapper 键 `projects/in_flight_tasks/recent_audit/generated_at` 齐全；`/ext/tasks?project_id=19` 含 id/parent_id/title/detail/status/author/updated/priority 且含 #18-29；`/ext/notes?project_id=19` 返回数组 | 键名/字段与 T-05 契约一致，仅 status **值**变中文 | PASS=字段齐全+数据在；FAIL=字段名变化/数据缺失（语义破坏） |

---

## 三、回归项（汇总红线）

| 项 | 命令 | 期望 | 判定 |
|---|---|---|---|
| 注册表全路由回归 | `PYTHONIOENCODING=utf-8 python route_diff_test.py --base http://127.0.0.1:8787` | 全 PASS，FAIL=0，exit 0 | PASS=全过；FAIL=任一 FAIL |
| 门户 /studio | curl 8787/studio | 200 | PASS=200 |
| 看板 /board | curl 8787/board | 200（HTML 含 /board/api/ 改写） | PASS=200 |
| 根路径 | curl 8787/、8788/ | 200 | PASS=200 |
| /ext 6 端点 GET | 见 T-1.7-1 | 6×200 | PASS=全 200 |
| 注册表热加载清场 | `git diff --exit-code route_registry.json` | 净（字节还原） | PASS=净；FAIL=残留 |

> **回归结论红线**：route_diff_test.py 任一 FAIL 或 /studio /board / 根路径任一非 200 → **整体 FAIL（源码 bug，退回 Engineer）**，即使 AC-1.1~1.6 全过。

---

## 四、判定矩阵

| 等级 | 定义 | 处置 |
|---|---|---|
| **PASS** | 该 AC 全部必过断言满足，无 FAIL 项 | 勾选 AC；进入下一 AC |
| **FAIL** | 任一必过断言不满足（期望按 PRD/方案 v3/契约，非测试自身错误） | 记 `[BUG][S|P]`（复现/期望/实际/环境），**路由→ Engineer（源码 bug）**；修复后进 Round 2 回归 |
| **WARN** | 非阻断观察项：语义/实现选择与契约细节不一致但行为正确；测试数据副作用；主理人待裁决项 | 记录并报主理人裁决，不阻塞放行；若主理人裁定影响验收则升级 |
| **N/A** | 实现未提供可选能力（如 /ext/docs 别名、独立前端「指导留言」栏等）且契约标注为跟进项/可选 | 跳过并注明，不计 FAIL |

**缺陷路由规则（QA 职责）**：
- 断言期望正确（对照 PRD/方案 v3/契约）但实际输出不符 → **源码 bug → Send to Engineer**。
- 断言本身写错（期望与契约不符）→ **测试 bug → QA 自修**（不派 Engineer）。

**轮次控制（STRICT · 最多 2 轮）**：
- Round 1：写用例→执行→分析。全 PASS → 退出（报主理人）。
- Round 2（Engineer 修复后或 QA 自修后）：回归重跑。全 PASS → 退出；仍有 FAIL → **立即退出，剩余问题记为 Known Issues 交主理人**，不进入 Round 3。

---

## 五、风险与已知边界（预登记 WARN）

1. **WARN-1 /ext/docs 可选性**：PRD AC-1.3 只要求本地 `/docs` + 外部 `/board/docs`；`/ext/docs` 为方案 v3 §2.7 的「或」表述。实现则验 200，未实现记 N/A，不判 FAIL。
2. **WARN-2 热加载测试临时改线上注册表（K2 sanctioned）**：T-1.6 全程改动 `route_registry.json`（加测试路由/写入冲突/字节还原）。已约定：改动前字节备份、用毕还原、`git diff` 验净。若执行中断导致残留，QA 负责还原后再判，避免把测试残留误判为源码 bug。
3. **WARN-3 隔离实例与线上同代码**：8799 临时实例跑同一份 server.py（新实现），校验/迁移重跑结果可迁移到线上结论；但**线上只做只读断言**，不因隔离实例全过就免线上只读抽查（T-1.1-1 / T-1.5-3 / T-1.7 仍必须在线上验）。
4. **WARN-4 check_wip 临时副本脚本为测试工件**：`$env:TEMP\qa_check_wip.ps1` 仅 sed 端口/RepoRoot，不入仓库、不改源码；T-1.4-2 用原脚本对线上只读跑（验证适配中文），T-1.4-3 用副本脚本对隔离实例跑（验证三态计数）。
5. **WARN-5 中文 CSS 徽标样式**：迁移后 index.html 若用 `class="badge 待办"`（中文类名），CSS 若无对应 `.待办{...}` 规则则徽标回退默认样式（功能不受影响，纯视觉）。记 WARN 报主理人，不判 FAIL；若实现保留英文类名映射（如 `classMap={待办:'todo'}`）则无此问题。
6. **WARN-6 备份文件命名不确定**：T-1.5-1 用 glob 放宽（`board.db*.bak` / `board.db.<ts>.bak` / `board.db.bak`）；若实现以 git 提交作为备份证据（board.db 已入库），则改为核对「迁移前最后一次 commit 中 board.db 内容为英文」，同样满足 K3。
7. **WARN-7 线上迁移由开发执行一次**：AC-1.5 线上 0 残留依赖 dev 已在线上跑迁移（PRD 证据要求「迁移前后 db 备份文件」）；QA 只读核验线上结果 + 副本重跑迁移逻辑，不替 dev 执行线上迁移。
8. **WARN-8 route_diff_test.py 计数动态**：注册表当前 35 条；若实现为 /docs 另加注册表行则计数变化，但**判定只看 FAIL=0 + exit 0**，不锁死条数。
9. **WARN-9 状态值变化对下游的预期**：/ext/status 等返回 status 值由英文变中文是**本次契约变更**（PRD 边界「status 返回中文即可」），非回归；但任何消费方若仍按英文断言会误报——回归断言按新契约（STATUS_OK）写，不按旧值写。

---

## 六、执行产物（测试执行阶段产出，本阶段不产出）

- 本文件勾选版（逐 AC 标 PASS/FAIL/WARN/N/A）
- 真跑命令输出存档（curl 状态码 + JSON 摘录 + route_diff_test.py 汇总行 + 热加载时间线）
- 隔离实例起停记录（8799 PID、临时 DB 路径、清理确认）
- 缺陷清单（`[BUG][S|P]` 格式，如有）
- K1~K4 专项结论（K1 在途过滤、K2 用后即删、K3 备份先行、K4 前端无英文残留）
- 汇总判定 → 经 SendMessage 回传主理人

---

## 七、验收结果（Round 1 · 2026-08-13 QA 独立验收 · 只验证+记录，零改动源码）

> 环境：8787(PID 29144) / 8788(PID 13040) 运行新代码（bb8f7c2 + 迁移 2a1628b）；隔离实例 8799 临时 DB 副本跑写路径，线上仅只读；全程未重启（PID 前后一致）。
> 结论：**AC-1.1 ~ AC-1.7 全 PASS；无 [BUG]；1 项 N/A（/ext/docs 可选未实现）；3 项 WARN（非阻塞）。建议放行。**
> 测试文档修正：T-1.1-2 期望由「在途=非完成」更新为「在途=三态（进行中/待验证/已验证）」（design §3.1-C/§9.3 显式破例，K1 判别不变）。

### L0 静态（离线）

| 项 | 结果 | 实际证据（摘录） |
|---|---|---|
| T-1.1-3 server.py 枚举/默认/过滤 | ✅ PASS | `STATUS_ENUM`/`PRIORITY_ENUM`（server.py:12-13）；`status DEFAULT '待办'`（:84）+ POST 默认 `'待办'`（:274）；`/ext/status` 过滤 `IN ('进行中','待验证','已验证')`（:201），无 `<>'done'` 残留 |
| T-1.1-4 K4 index.html 无英文残留 | ✅ PASS | 无 `ST=` 英文键映射；下拉 `value="待办"/"进行中"/"待验证"/"已验证"/"完成"/"阻塞"`（:81-83）；CSS `.badge[data-status="待办"]…"阻塞"`（:24-29）；徽章 `b.dataset.status=t.status; b.textContent=t.status`（:195）；grep todo/doing/done/blocked 零命中 |
| T-1.2-1 校验分支 POST+PUT | ✅ PASS | `validate_task_fields`（:127-138）：title 非空/priority∈枚举/status∈枚举 → 中文 400；POST :269-271、PUT :321-323 均调用 |
| T-1.3-5 docs.html + /docs 路由 | ✅ PASS | `shared_board/docs.html` 存在（9051B）；server.py `GET /docs`/`/docs.html`（:161-167） |
| T-1.4-1 check_wip 三态 | ✅ PASS | `$wipStates=@("进行中","待验证","已验证")`（check_wip.ps1:58）+ `-contains`（:60）；无 `-eq "doing"` |
| L0-7 agnes_proxy 热加载 | ✅ PASS | `_ROUTE_REGISTRY_CACHE`（:204）+ `_get_route_registry()` mtime 惰性（:206-231）；冲突 catch RouteRegistryError 沿用旧路由（:220-225）；`_route_for` 走 `_get_route_registry()`（:253）；照抄 `_BOARD_TOKEN_CACHE` 模式 |
| T-1.5-4 SKILL.md 中文 5 态 | ✅ PASS | SKILL.md:34「待办/进行中/待验证/已验证/完成；阻塞（旁路）」+ :35 在途三态口径 |
| py_compile | ✅ PASS | server.py + agnes_proxy.py 编译通过 |

### L1-隔离实例（8799 临时 DB 副本 · 写路径）

| 项 | 结果 | 实际证据（摘录） |
|---|---|---|
| T-1.2-2 非法 status=todo | ✅ PASS | POST → 400 `{"error":"status 非法，允许: 待办/进行中/待验证/已验证/完成/阻塞"}` |
| T-1.2-3 缺 title | ✅ PASS | POST → 400 `{"error":"title 不能为空"}` |
| T-1.2-4 非法 priority=最高 | ✅ PASS | POST → 400 `{"error":"priority 非法，允许: 紧急/高/中/低"}` |
| T-1.2-5 合法提交+默认中文 | ✅ PASS | POST（不带 status）→ 200 `{"id":1}`；GET 回读 status=`待办` |
| T-1.2-6 PUT 校验对称 | ✅ PASS | PUT status=todo → 400；PUT status=完成 → 200 `{"ok":true}` |
| T-1.4-3 check_wip 构造样例 | ✅ PASS | 临时实例建 4 任务（进行中/待验证/已验证/完成）→ 临时副本脚本：`-Limit 3` → `[OK] WIP PASS (3/3)` exit 0；`-Limit 2` → `[FAIL] WIP 超限 (3/2)` exit 1；完成不计（wip_count=3） |
| T-1.5-2 迁移映射重跑 | ✅ PASS | 备份副本迁移后 EN_RESIDUE=0、INVALID=0、分布=待办×10+完成×10 |

### L1-线上只读（8787+8788）

| 项 | 结果 | 实际证据（摘录） |
|---|---|---|
| T-1.1-1 项目19全中文 | ✅ PASS | 8788 直连 + 8787 `/board/api/tasks` 均 200；12 条全中文，en=0 |
| T-1.1-2 K1 在途过滤 | ✅ PASS | `/ext/status` in_flight=0（无「完成」，⊆三态）；`sqlite(三态)=0` 一致；`sqlite(not 完成)=10` 佐证若过滤未改会爆表（K1 判别有效） |
| T-1.5-1 K3 备份存在 | ✅ PASS | `board.db.bak-20260813-190840` 存在，内容含英文 `[('todo',),('done',)]`（迁移前快照） |
| T-1.5-3 线上 0 残留 | ✅ PASS | 只读 sqlite：英文残留=0 |
| T-1.3-1/2/3 /docs 可达+内容 | ✅ PASS | 8788/docs=200；8787/board/docs=200；六类关键词（枚举/优先级/端点/必带字段/curl 示例/X-Agent+X-Board-Token/403）全命中 |
| T-1.3-4 /ext/docs 可选 | **N/A** | 8787/ext/docs → 404（PRD 只要求 /board/docs，可选未实现，记 N/A 不判 FAIL） |
| T-1.6-0 测试路由未加载 | ✅ PASS | `/qa-hot-0713/status` → 404 `unknown path`（基线） |
| T-1.6-1 热加载加路由生效 | ✅ PASS | 注册表加测试路由 → **t+1s** `/qa-hot-0713/status` → 200（ext/status JSON）——零重启生效 |
| T-1.6-2 零重启证据 | ✅ PASS | 8787 PID 全程 = **29144**（与基线一致）；8788 = 13040 |
| T-1.6-3 冲突拒绝旧路由可用 | ✅ PASS | 追加 prefix=`/api`（与 /api/projects 冲突）→ 2s 后 `/qa-hot-0713/status`、`/board`、`/ext/status`、`/api/projects` 全 200；网关不崩、冲突行未生效 |
| T-1.6-4 K2 删路由回归+清场 | ✅ PASS | 字节还原原始注册表 → t+1s 测试路由回 404；/board、/ext/status 200；route count=35、无 qa-hot 残留；**BYTE-IDENTICAL** 与备份 + `git diff --exit-code route_registry.json` exit 0 |
| T-1.7-1 /ext 6 端点 | ✅ PASS | status/projects/tasks?pid=19/audit?pid=19/presence/notes?pid=19 全 200 |
| T-1.7-2 门户/看板/根 | ✅ PASS | /studio、/board、8787/、8788/ 全 200 |
| T-1.7-3 route_diff_test.py | ✅ PASS | `PYTHONIOENCODING=utf-8` → **35 路由, PASS=35, FAIL=0, exit 0** |
| T-1.7-4 /ext 语义不破坏 | ✅ PASS | wrapper 键 `projects/in_flight_tasks/recent_audit/generated_at` 齐全；tasks 字段齐全含 #18-29 |

### 缺陷清单（Round 1）

- 无 `[BUG]`。

### 测试文档修正（QA 自修 · 非源码问题）

- **TEST-FIX-1（T-1.1-2 期望更新）**：原 test.md 以 T-05 契约「在途=非完成」断言 `len(in_flight)==sqlite(not 完成)=10`；实现按 design §3.1-C/§9.3 将 in_flight **收窄为三态**（进行中/待验证/已验证，与 check_wip 口径一致，为对「不碰 /ext 语义」边界的文档化必要破例）。实现与 design 一致 → 断言改为 `len(in_flight)==sqlite(三态)`（线上=0）。K1 核心判别（不含「完成」）不变，仍能抓出 `!= 'done'` 恒真 bug。

### WARN 记录（非阻塞）

1. **WARN-A（in_flight 语义收窄）**：`/ext/status` 在途由「非完成（含待办/阻塞）」收窄为「三态」——design §9.3 明示「内容变少是预期正确行为（当前存量在途=0，总览在途为空属正确；未来任务推进到进行中才出现）」。报主理人知悉：若下游仍按旧「非完成」口径解读总览，会以为"无在途"，实为口径变更。
2. **WARN-B（/ext/docs 可选未实现）**：PRD AC-1.3 只要求本地 + `/board/docs`；`/ext/docs` 404 属可选未实现，记 N/A。若外部角色经 8787 只认 `/ext/docs`，可后续补一行别名。
3. **WARN-C（route_registry.json git M 状态）**：`git status` 显示 route_registry.json 为 M，但 `git diff --exit-code` = 0 —— 系 CRLF 归一化差异（内容与 HEAD 一致），非测试残留；热加载测试已字节还原并 cmp 一致。
4. **WARN-D（测试副作用）**：隔离实例写测试仅在 $env:TEMP 临时 DB 副本（已清理）；线上零写路径。热加载测试对 route_registry.json 的临时改动已字节还原。
