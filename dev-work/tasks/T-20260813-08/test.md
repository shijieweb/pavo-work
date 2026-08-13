# T-20260813-08 测试文档（test.md）· 看板 UI P0×3（详情入口 / 进度概览 / 删除弱化）

> 分层：**L0 离线静态**（不依赖服务，grep/代码核验）｜**L1-线上浏览器**（8788 直连或 8787/board，Playwright 实测交互 + 人工点击路径兜底；纯前端改动，浏览器强制刷新即可生效，**零重启**）。
> 状态：**测试文档先行**（老板 19:57 新流程）——本文档只描述计划/用例/判定，不执行任何改动；主理人审过后才进入测试执行。
> 铁律（本阶段 + 执行阶段）：**只写文档/只读探测**；禁止改代码、禁止改 `index.html`、禁止重启 8787/8788、禁止删真实数据；执行阶段删除/状态写路径一律走**临时实例 8799 + 临时 DB 副本**，线上仅只读断言 + 弹窗出现即取消。
> 契约来源：PRD `PRD.md`（AC-1.1~1.4）+ 现状代码 `shared_board/index.html`（已只读核对，基线快照见 §〇）+ 上一任务 T-07 验收结论（8788 直连/8787 `/board/api` 双路 200、5 态中文、项目 19 = 12 条）。
> 主理人审视坑位：**K1 详情按钮事件冒泡**（点「详情」不得同时触发展开——按钮 handler 必须 `stopPropagation`，否则 AC-1.1 破坏现有单击展开）、**K2 进度条口径**（`已完成` 只计「完成」态；`待验证` 单列；总数=任务树实际条数；阻塞/待办只入总数不入 X/Y/Z 属 design 自由，但总数必须逐条一致）、**K3 删除降级不得丢 confirm**（视觉可弱化，`confirm` 二次确认必须保留）、**K4 后端零改动**（`server.py`/API/DB 字节零差异，`git diff` 净）——四坑均有专项用例，缺一即退回。

---

## 〇、基线快照（2026-08-13 实现前 · QA 只读实测）

| 探测项 | 结果 | 说明 |
|---|---|---|
| `8787 /`、`8787 /board` | 200 / 200 | 网关在跑（PID **29144**） |
| `8788 /` | 200 | board 直连在跑（PID **13040**） |
| 8787/board 返回 HTML vs 本地 index.html | 仅差 2 处：① 注入 `<script>window.__BOARD_TOKEN__="…"`；② 网关改写 `api/`→`board/api/`、`/api`→`/board/api` | **服务端逐请求直读磁盘文件**（server.py:150-151）→ 静态改动浏览器强制刷新即生效，无需重启（热刷新证据） |
| 项目 19 任务分布（`/api/tasks?project_id=19`，8788 直连） | 12 条 = **完成×10 + 待办×2**（0 进行中/0 待验证/0 阻塞） | T-07 迁移后分布；进度条验收期望值以此为准 |
| 项目列表 `/api/projects` | 3 项：4 看板项目 / 18 测试项目 / 19 短剧自动化工作流 | 浏览器实测选项目 19 |
| `git status --short shared_board/index.html shared_board/server.py` | **空（干净）** | 后端零改动（K4）判别基线：实现后 `server.py` 仍须干净 |
| index.html 现状 | 无「详情」按钮（card 仅 `tri+ttl+pri+badge`，单击=展开、双击=详情、长按=详情）；无顶部进度条；删除按钮 `class="danger"`（:92）红底大字；`delTask()` 有 `confirm("删除此任务及所有子任务？")`（:164） | AC-1.1/1.2 起点、AC-1.3 起点 |
| Playwright 可用性 | **python-playwright 已装**；chromium 缓存齐（chromium-1169/1208/1228/1234 + headless_shell）；Edge/Chrome 本机存在 | L1 浏览器实测首选；无则走人工点击路径（§1.4） |
| node/npm | v22.22.2 / 10.9.7；`npx playwright` 可按需装 1.62.1 | 备用方案 |

> 基线结论：**L0 无需起服务（grep 文件即可）**；**L1 浏览器实测用现有 8787/8788，不重启**；写路径（建临时任务/改状态/删临时任务）走 8799 临时实例 + 临时 DB 副本（沿用 T-07 §1.3 起停模板）。

---

## 一、测试计划

### 1.1 分层选择

| 层 | 范围 | 依赖 | 污染面 |
|---|---|---|---|
| **L0 离线静态** | 代码核验 `index.html`：AC-1.1 详情按钮存在 + 事件不回归；AC-1.2 进度条逻辑 + 口径；AC-1.3 删除按钮样式降级 + confirm 保留；AC-1.4 5 态/阻塞/日志/保存/新建结构无破坏；K4 `server.py` git 净 | 无服务 | 零 |
| **L1-线上浏览器（只读交互）** | 8788 直连或 8787/board，Playwright：详情按钮点击开抽屉、单击展开不回归、双击/长按详情、进度条文案与 API 逐条一致、删除弹窗出现即取消、保存/新建/状态切换/日志回归 | 8787/8788 在跑 + Playwright | 零（无写路径；删除只到弹窗→取消） |
| **L1-隔离实例（写路径）** | 8799 临时 board 实例 + 临时 DB 副本：建临时任务→改状态→验证进度条实时更新→删临时任务→验证数字回退；删除确认后行为验证 | 本地 python | 仅 $env:TEMP 临时文件，零污染线上 |

**执行顺序**：L0 静态 → L1-线上只读（浏览器实测）→ L1-隔离实例（写路径）→ 汇总判定。**L0 全过才进 L1**（L0 抓实现缺失/口径错，L1 抓交互/实时性）。

### 1.2 铁律（执行阶段强制）

1. **不重启 8787/8788**：记录 PID（基线 29144/13040），全程前后一致；服务端直读磁盘，静态改动强制刷新浏览器（Ctrl+F5 / 清缓存）即生效，**不以重启作为验证手段**。
2. **线上零写路径**：AC-1.2 状态切换、AC-1.3 确认后删除等**写测试一律走 8799 临时实例 + 临时 DB 副本**；线上仅只读断言（API GET、浏览器只读交互、删除弹窗出现→取消）。
3. **禁止真删任务**：删除行为验证用「弹窗出现→取消」或「临时任务→删→确认清理」，一律在临时实例/临时 DB 上完成；线上数据零删除。
4. **不改 `index.html`/`server.py`/任何源码**：QA 只读核验；发现的 bug 以 `[BUG]` 报 Engineer，不自改。
5. PowerShell 中 `curl` 是 `Invoke-WebRequest` 别名，一律用 **`curl.exe`**；JSON/中文输出用 python 按 UTF-8 读，避免 GBK 乱码误判。

### 1.3 环境准备（执行阶段）

```powershell
# 服务在位 + PID 基线（L1 前必跑；不重启）
curl.exe -s -o NUL -w "8787=%{http_code}\n" http://127.0.0.1:8787/
curl.exe -s -o NUL -w "8788=%{http_code}\n" http://127.0.0.1:8788/
Get-NetTCPConnection -LocalPort 8787,8788 -State Listen | Select-Object LocalPort,OwningProcess
```

**临时实例起停（L1-隔离实例写路径用，沿用 T-07 模板，非源码改动）**：

```powershell
$ts = Get-Date -Format "HHmmss"
Copy-Item shared_board\board.db "$env:TEMP\qa_board_t08_$ts.db" -Force
$tok = (Select-String -Path shared_board\.env -Pattern '^BOARD_TOKEN=(.+)$').Matches[0].Groups[1].Value.Trim()
$env:BOARD_TOKEN = $tok
Start-Process -WindowStyle Hidden -FilePath python -ArgumentList @(
  '-c', "import sys; sys.path.insert(0, r'C:\Users\67972\WorkBuddy\workbuddy\shared_board'); import server; server.DB = r'$env:TEMP\qa_board_t08_$ts.db'; from http.server import HTTPServer; HTTPServer(('127.0.0.1', 8799), server.H).serve_forever()")
curl.exe -s -o NUL -w "8799=%{http_code}\n" http://127.0.0.1:8799/api/projects
# 用毕：杀 8799 + 删临时 DB
$p = Get-NetTCPConnection -LocalPort 8799 -State Listen | Select-Object -ExpandProperty OwningProcess
Stop-Process -Id $p -Force; Remove-Item "$env:TEMP\qa_board_t08_$ts.db" -Force
```

> 说明：8799 跑**同一份 server.py + 同一份 index.html**（静态文件同目录直读），UI 与写路径结果可迁移到线上结论；线上仍保留只读抽查。

### 1.4 测试工具

| 工具 | 用途 |
|---|---|
| **L0 grep（首选，无需服务）** | 对 `shared_board/index.html` 做断言式 grep：详情按钮/进度条/删除样式/confirm/5 态下拉/日志结构 |
| **python（urllib）** | 只读接口断言：`/api/tasks?project_id=19` 计数、`/api/projects`、交叉核对进度条数字 |
| **curl.exe** | 只读接口探测（状态码）；抓 8787/board HTML 做「线上已生效」静态断言 |
| **Playwright（python）** | L1 浏览器实测：点详情、单击展开、双击/长按、进度条文案、删除弹窗、样式计算。**已探测可用**（§〇） |
| **人工点击路径** | Playwright 不可用时的兜底：按 §二 L1 用例的「人工步骤 + 期望」逐项手测 |

**Playwright 参考脚本**（执行阶段生成 `$env:TEMP\qa_t08_ui.py`，测试工件非源码；选择器以实现后实际 DOM 为准）：

```python
# -*- coding: utf-8 -*-
import json, re, sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8788"   # 或 http://127.0.0.1:8787/board
PID = 19

def api_count():
    import urllib.request
    d = json.load(urllib.request.urlopen(f"{BASE}/api/tasks?project_id={PID}"))
    from collections import Counter
    return len(d), Counter(t["status"] for t in d)

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)  # 本机 Edge；无则 channel="chrome"
    pg = b.new_page(viewport={"width": 1280, "height": 900})
    pg.on("dialog", lambda d: d.dismiss())   # 删除弹窗一律取消（零删除）
    pg.goto(BASE, wait_until="networkidle")
    pg.select_option("#projSel", str(PID)); pg.wait_for_timeout(1200)
    body = pg.inner_text("body")
    # 1) 进度条文案（实现后按实际 DOM 选择器微调）
    m = re.search(r"(\d+) 进行中 · (\d+) 待验证 · (\d+) 已完成 / (\d+)", body)
    print("PROGRESS:", m.groups() if m else None)
    n, c = api_count()
    print("API:", n, dict(c))
    # 2) 详情按钮存在且点击开抽屉（项目19有完成态任务）
    btn = pg.locator("button:has-text('详情')").first
    print("HAS_DETAIL_BTN:", btn.count() > 0)
    btn.click(); pg.wait_for_timeout(400)
    print("DRAWER_OPEN:", pg.locator("#drawer.show").count() > 0)
    pg.locator("#drawer .ghost:has-text('关闭')").click()
    # 3) 删除按钮样式弱于保存（computed style 断言示例）
    save_bg = pg.evaluate("getComputedStyle(document.querySelector('#drawer button:has-text(\"保存\")')).backgroundColor")
    del_bg  = pg.evaluate("getComputedStyle(document.querySelector('#drawer button:has-text(\"删除此任务\")')).backgroundColor")
    print("SAVE_BG:", save_bg, "DEL_BG:", del_bg)
    b.close()
```

> 兜底：若 Playwright 启动失败（浏览器/驱动缺失），改走**人工点击路径**——按 §二各 L1 用例的「人工步骤」逐项操作并对照期望，结果记录为 通过/失败。

---

## 二、逐 AC 测试用例

> 状态枚举（契约）：`STATUS_OK = {待办, 进行中, 待验证, 已验证, 完成, 阻塞}`（阻塞旁路态）。
> 项目 19 当前分布（基线）：12 条 = 完成×10 + 待办×2 → 进度条期望 `0 进行中 · 0 待验证 · 10 已完成 / 12`（实现后以实际 API 返回为准，用例写「与 API 逐条一致」）。

### AC-1.1 详情入口显式化（P0-1，方案 A：加显式「详情」按钮，现有交互保持）

| 用例 | 手段 | 命令/步骤 | 期望 | 判定标准 |
|---|---|---|---|---|
| **T-1.1-1**（L0）详情按钮存在 | grep index.html `build()` 卡片渲染段 | `grep -n "详情" shared_board/index.html`；重点看卡片 `card.append(...)` 附近出现按钮元素（`document.createElement("button")` 或模板串），文本含「详情」 | 卡片渲染中存在显式「详情」按钮（**非**仅抽屉标题「任务详情」/详情 label）；按钮 onclick 绑定 `openDrawer(t.id)` | **PASS**：卡片级「详情」按钮 + 点击开抽屉绑定。<br>**FAIL**：无按钮 / 仅抽屉标题命中（详情入口未落地）→ Engineer |
| **T-1.1-2**（L0 · **K1 专项**）详情按钮不冒泡 | grep 详情按钮 handler | 详情按钮 onclick 内含 `stopPropagation()` 或 `e.stopPropagation()`；且 handler 直接调 `openDrawer(...)` 而非 `card.onclick` 逻辑 | 点详情**不会**同时触发展开切换 | **PASS**：handler 有 stopPropagation 且直调 openDrawer。<br>**FAIL（K1 命中）**：无 stopPropagation（点详情→展开被切换）→ Engineer |
| **T-1.1-3**（L0）现有交互零改动 | grep index.html | ① `card.onclick` 展开切换仍在；② `card.ondblclick` = openDrawer 仍在；③ `card.ontouchstart/ontouchend` 长按 500ms 逻辑仍在 | 三处交互 handler 均存在且逻辑未变 | **PASS**：三处齐全。<br>**FAIL**：任一被删/改（回归红线）→ Engineer |
| **T-1.1-L1-1**（L1 浏览器）详情按钮点击开详情 | Playwright 或人工 | 浏览器打开 8787/board（或 8788）→ 选项目 19 → 点任一卡片上的「详情」按钮 | 抽屉（#drawer.show）打开，标题/状态/详情字段与该任务一致 | **PASS**：抽屉开 + 字段对。<br>**FAIL**：不弹/弹错任务 → Engineer |
| **T-1.1-L1-2**（L1 浏览器）单击展开不回归 | Playwright 或人工 | 点一个**有子任务**的卡片（非「详情」按钮）→ 再点一次 | 第一次展开子任务（.children.open），第二次收起；**不**打开抽屉 | **PASS**：展开/收起切换正常且无抽屉。<br>**FAIL**：单击开抽屉/不展开 → Engineer |
| **T-1.1-L1-3**（L1 浏览器）双击详情不回归 | Playwright 或人工 | 桌面双击卡片（非按钮） | 抽屉打开 | **PASS**：双击开详情。<br>**FAIL**：无反应/被单击展开抢占 → Engineer |
| **T-1.1-L1-4**（L1 浏览器 · 移动端）长按详情不回归 | Playwright（viewport 375×667 touch）或人工 | 手机视口长按卡片 500ms | 抽屉打开 | **PASS**：长按开详情。<br>**FAIL**：无反应 → Engineer（移动端回归） |
| **T-1.1-L1-5**（L1 浏览器 · **K1 实测**）详情与展开互不干扰 | Playwright 或人工 | 对**有子任务**的卡片：先点「详情」按钮 | 抽屉打开且该卡片**未展开/未收起**（子任务区状态不变） | **PASS**：点详情只开抽屉。<br>**FAIL（K1 命中）**：子任务区状态被切换 → Engineer |

### AC-1.2 顶部进度概览（P0-2）

| 用例 | 手段 | 命令/步骤 | 期望 | 判定标准 |
|---|---|---|---|---|
| **T-1.2-1**（L0）进度渲染逻辑存在 | grep index.html | 存在进度渲染函数（如 `renderProgress()`），从 `tasks` 数组按状态计数（`filter`/`reduce`），输出格式含「进行中」「待验证」「已完成」「总数」；在 `load()`/`render()` 中调用 | 计数逻辑存在 + 文案格式 `X 进行中 · Y 待验证 · Z 已完成 / 总数` | **PASS**：函数 + 格式串齐全。<br>**FAIL**：无计数/无格式 → Engineer |
| **T-1.2-2**（L0 · **K2 口径专项**）计数口径 | grep 计数逻辑 | `已完成` 只统计 `status==="完成"`；`待验证` 只统计 `status==="待验证"`；`进行中` 只统计 `status==="进行中"`；总数=全部任务条数（含待办/阻塞/已验证） | 口径与任务树逐条一致 | **PASS**：X/Y/Z 各自只计对应状态，总数=任务数组 length。<br>**FAIL（K2 命中）**：把「待办/阻塞/已验证」误入 X/Y/Z 或总数≠任务数 → Engineer |
| **T-1.2-3**（L0）实时更新挂钩 | grep index.html | 进度渲染在 `load()` 拉取 tasks 后调用（含 `setInterval` 5s 轮询路径与保存/新建后的 `load()` 路径） | 每次数据刷新进度条同步刷新 | **PASS**：进度渲染挂载于 load 主链路。<br>**FAIL**：仅初始渲染一次 → Engineer |
| **T-1.2-L1-1**（L1 浏览器只读）数字与 API 逐条一致 | Playwright 或人工 + python | ① 浏览器选项目 19，读进度条文案；② `curl.exe -s "http://127.0.0.1:8788/api/tasks?project_id=19"` 用 python `Counter(status)` | 进度条 `X 进行中 · Y 待验证 · Z 已完成 / 总数` 与 API 分布**完全一致**（当前基线期望 `0 进行中 · 0 待验证 · 10 已完成 / 12`，实现后以实际为准） | **PASS**：X==API(进行中) 且 Y==API(待验证) 且 Z==API(完成) 且 总数==len(tasks)。<br>**FAIL**：任一不一致 → Engineer |
| **T-1.2-L1-2**（L1 浏览器只读）多态项目显示 | Playwright 或人工 | 切换项目 4/18/19，逐一核对进度条 vs API 分布 | 每个项目进度条均与对应 API 一致 | **PASS**：全项目一致。<br>**FAIL**：任一项目不一致 → Engineer |
| **T-1.2-L1-3**（L1-隔离实例 · 写路径）状态切换实时更新 | 临时实例 8799 + 临时 DB | ① 建临时任务 A（status=待办，title 含 `QA-T08-PROG-<ts>`）→ 进度条 `待办+1`（总数+1）；② 将 A 改 status=进行中 → 进度条「进行中+1、总数不变」；③ 改 status=完成 → 「已完成+1、进行中-1」；④ 删除 A → 数字回退 | 进度条随状态切换**实时**更新（保存后立即或 ≤5s 轮询内） | **PASS**：四步数字均正确且回退。<br>**FAIL**：数字不更新/错位 → Engineer。测试数据在临时 DB，用毕即删（§1.3 清理） |

### AC-1.3 删除按钮弱化（P0-3）

| 用例 | 手段 | 命令/步骤 | 期望 | 判定标准 |
|---|---|---|---|---|
| **T-1.3-1**（L0）样式降级 | grep index.html | 删除按钮不再单独 `class="danger"` 红底：查找 `删除此任务` 所在 button 的 class；应含次级样式（如 `ghost danger` / `outline` / `danger-subtle` / 小字号）或移出主操作行 | 视觉明显弱于保存按钮（保存为主按钮样式） | **PASS**：删除按钮 class 为次级样式（非纯 `danger` 主样式）。<br>**FAIL**：仍是 `class="danger"` 红底大字（未弱化）→ Engineer |
| **T-1.3-2**（L0 · **K3 专项**）确认保留 | grep delTask() | `delTask()` 函数内仍有 `confirm("删除此任务及所有子任务？")` 且 `if(!confirm(...)) return;` 守卫；DELETE 请求仍 `method:"DELETE"` | 二次确认**必须保留** | **PASS**：confirm 守卫存在。<br>**FAIL（K3 命中）**：confirm 被删/绕过 → Engineer |
| **T-1.3-3**（L1 浏览器 · 样式断言） | Playwright | 打开抽屉，`getComputedStyle` 对比「保存」vs「删除此任务」按钮：backgroundColor / 字号 / padding | 删除按钮背景非强红（如透明/浅色/描边），视觉权重 < 保存 | **PASS**：删除按钮 computed style 明显弱于保存。<br>**FAIL**：仍红底与保存同级 → Engineer |
| **T-1.3-4**（L1 浏览器 · **数据安全**）弹窗出现→取消 | Playwright 或人工 | 点「删除此任务及子任务」→ 弹确认框 → **点取消** | 弹窗出现（confirm 触发）；取消后任务**未被删除**（任务数不变、卡片还在） | **PASS**：弹窗出现 + 取消零删除。<br>**FAIL**：不弹窗直接删（K3）/取消仍删 → Engineer。<br>**本用例零删除，线上可安全执行** |
| **T-1.3-5**（L1-隔离实例 · 写路径）确认后删除正常 | 临时实例 8799 + 临时 DB | 建临时任务 B（含子任务 C）→ 点删除 → 弹窗点确认 | B 与子任务 C 均被删除（总数-2），抽屉关闭 | **PASS**：子树删除正常。<br>**FAIL**：删不动/误删其他 → Engineer。仅临时 DB，用毕即删 |

### AC-1.4 回归红线（展开/收起、状态切换、保存、新建、5 态、阻塞、日志、后端零改动）

| 用例 | 手段 | 命令/步骤 | 期望 | 判定标准 |
|---|---|---|---|---|
| **T-1.4-1**（L0）5 态+阻塞下拉完整 | grep index.html 抽屉 select | `d_status` 下拉含 6 个 option：待办/进行中/待验证/已验证/完成/阻塞 | 全量在 | **PASS**：6 态齐。<br>**FAIL**：缺任一 → Engineer |
| **T-1.4-2**（L0）徽标样式规则完整 | grep index.html CSS | `.badge[data-status="待办"/"进行中"/"待验证"/"已验证"/"完成"/"阻塞"]` 6 条规则存在 | 徽标样式未删 | **PASS**：6 规则齐。<br>**FAIL**：缺任一（显示回退）→ Engineer |
| **T-1.4-3**（L0 · **K4 后端零改动专项**） | git diff | `git diff --exit-code shared_board/server.py`；`git status --short shared_board/server.py`；对比 server.py mtime 是否变化 | server.py 零改动（diff 净） | **PASS**：diff 净 + mtime 未变。<br>**FAIL（K4 命中）**：server.py 被改 → 退回 Engineer（超范围） |
| **T-1.4-4**（L0）日志/保存/新建结构完好 | grep index.html | `renderAudit`/`loadAudit`、`saveDrawer`、`addRoot`/`addChild`、`delTask` 函数均存在 | 主功能函数未被删改 | **PASS**：函数齐全。<br>**FAIL**：缺失 → Engineer |
| **T-1.4-L1-1**（L1 浏览器）保存回归 | 临时实例或人工（只读项目） | 打开抽屉改标题→点保存 | 抽屉关闭，任务树标题更新（若只读环境改为「点保存不报错、数据未变」） | **PASS**：保存正常。<br>**FAIL**：保存失败/报错 → Engineer |
| **T-1.4-L1-2**（L1 浏览器）新建回归 | 人工 | 点「+ 主任务」→ 树中出现「新任务」；有子任务卡片点「+ 子任务」 | 新建正常 | **PASS**：主/子任务新建可用。<br>**FAIL**：新建失败 → Engineer |
| **T-1.4-L1-3**（L1-隔离实例）状态切换回归 | 临时实例 8799 | 建临时任务 → 抽屉下拉切「阻塞」→ 保存 → 卡片徽标显示「阻塞」红色样式 | 5 态+阻塞切换显示正常 | **PASS**：阻塞态显示正确。<br>**FAIL**：徽标错/不更新 → Engineer |
| **T-1.4-L1-4**（L1 浏览器）日志回归 | Playwright 或人工 | 打开项目 19，页面底部「操作日志」区渲染最近条目（`[ts] agent action target`），非空 | 日志正常显示 | **PASS**：日志区有内容。<br>**FAIL**：空/报错 → Engineer |
| **T-1.4-L1-5**（L1 只读）接口/页面回归 | curl.exe + python | ① `/ext/status`、`/ext/projects`、`/ext/tasks?project_id=19`、`/ext/audit?project_id=19`、`/ext/presence`、`/ext/notes?project_id=19`（8787）→ 6×200；② `/studio`、`/board`、`8787/`、`8788/` → 4×200；③ `8787/board` HTML 含新标记（详情按钮/进度条文案/删除新样式） | 后端接口零回归 + 新前端已生效 | **PASS**：6×200 + 4×200 + HTML 含新标记。<br>**FAIL**：任一非 200 / HTML 无新标记（未生效→先强制刷新浏览器再判）→ Engineer |
| **T-1.4-L1-6**（L1 只读）实时轮询不回归 | Playwright | 浏览器停留 ≥6s，观察任务树/进度条/日志随 `setInterval` 5s 轮询刷新无报错 | 轮询正常 | **PASS**：无报错、数据持续刷新。<br>**FAIL**：控制台报错/停更 → Engineer |

---

## 三、回归项（汇总红线）

| 项 | 手段 | 期望 | 判定 |
|---|---|---|---|
| 后端零改动（K4） | `git diff --exit-code shared_board/server.py` + mtime | 净 | PASS=净；FAIL=被改 → 整体退回 |
| 展开/收起 | L1 单击有子任务卡片两次 | 展开→收起 | PASS；FAIL → Engineer |
| 双击/长按详情 | L1 桌面双击 + 移动端长按 | 抽屉开 | PASS；FAIL → Engineer |
| 保存/新建 | L1 保存标题 + 新建主/子任务 | 正常 | PASS；FAIL → Engineer |
| 5 态+阻塞显示 | L0 下拉/CSS + L1 切换显示 | 6 态全 | PASS；FAIL → Engineer |
| 操作日志 | L1 日志区非空 | 正常 | PASS；FAIL → Engineer |
| 接口/页面 | /ext 6×200 + /studio /board /根 4×200 | 全 200 | PASS=全 200；FAIL=任一非 200 |
| 线上 HTML 生效 | curl 8787/board 含新标记 | 新标记在 | PASS=在；FAIL=不在（先清缓存再判，非重启） |

> **回归结论红线**：K4 后端被改 或 展开/保存/新建/日志任一回归 → **整体 FAIL（退回 Engineer）**，即使 AC-1.1~1.3 全过。

---

## 四、判定矩阵

| 等级 | 定义 | 处置 |
|---|---|---|
| **PASS** | 该 AC 全部必过断言满足，无 FAIL 项 | 勾选 AC；进入下一 AC |
| **FAIL** | 任一必过断言不满足（期望按 PRD/现状基线，非测试自身错误） | 记 `[BUG][S|P]`（复现/期望/实际/环境），**路由→ Engineer（源码 bug）**；修复后进 Round 2 回归 |
| **WARN** | 非阻断观察项：实现选择与契约细节不一致但行为正确；测试副作用；主理人待裁决项 | 记录并报主理人裁决，不阻塞放行 |
| **N/A** | 实现未提供可选能力且契约标注可选/跟进 | 跳过并注明，不计 FAIL |

**缺陷路由规则（QA 职责）**：
- 断言期望正确（对照 PRD/基线）但实际输出不符 → **源码 bug → Send to Engineer**。
- 断言本身写错（期望与契约不符）→ **测试 bug → QA 自修**（不派 Engineer）。

**轮次控制（STRICT · 最多 2 轮）**：
- Round 1：写用例→执行→分析。全 PASS → 退出（报主理人）。
- Round 2（Engineer 修复后或 QA 自修后）：回归重跑。全 PASS → 退出；仍有 FAIL → **立即退出，剩余问题记为 Known Issues 交主理人**，不进入 Round 3。

---

## 五、风险与已知边界（预登记 WARN）

1. **WARN-1 实现细节自由度**：详情按钮/进度条的 class 名、DOM 结构为 design 自由；L0 断言按**契约语义**（有按钮/有格式串/口径对）写，不锁死 class 名；L1 Playwright 选择器执行时按实际 DOM 微调（脚本为参考）。
2. **WARN-2 进度条口径的「其余态」归属**：PRD 允许阻塞/待办/其他「单列或并入计数」；若 design 把待办/阻塞/已验证只计入总数（不进 X/Y/Z），属合规——QA 断言以「X/Y/Z 各自只计对应状态 + 总数=任务数组 length」为准，不锁死是否单列。
3. **WARN-3 浏览器缓存**：验证「线上已生效」以 **curl 抓 8787/board HTML** 为准（服务端直读磁盘）；浏览器侧需强制刷新（Ctrl+F5/清缓存）。若浏览器显示旧版而 curl 已含新标记 → 缓存问题非源码问题。
4. **WARN-4 项目 19 分布为基线非契约**：`0 进行中 · 0 待验证 · 10 已完成 / 12` 仅当前快照；执行时以 `/api/tasks?project_id=19` 实时返回为准（用例已写「逐条一致」，不锁死具体数字）。
5. **WARN-5 删除视觉降级的主观性**：样式「明显弱于保存」以 computed style 数值对比 + 人工目测双确认；若实现只微调颜色（如浅红描边），记 WARN 报主理人裁决是否满足「弱化」意图，不单独判 FAIL。
6. **WARN-6 移动端长按回归的可用性**：Playwright touch 视口模拟为近似；若无法自动化，以人工手机实测（同一 WiFi 访问 `http://电脑IP:8788`）兜底。
7. **WARN-7 写路径测试副作用**：AC-1.2-L1-3 / AC-1.3-5 / AC-1.4-L1-3 的临时任务与删除仅在 8799 临时 DB 副本执行（§1.3 清理）；线上零写路径，若执行中断导致临时实例残留，QA 负责清理后再判。

---

## 六、执行产物（测试执行阶段产出，本阶段不产出）

- 本文件勾选版（逐 AC 标 PASS/FAIL/WARN/N/A）
- L0 grep 断言输出存档（详情按钮/进度格式/删除样式/confirm/5 态/日志函数）
- L1 Playwright 运行输出（进度条 vs API 计数、抽屉开合、样式对比）或人工点击路径记录
- 临时实例起停记录（8799 PID、临时 DB 路径、清理确认）
- 缺陷清单（`[BUG][S|P]` 格式，如有）
- K1~K4 专项结论（K1 详情按钮不冒泡、K2 进度口径、K3 confirm 保留、K4 后端零改动）
- 汇总判定 → 经 SendMessage 回传主理人
