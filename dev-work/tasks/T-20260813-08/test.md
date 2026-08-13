# T-20260813-08a 测试文档（test.md）· 看板 UI 视图重做（参考 kanban.html 范式）

> 分层：**L0 离线静态**（不依赖服务，grep 代码核验）｜**L1-线上浏览器**（8788 直连或 8787/board，Playwright 实测 + 人工点击路径兜底；纯前端改动，浏览器强制刷新即可生效，**零重启**）｜**L1-隔离实例**（8799 临时实例 + 临时 DB 副本，**写路径**专用）。
> 状态：**测试文档先行**（老板 19:57 新流程）——本文档只描述计划/用例/判定，不执行任何改动；主理人审过后才进入测试执行。
> 铁律（本阶段 + 执行阶段）：**只写文档/只读探测**；禁止改代码、禁止改 `shared_board/index.html`、禁止重启 8787/8788、禁止删真实数据；执行阶段删除/状态写路径一律走**临时实例 8799 + 临时 DB 副本**，线上仅只读断言 + 删除弹窗出现即取消 + 暗色 localStorage（浏览器本地，无 API 写）。
> 契约来源：PRD `PRD.md`（T-08a 范围：AC-1.1/1.2/1.3/1.8 + 在线样式 + K1 迁移）+ 参考源 `reference_kanban.html`（326 行：泳道/统计条/暗色/toast/filters 范式）+ 现状代码 `shared_board/index.html`（已只读核对，回归红线）+ `server.py`（接口契约：`/api/tasks|projects|presence|audit`、owner 写锁 403、`/ext` 6 端点）+ 上一任务 T-07 验收结论。
> 主理人审视坑位：**K1 详情按钮冒泡**（`stopPropagation` 必须保留，否则点「详情」触发泳道内展开/双开——K1 迁移红线）、**K2 统计口径**（总计=任务数组 length；进行中/待验证/阻塞/完成各自只计对应 status；待办/已验证只入总计——与旧 `renderProg` 口径一致，统计条数字必须与泳道各列逐条一致）、**K3 暗色持久化键**（`localStorage('kanban-dark')` 照参考 + `body.dark`，刷新后保持）、**K4 toast 替代 alert 但 confirm 不得被替**（保存/刷新反馈用 toast；删除二次确认 `confirm` 必须保留）、**K5 后端零改动**（`server.py` git diff 净；presence 仍走 `/api/presence`）——五坑均有专项用例，缺一即退回。

---

## 〇、基线快照（2026-08-13 实现前 · QA 只读实测）

| 探测项 | 结果 | 说明 |
|---|---|---|
| `8787 /`、`8787 /board` | 200 / 200 | 网关在跑（PID **29144**） |
| `8788 /` | 200 | board 直连在跑（PID **13040**） |
| `8799` | 未监听 | 隔离实例专用端口（执行阶段起停，见 §1.3） |
| 8787/board 返回 HTML vs 本地 index.html | 仅差 2 处：① 注入 `<script>window.__BOARD_TOKEN__="…"`；② 网关改写 `api/`→`board/api/`、`/api`→`/board/api`（len 15646 vs 15505） | **服务端逐请求直读磁盘文件**（server.py:150-151）→ 静态改动浏览器强制刷新即生效，无需重启（热刷新证据） |
| 项目列表 `/api/projects` | 3 项：4 看板项目(owner=kanban) / 18 测试项目(老板) / 19 短剧自动化工作流(阿编) | 浏览器实测选项目 19 |
| 项目 19 任务分布（`/api/tasks?project_id=19`，8788 直连） | 12 条 = **完成×10 + 待办×2**（进行中/待验证/已验证/阻塞 = 0）；优先级 紧急×1/高×3/中×7/低×1 | **泳道/统计期望值以此为准**：待办列 2、完成列 10、其余列空；统计条 `总计12 · 进行中0 · 待验证0 · 阻塞0 · 完成10` |
| 项目 19 树结构 | 9 根 + 3 子；task **22**「O4 board机械闸门迁移(当前)」(完成/紧急) 有 3 个子任务 27/28/29（均完成） | 子任务计数徽章 / 展开 / K1 详情不冒泡的**实测对象** |
| 项目 4 / 18 分布 | 4：1 条待办；18：7 条待办 | 多项目切换回归用 |
| presence `/api/presence` | 老板(19:09) / 远程指导(18:41) / 阿编(00:29) | 执行时大概率全 **offline**（last_seen 均超 5min）→ 线上只读断言「渲染成人头+名字、按 last_seen 区分 on/off 样式」；**在线样式实测在 8799 用 X-Agent touch 造在线 agent**（§1.3） |
| audit(项目19) `/api/audit?project_id=19` | 20 条，含 老板 创建任务 `QA-TEST-1909-ok`、远程指导 指导留言 | 审计流回归断言「日志区非空 + 含近期条目」 |
| `git status --short shared_board/server.py shared_board/index.html` | **空（干净）**；`git diff --exit-code server.py` exit=0 | 后端零改动（K5）判别基线：实现后 `server.py` 仍须干净 |
| index.html 现状（改造前） | **树视图**（非泳道）；无统计条/无暗色/无 toast；presence 用「dot+名字」（非人头）；drawer 已有 5 态+优先级+详情+子任务+`delbtn`；详情按钮已带 `stopPropagation`（:205）；`delTask()` 有 `confirm("删除此任务及所有子任务？")`（:172）；`renderProg()` 进度概览在（:226） | 泳道/统计条/暗色/toast/在线人头样式 = **新增**；drawer/详情按钮/confirm/多项目/复制派单/审计 = **保留（回归红线）**；K1 迁移 = 详情按钮 + 进度概览（→统计条）迁入新 UI |
| 参考源 `reference_kanban.html` | 326 行：`:root`/`.dark` 双主题变量、`.stats` 统计条、`.col/.col-header/.count` 泳道、`.card` 卡片、`#toast`+`showToast`、`btnDark`+`localStorage('kanban-dark')`、filters 按钮组 | 实现对照抄样式；数据/功能走我们的 API |
| Playwright 可用性 | **python-playwright 已装**；chromium 缓存齐（chromium-1169/1208/1228/1234 + headless_shell）；Edge/Chrome 本机存在 | L1 浏览器实测首选；无则走人工点击路径（§1.4） |
| node/npm | v22.22.2 / 10.9.7；`npx playwright` 可按需装 1.62.1 | 备用方案 |

> 基线结论：**L0 无需起服务（grep 文件即可）**；**L1 浏览器实测用现有 8787/8788，不重启**；写路径（建临时任务/改状态/删临时任务/造 presence/造 待验证·已验证 任务）走 **8799 临时实例 + 临时 DB 副本**（沿用 T-08 §1.3 起停模板）。

---

## 一、测试计划

### 1.1 分层选择

| 层 | 范围 | 依赖 | 污染面 |
|---|---|---|---|
| **L0 离线静态** | 代码核验（改造后 `index.html`）：AC-1.1 泳道 6 列分组+列计数逻辑；AC-1.2 统计条口径；AC-1.3 暗色变量块+持久化键；toast 结构；AC-1.8 待验证 amber/已验证 purple 配色；在线 👤 人头渲染；K1 详情按钮 stopPropagation + 进度概览迁移；回归（drawer 6 态下拉/优先级/saveDrawer/addChild/delTask confirm/delbtn 弱样式/projSel/copyDispatch/loadAudit）；K5 `server.py` git 净 | 无服务 | 零 |
| **L1-线上浏览器（只读交互）** | 8788 直连或 8787/board，Playwright：泳道分组/统计一致/暗色切换持久化/在线样式/详情开抽屉/进度概览/toast/删除弹窗出现即取消/复制派单/审计/多项目/轮询 | 8787/8788 在跑 + Playwright | 零（无 API 写路径；删除只到弹窗→取消；暗色仅 localStorage） |
| **L1-隔离实例（写路径）** | 8799 临时 board 实例 + 临时 DB 副本：建 待验证/已验证 任务→配色断言；造在线 agent→头像样式断言；建临时任务→状态切换→统计/泳道实时更新；抽屉编辑保存/子任务/删除 confirm 确认后/写锁 403 | 本地 python | 仅 $env:TEMP 临时文件，零污染线上 |

**执行顺序**：L0 静态 → L1-线上只读（浏览器实测）→ L1-隔离实例（写路径）→ 汇总判定。**L0 全过才进 L1**（L0 抓实现缺失/口径错，L1 抓交互/实时性/视觉）。

### 1.2 铁律（执行阶段强制）

1. **不重启 8787/8788**：记录 PID（基线 29144/13040），全程前后一致；服务端直读磁盘，静态改动强制刷新浏览器（Ctrl+F5 / 清缓存）即生效，**不以重启作为验证手段**。
2. **线上零 API 写路径**：状态切换/保存/新建/删除/造 presence 等写测试一律走 **8799 临时实例 + 临时 DB 副本**；线上仅只读断言（API GET、浏览器只读交互、删除弹窗出现→取消、暗色 localStorage、复制派单 clipboard——均无 API 写）。
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

**临时实例起停（L1-隔离实例写路径用，沿用 T-08 §1.3 模板，非源码改动）**：

```powershell
$ts = Get-Date -Format "HHmmss"
Copy-Item shared_board\board.db "$env:TEMP\qa_board_t08a_$ts.db" -Force
$tok = (Select-String -Path shared_board\.env -Pattern '^BOARD_TOKEN=(.+)$').Matches[0].Groups[1].Value.Trim()
$env:BOARD_TOKEN = $tok
Start-Process -WindowStyle Hidden -FilePath python -ArgumentList @(
  '-c', "import sys; sys.path.insert(0, r'C:\Users\67972\WorkBuddy\workbuddy\shared_board'); import server; server.DB = r'$env:TEMP\qa_board_t08a_$ts.db'; from http.server import HTTPServer; HTTPServer(('127.0.0.1', 8799), server.H).serve_forever()")
curl.exe -s -o NUL -w "8799=%{http_code}\n" http://127.0.0.1:8799/api/projects
# 造「在线」agent（写路径专用）：GET 带 X-Agent 即 touch presence（server.py:168-169），last_seen=now → 前端判在线
curl.exe -s -H "X-Agent: QA-ONLINE-$ts" http://127.0.0.1:8799/api/projects
# 用毕：杀 8799 + 删临时 DB
$p = Get-NetTCPConnection -LocalPort 8799 -State Listen | Select-Object -ExpandProperty OwningProcess
Stop-Process -Id $p -Force; Remove-Item "$env:TEMP\qa_board_t08a_$ts.db" -Force
```

> 说明：8799 跑**同一份 server.py + 同一份 index.html**（静态文件同目录直读），UI 与写路径结果可迁移到线上结论；线上仍保留只读抽查。

### 1.4 测试工具

| 工具 | 用途 |
|---|---|
| **L0 grep（首选，无需服务）** | 对改造后 `shared_board/index.html` 做断言式 grep：泳道分组/列计数/统计口径/暗色/ toast/新态配色/在线头像/详情按钮 stopPropagation/drawer 6 态/confirm/写锁错误面 |
| **python（urllib）** | 只读接口断言：`/api/tasks?project_id=19` 计数、`/api/projects`、`/api/presence`、`/api/audit`，交叉核对统计条/泳道数字 |
| **curl.exe** | 只读接口探测（状态码）；抓 8787/board HTML 做「线上已生效」静态断言 |
| **Playwright（python）** | L1 浏览器实测：泳道卡数/统计条/暗色切换持久化/详情开抽屉/在线样式/toast/删除弹窗/复制派单。**已探测可用**（§〇） |
| **人工点击路径** | Playwright 不可用时的兜底：按 §二 L1 用例的「人工步骤 + 期望」逐项手测 |

**Playwright 参考脚本**（执行阶段生成 `$env:TEMP\qa_t08a_ui.py`，测试工件非源码；选择器以实现后实际 DOM 为准——参考范式 class：`.col`/`.col-header .count`/`.stats`/`#btnDark`/`#toast`/`.avatar`）：

```python
# -*- coding: utf-8 -*-
import json, re
from collections import Counter
from playwright.sync_api import sync_playwright
import urllib.request

BASE = "http://127.0.0.1:8788"   # 或 http://127.0.0.1:8787/board
PID = 19

def api_count():
    d = json.load(urllib.request.urlopen(f"{BASE}/api/tasks?project_id={PID}"))
    return len(d), Counter(t["status"] for t in d)

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)  # 本机 Edge；无则 channel="chrome"
    pg = b.new_page(viewport={"width": 1560, "height": 900})
    pg.on("dialog", lambda d: d.dismiss())   # 删除弹窗一律取消（零删除）
    pg.goto(BASE, wait_until="networkidle")
    pg.select_option("#projSel", str(PID)); pg.wait_for_timeout(1500)

    n, c = api_count()
    # 1) 泳道卡数：按列头文本定位 .col，统计其中 .card 数 + 读 .count 徽章
    for label in ["待办", "进行中", "待验证", "已验证", "完成", "阻塞"]:
        col = pg.locator(f".col:has(.col-header:has-text('{label}'))")
        badge = col.locator(".count").inner_text()
        cards = col.locator(":scope > .col-body > .card, :scope > .col-body .col-inner .card").count()
        print(f"LANE {label}: badge={badge} cards={cards}")
    # 2) 统计条
    print("STATS:", pg.locator(".stats").inner_text())
    # 3) 暗色切换
    pg.click("#btnDark"); pg.wait_for_timeout(300)
    print("DARK_CLASS:", pg.evaluate("document.body.classList.contains('dark')"))
    print("LS_DARK:", pg.evaluate("localStorage.getItem('kanban-dark')"))
    pg.reload(wait_until="networkidle"); pg.wait_for_timeout(1200)
    print("DARK_AFTER_RELOAD:", pg.evaluate("document.body.classList.contains('dark')"))
    # 4) 详情按钮开抽屉 + 不冒泡（task 22 有 3 子任务）
    card22 = pg.locator(".card:has-text('O4 board机械闸门迁移')").first
    before = pg.evaluate("document.querySelectorAll('.children.open, .subtree.open').length")
    card22.locator("button:has-text('详情')").click(); pg.wait_for_timeout(400)
    print("DRAWER_OPEN:", pg.locator("#drawer.show").count() > 0)
    print("TITLE_FIELD:", pg.locator("#d_title").input_value())
    print("EXPAND_CHANGED:", before != pg.evaluate("document.querySelectorAll('.children.open, .subtree.open').length"))
    pg.locator("#drawer button:has-text('关闭')").click()
    # 5) 刷新 toast
    pg.click("#btnRefresh"); pg.wait_for_timeout(300)
    print("TOAST_SHOW:", pg.locator("#toast.show").count() > 0, "TEXT:", pg.locator("#toast").inner_text())
    # 6) 在线条：avatar 数 vs API
    av = pg.locator("#presence .avatar").count()
    pres = json.load(urllib.request.urlopen(f"{BASE}/api/presence"))
    print("PRESENCE_AVATARS:", av, "API_AGENTS:", len(pres))
    b.close()
```

> 兜底：若 Playwright 启动失败（浏览器/驱动缺失），改走**人工点击路径**——按 §二各 L1 用例的「人工步骤」逐项操作并对照期望，结果记录为 通过/失败。

---

## 二、逐 AC 测试用例

> 状态枚举（契约）：`STATUS_OK = {待办, 进行中, 待验证, 已验证, 完成, 阻塞}`（阻塞旁路态）。
> 项目 19 当前分布（基线）：12 条 = 完成×10 + 待办×2 → 泳道期望 `待办2 / 进行中0 / 待验证0 / 已验证0 / 完成10 / 阻塞0`；统计条期望 `总计12 · 进行中0 · 待验证0 · 阻塞0 · 完成10`（实现后以实际 API 返回为准，用例写「与 API 逐条一致」）。

### AC-1.1 泳道按 5 态正确分组（+阻塞列），每列计数对

| 用例 | 手段 | 命令/步骤 | 期望 | 判定标准 |
|---|---|---|---|---|
| **T-1.1-1**（L0）泳道分组逻辑存在 | grep index.html | 存在列定义（数组/映射）含 6 项：待办/进行中/待验证/已验证/完成/阻塞；渲染时按 `t.status` 分组入列；列头含计数徽章元素；board 容器 `overflow-x:auto` | 6 列分组 + 列计数 + 横向滚动 | **PASS**：分组逻辑 + 计数徽章 + overflow-x:auto 齐全。<br>**FAIL**：缺列/无计数/无横向滚动 → Engineer |
| **T-1.1-2**（L0）空态存在 | grep index.html | 空列渲染「暂无任务」类空态文案 | 空列有占位 | **PASS**：空态文案在。<br>**FAIL**：空列白板 → Engineer |
| **T-1.1-3**（L0）子任务计数徽章 | grep index.html | 卡片渲染含子任务计数（`children`/`parent_id` 统计） | 有子任务的卡显示计数 | **PASS**：计数逻辑在。<br>**FAIL**：无 → Engineer（回归红线之一） |
| **T-1.1-L1-1**（L1 浏览器）项目 19 泳道分组 | Playwright 或人工 + python | 浏览器选项目 19 → 逐列读 `count` 徽章 + 数卡；`python` 交叉核对 `Counter(status)` | 待办列 **2** 张卡、完成列 **10** 张卡、进行中/待验证/已验证/阻塞列空（空态文案）；列计数徽章 = `2/0/0/0/10/0` | **PASS**：徽章与卡数双一致且 == API 分布。<br>**FAIL**：任一列错/计数不符 → Engineer |
| **T-1.1-L1-2**（L1 浏览器）多项目泳道 | Playwright 或人工 | 切换项目 4/18/19，逐项目核对泳道 vs API | 每项目分组与 API 一致（4：待办1；18：待办7；19：见上） | **PASS**：全项目一致。<br>**FAIL**：任一不一致 → Engineer |
| **T-1.1-L1-3**（L1 浏览器）空态可见 | Playwright 或人工 | 项目 19 看 进行中/待验证/已验证/阻塞 列 | 空列显示「暂无任务」类空态 | **PASS**：空态在。<br>**FAIL**：空白/报错 → Engineer |
| **T-1.1-L1-写-1**（L1-隔离 · 写路径）状态切换后泳道实时更新 | 临时实例 8799 + 临时 DB | ① 建临时任务 A（status=待办，title 含 `QA-T08A-LANE-<ts>`）→ 待办列+1、徽章=3；② 改 A=进行中 → 待办-1、进行中+1；③ 改 A=待验证 → 待验证列出现 1 卡；④ 改 A=完成 → 完成+1；⑤ 删除 A → 全部回退 | 泳道分组/计数随状态切换**实时**更新（保存后立即或 ≤5s 轮询内） | **PASS**：五步数字均正确且回退。<br>**FAIL**：不更新/错位 → Engineer。仅临时 DB，用毕即删 |

### AC-1.2 统计条数字与泳道各列一致（总计/进行中/待验证/阻塞/完成）

| 用例 | 手段 | 命令/步骤 | 期望 | 判定标准 |
|---|---|---|---|---|
| **T-1.2-1**（L0）统计渲染逻辑存在 | grep index.html | 存在统计渲染（函数/内联），从 `tasks` 按状态计数：`总计=length`；进行中/待验证/阻塞/完成 各自只计对应 status；输出含「总计/进行中/待验证/阻塞/完成」 | 5 项统计 + 口径 | **PASS**：5 项计数 + 口径正确。<br>**FAIL**：无计数/缺项/口径错 → Engineer |
| **T-1.2-2**（L0 · **K2 口径专项**）计数口径 | grep 统计逻辑 | `总计` = 任务数组 length（含 待办/已验证/阻塞）；`进行中` 只计 `status==="进行中"`；`待验证` 只计 `待验证`；`阻塞` 只计 `阻塞`；`完成` 只计 `完成` | 与泳道各列逐条一致 | **PASS**：X/Y/Z/W/V 各自只计对应状态，总计=任务数。<br>**FAIL（K2 命中）**：把「待办/已验证」误入 X/Y/Z/W/V 或总计≠任务数 → Engineer |
| **T-1.2-3**（L0）实时更新挂钩 | grep index.html | 统计渲染在 `load()` 拉取 tasks 后调用（初始 + 轮询 + 保存/新建后） | 每次数据刷新统计同步刷新 | **PASS**：挂载于 load 主链路。<br>**FAIL**：仅初始一次 → Engineer |
| **T-1.2-L1-1**（L1 浏览器）统计 vs API 逐条一致 | Playwright 或人工 + python | 浏览器选项目 19 读统计条；python `Counter(status)` 交叉核对 | `总计12 · 进行中0 · 待验证0 · 阻塞0 · 完成10`（实现后以实际 API 为准，逐条一致） | **PASS**：5 项全 == API。<br>**FAIL**：任一不一致 → Engineer |
| **T-1.2-L1-2**（L1 浏览器）统计 vs 泳道列计数 | Playwright 或人工 | 同屏读统计条 + 各列 `count` 徽章 | 统计条每项 == 对应列徽章 | **PASS**：完全一致。<br>**FAIL**：不一致 → Engineer |
| **T-1.2-L1-写-1**（L1-隔离 · 写路径）状态切换统计实时更新 | 临时实例 8799 | 沿用 T-1.1-L1-写-1 五步，同步读统计条 | 统计随状态切换实时正确（待办只入总计；进行中/待验证/阻塞/完成 进对应项） | **PASS**：五步统计与泳道同步。<br>**FAIL**：统计与泳道脱节 → Engineer |

### AC-1.3 暗色切换生效且 localStorage 持久化（刷新后保持）

| 用例 | 手段 | 命令/步骤 | 期望 | 判定标准 |
|---|---|---|---|---|
| **T-1.3-1**（L0）暗色变量块 | grep index.html | CSS 含 `.dark` 变量块：`--bg:#0f172a` `--card-bg:#1e293b` `--text:#e2e8f0` `--border:#334155`（照参考）；亮色 `:root` 块在 | 双主题变量 | **PASS**：`:root` + `.dark` 双块、暗色 4 令牌正确。<br>**FAIL**：缺暗色块/令牌错 → Engineer |
| **T-1.3-2**（L0 · **K3 专项**）切换 + 持久化逻辑 | grep index.html | 存在暗色按钮（`btnDark` 或同类）；click handler：`body.classList.toggle('dark')` + `localStorage.setItem('kanban-dark', dark?'1':'0')`；初始读 `localStorage.getItem('kanban-dark')==='1'` 加 `dark` 类；按钮图标 🌙/☀️ 随状态切换 | 切换 + 持久化键照参考 | **PASS**：toggle + setItem + 初始读取三处齐、键为 `kanban-dark`。<br>**FAIL（K3 命中）**：无 localStorage / 键不同 → Engineer |
| **T-1.3-L1-1**（L1 浏览器）暗色切换生效 | Playwright 或人工 | 点 🌙 → 断言 `document.body.classList.contains('dark')` + `localStorage.getItem('kanban-dark')` | `dark` 类 + `localStorage='1'`；按钮变 ☀️；背景色变暗（computed `--bg`） | **PASS**：类 + localStorage + 图标 + computed 背景四断言齐。<br>**FAIL**：任一 → Engineer |
| **T-1.3-L1-2**（L1 浏览器 · **K3 实测**）刷新后保持 | Playwright | 切暗色后 `pg.reload()` → 再断言 | 刷新后仍 `dark` 类 + 背景仍暗 | **PASS**：持久化生效。<br>**FAIL（K3 命中）**：刷新回亮色 → Engineer |
| **T-1.3-L1-3**（L1 浏览器）切回亮色 | Playwright | 再点 ☀️ → 断言 | `dark` 类移除 + `localStorage='0'` | **PASS**：双向可切。<br>**FAIL**：不可逆 → Engineer |

### AC-1.6 toast（T-08a 视图重做必备：保存成功/失败/刷新反馈）

| 用例 | 手段 | 命令/步骤 | 期望 | 判定标准 |
|---|---|---|---|---|
| **T-1.6-1**（L0）toast 结构 | grep index.html | 存在 `#toast` 元素 + `showToast(msg)`（加 `.show` 类 + 延时移除，约 2s）；CSS `.toast` 底部居中 + `.toast.show` 淡入 | 结构 + 函数 | **PASS**：元素 + 函数 + 样式齐。<br>**FAIL**：无 toast（仍 alert 也可接受?——见 K4）→ 若保存/刷新仍用 alert 记 FAIL 退回 Engineer（PRD 明确 toast 替代 alert） |
| **T-1.6-L1-1**（L1 浏览器）手动刷新 toast | Playwright 或人工 | 点刷新按钮 → 断言 `#toast.show` 出现且文案含「刷新/已刷新」 | toast 出现，2s 后消失 | **PASS**：出现 + 文案 + 自动消失。<br>**FAIL**：无 toast → Engineer |

### AC-1.8 新态配色可见：待验证=amber、已验证=purple

| 用例 | 手段 | 命令/步骤 | 期望 | 判定标准 |
|---|---|---|---|---|
| **T-1.8-1**（L0）待验证 amber | grep index.html CSS | `待验证` 状态规则（徽章/边条/色变量）色值属 **amber 系**（`#f59e0b`/`#d97706`/`#a16207`/`#fef3c7` 族） | amber 配色 | **PASS**：待验证 amber 族。<br>**FAIL**：非 amber（如蓝/灰）→ Engineer |
| **T-1.8-2**（L0）已验证 purple | grep index.html CSS | `已验证` 状态规则色值属 **purple 系**（`#8b5cf6`/`#7c3aed`/`#4338ca`/`#ede9fe` 族） | purple 配色 | **PASS**：已验证 purple 族。<br>**FAIL**：非 purple → Engineer |
| **T-1.8-3**（L0）两态可区分 | grep index.html CSS | 待验证与已验证色值**不同**（amber ≠ purple） | 视觉可区分 | **PASS**：两规则色值不同。<br>**FAIL**：同色/缺一 → Engineer |
| **T-1.8-L1-写-1**（L1-隔离 · 写路径）新态配色实测 | 临时实例 8799 + 临时 DB | ① 建临时任务 C1（status=待验证）→ 读卡片状态徽章/边条 `getComputedStyle`；② 建 C2（status=已验证）→ 同样读取 | C1 徽章/边条色 ∈ amber 系；C2 ∈ purple 系；两者 computed 色不同 | **PASS**：两色正确且可区分。<br>**FAIL**：色错/同色 → Engineer。仅临时 DB |

### 在线 👤 样式化（presence 数据 → 人头+名字，在线/离线一眼可见）

| 用例 | 手段 | 命令/步骤 | 期望 | 判定标准 |
|---|---|---|---|---|
| **T-online-1**（L0）presence 渲染逻辑 | grep index.html | `loadPresence()` 仍调 `/api/presence`；`renderPresence` 为每个 agent 渲染**人头头像元素**（圆形、含首字/图标）+ **名字**；按 `last_seen` 距今 ≤5min 判 online/offline，两种样式区分（在线彩色人头/离线灰显或淡化） | 人头+名字 + on/off 区分 | **PASS**：头像元素 + 名字 + online/offline 逻辑齐。<br>**FAIL**：仍只有 dot / 无头像 / 无区分 → Engineer |
| **T-online-L1-1**（L1 浏览器 · 线上现状）presence 渲染 | Playwright 或人工 + python | 打开项目 19 → 断言 `#presence` 内头像元素数 == `/api/presence` agent 数；逐个 agent 名字可见；按 last_seen 计算 on/off 样式正确 | 人头+名字渲染无报错 | **PASS**：头像数 == API 数、名字在、样式按 last_seen。<br>**WARN**：执行时全 offline（§〇 presence 均超 5min）→ 在线样式转 T-online-L1-写-1 实测，本条只断言「渲染不报错 + offline 样式正确」。<br>**FAIL**：渲染报错/头像缺失 → Engineer |
| **T-online-L1-写-1**（L1-隔离 · 写路径）在线 vs 离线样式 | 临时实例 8799 + 临时 DB | ① `curl.exe -H "X-Agent: QA-ONLINE-$ts" http://127.0.0.1:8799/api/projects`（touch 造在线 agent）；② 浏览器打开 8799 项目 19 → 断言 | `QA-ONLINE-<ts>` 显示**在线样式**（彩色人头+名字）；复制库中的 老板(19:09) 等旧 agent 显示**离线样式**（灰/淡化） | **PASS**：在线/离线两种样式正确区分。<br>**FAIL**：无区分/全同色 → Engineer。仅临时 DB |

### K1 迁移：详情按钮点击开抽屉（不触发展开）；进度概览数字正确（与泳道统计一致）

| 用例 | 手段 | 命令/步骤 | 期望 | 判定标准 |
|---|---|---|---|---|
| **T-K1-1**（L0）详情按钮存在 | grep index.html | 卡片渲染中存在显式「详情」按钮（**非**仅抽屉标题「任务详情」）；按钮绑定 `openDrawer(t.id)` | 卡片级详情按钮 | **PASS**：卡片级「详情」按钮 + 开抽屉绑定。<br>**FAIL**：无按钮/仅抽屉标题命中 → Engineer |
| **T-K1-2**（L0 · **K1 专项**）详情按钮不冒泡 | grep 详情按钮 handler | 详情按钮 handler 内含 `stopPropagation()` 或 `e.stopPropagation()`，且直调 `openDrawer(...)` | 点详情**不**触发泳道内展开/其他卡片行为 | **PASS**：handler 有 stopPropagation 且直调 openDrawer。<br>**FAIL（K1 命中）**：无 stopPropagation → Engineer |
| **T-K1-3**（L0）进度概览迁移 | grep index.html | 统计条（或等价进度概览）在渲染主链路中调用，数字来源于 tasks 状态计数（= 旧 `renderProg` 迁移）；K1 详情按钮 + 统计条同时存在 | 详情/进度两能力迁入新 UI | **PASS**：详情按钮 + 统计条（进度概览）均在新 UI。<br>**FAIL**：缺任一（P0×3 能力丢失）→ Engineer |
| **T-K1-L1-1**（L1 浏览器）详情按钮开抽屉 | Playwright 或人工 | 项目 19 点 task 22 卡片「详情」按钮 | 抽屉（#drawer.show）打开；`d_title/d_status/d_priority/d_detail` 与该任务一致 | **PASS**：抽屉开 + 字段对。<br>**FAIL**：不弹/弹错任务 → Engineer |
| **T-K1-L1-2**（L1 浏览器 · **K1 实测**）详情不触发展开 | Playwright 或人工 | 对 task 22（有 3 子任务）：点详情前记录展开状态（`.children.open`/`.subtree.open` 数量），点详情后再记录 | 抽屉开且展开状态**未变** | **PASS**：展开状态不变。<br>**FAIL（K1 命中）**：子任务区被切换 → Engineer |
| **T-K1-L1-3**（L1 浏览器）进度概览数字 == 统计条 == API | Playwright + python | 统计条数字 vs 泳道列计数 vs `Counter(API)` 三向核对（= T-1.2-L1-1/2 合并） | 三向一致 | **PASS**：三向一致。<br>**FAIL**：不一致 → Engineer |
| **T-K1-L1-写-1**（L1-隔离 · 写路径）详情字段随状态同步 | 临时实例 8799 | 建临时任务改状态为 待验证 → 点详情 → 抽屉状态下拉显示「待验证」 | 抽屉字段与当前任务一致 | **PASS**：字段对。<br>**FAIL**：字段陈旧 → Engineer |

### 回归红线（抽屉编辑/5 态切换/保存/子任务/删除弱化 confirm/写锁 403/审计/复制派单/多项目切换）

| 用例 | 手段 | 命令/步骤 | 期望 | 判定标准 |
|---|---|---|---|---|
| **T-reg-1**（L0）drawer 结构完整 | grep index.html | `#drawer` 含：`d_title`、`d_status`（6 option：待办/进行中/待验证/已验证/完成/阻塞）、`d_priority`（4 option：紧急/高/中/低）、`d_detail`、保存按钮、`+ 子任务`、`delbtn` | 编辑能力结构未删 | **PASS**：6 态 + 4 优先级 + 详情 + 保存 + 子任务 + 删除齐。<br>**FAIL**：缺任一 → Engineer |
| **T-reg-2**（L0）保存/新建/删除函数 | grep index.html | `saveDrawer`（PUT）、`addRoot`/`addChild`（POST）、`delTask`（DELETE + `confirm("删除此任务及所有子任务？")` 守卫）均存在 | 主功能函数未删 | **PASS**：函数齐全 + confirm 守卫在。<br>**FAIL**：缺失/confirm 被删（K4 命中）→ Engineer |
| **T-reg-3**（L0）删除弱化样式 | grep index.html | 删除按钮为次级样式（`delbtn`/ghost/小字/描边，视觉弱于保存主按钮），不再红底大字主按钮 | 弱化 | **PASS**：次级样式。<br>**FAIL**：仍主样式 → Engineer |
| **T-reg-4**（L0）多项目/复制派单/审计函数 | grep index.html | `projSel` 下拉 + `setProj`/`load`、`copyDispatch`（clipboard + fallback）、`loadAudit`/`renderAudit` 均存在 | 顶部栏能力保留 | **PASS**：函数齐全。<br>**FAIL**：缺失 → Engineer |
| **T-reg-5**（L0 · **K5 后端零改动专项**） | git diff | `git diff --exit-code shared_board/server.py`；`git status --short shared_board/server.py`；对比 mtime | server.py 零改动 | **PASS**：diff 净 + mtime 未变。<br>**FAIL（K5 命中）**：server.py 被改 → 退回 Engineer（超范围） |
| **T-reg-L1-1**（L1 浏览器）单击卡片开抽屉 | Playwright 或人工 | 点任一卡片（非「详情」按钮） | 抽屉打开（PRD 二.1 新交互：单击卡片=详情 drawer） | **PASS**：单击开抽屉。<br>**FAIL**：无反应 → Engineer |
| **T-reg-L1-2**（L1 浏览器）删除弹窗出现→取消 | Playwright 或人工 | 开抽屉 → 点「删除此任务及子任务」→ 弹 confirm → **点取消** | 弹窗出现；取消后任务未被删除（泳道卡数不变） | **PASS**：弹窗 + 取消零删除。<br>**FAIL**：不弹窗直接删（K4）/取消仍删 → Engineer。<br>**本用例零删除，线上可安全执行** |
| **T-reg-L1-3**（L1 浏览器）复制派单 | Playwright 或人工 | 项目 19 → 点「复制派单」→ 捕获反馈（toast/alert/dialog） | 反馈含「派单」及项目名「短剧自动化工作流」、owner「阿编」；无 API 写 | **PASS**：反馈文案对。<br>**WARN**：clipboard 权限在 headless 可能受限，走 fallbackCopy 文案断言即可。<br>**FAIL**：无反馈/文案错 → Engineer |
| **T-reg-L1-4**（L1 浏览器）审计流 | Playwright 或人工 | 项目 19 底部「操作日志」区 | 非空，含近期条目（如 `QA-TEST-1909-ok`/指导留言） | **PASS**：日志区有内容。<br>**FAIL**：空/报错 → Engineer |
| **T-reg-L1-5**（L1 浏览器）多项目切换 | Playwright 或人工 | 切 4/18/19 | 泳道内容随项目变化，统计随动 | **PASS**：切换正常。<br>**FAIL**：不更新 → Engineer |
| **T-reg-L1-6**（L1 浏览器）轮询不回归 | Playwright | 停留 ≥6s，观察控制台 | 无报错、数据持续刷新（setInterval 轮询在） | **PASS**：无报错、持续刷新。<br>**FAIL**：控制台报错/停更 → Engineer |
| **T-reg-L1-7**（L1 只读）接口/页面回归 | curl.exe + python | ① `/ext/status`、`/ext/projects`、`/ext/tasks?project_id=19`、`/ext/audit?project_id=19`、`/ext/presence`、`/ext/notes?project_id=19`（8787）→ 6×200；② `/studio`、`/board`、`8787/`、`8788/` → 4×200；③ `8787/board` HTML 含新标记（泳道/统计/暗色/toast/头像） | 后端接口零回归 + 新前端已生效 | **PASS**：6×200 + 4×200 + HTML 含新标记。<br>**FAIL**：任一非 200 / HTML 无新标记（未生效→先强制刷新浏览器再判）→ Engineer |
| **T-reg-L1-写-1**（L1-隔离 · 写路径）抽屉编辑保存 | 临时实例 8799 + 临时 DB | 建临时任务 → 开抽屉改 title/status/priority → 保存 | PUT 成功；卡片更新（标题/徽章/优先级）；toast 成功反馈；统计/泳道同步 | **PASS**：保存 + 回显 + 统计同步。<br>**FAIL**：保存失败/不同步 → Engineer |
| **T-reg-L1-写-2**（L1-隔离 · 写路径）子任务回归 | 临时实例 8799 + 临时 DB | 建父任务 P → 建子任务 C（title 含 `QA-T08A-SUB-<ts>`）→ 刷新 | 父卡显示子任务计数=1；展开可见 C；抽屉内/泳道内「+ 子任务」可新增 | **PASS**：计数 + 展开 + 新增齐。<br>**FAIL**：子任务能力回归 → Engineer |
| **T-reg-L1-写-3**（L1-隔离 · 写路径）确认后删除正常 | 临时实例 8799 + 临时 DB | 建父任务 P + 子任务 C → 点删除 → confirm **确认** | P 与 C 均被删除；泳道卡数回退；抽屉关闭 | **PASS**：子树删除 + 回退。<br>**FAIL**：删不动/误删 → Engineer。仅临时 DB |
| **T-reg-L1-写-4**（L1-隔离 · 写路径 · 写锁 403） | 临时实例 8799 + 临时 DB | ① 建项目（owner=QA-OWNER-<ts>）+ 其下任务；② 以 `X-Agent: QA-WRITER-<ts>`（非 owner 非老板）PUT 该任务 → 期望 403；③ 以老板身份 PUT → 期望 200 | 非 owner 写 → 403 `{"error":"无权限修改此任务(owner=…)"}`；前端错误面（toast/ERR）显示不白屏；数据不变 | **PASS**：403 + 前端错误面 + 数据未变。<br>**FAIL**：非 403/前端白屏/数据被改 → Engineer。仅临时 DB |
| **T-reg-L1-写-5**（L1-隔离 · 写路径）5 态+阻塞切换显示 | 临时实例 8799 + 临时 DB | 建临时任务 → 抽屉切「阻塞」→ 保存 → 断言 | 卡片徽章显示「阻塞」红色样式；阻塞列出现 1 卡；统计「阻塞」+1 | **PASS**：阻塞态显示正确 + 泳道/统计同步。<br>**FAIL**：徽章错/不更新 → Engineer |

---

## 三、回归项（汇总红线）

| 项 | 手段 | 期望 | 判定 |
|---|---|---|---|
| 后端零改动（K5） | `git diff --exit-code shared_board/server.py` + mtime | 净 | PASS=净；FAIL=被改 → 整体退回 |
| 详情按钮不冒泡（K1） | L0 grep + L1 点详情前后展开状态 | stopPropagation 在 + 展开状态不变 | PASS；FAIL → Engineer |
| 统计口径（K2） | L0 grep + L1 三向核对 | 各计各态 + 总计=任务数 | PASS；FAIL → Engineer |
| 暗色持久化（K3） | L1 切暗色 → reload | 刷新后仍暗 | PASS；FAIL → Engineer |
| 删除 confirm（K4） | L0 grep + L1 弹窗出现→取消 | confirm 保留 + 取消零删 | PASS；FAIL → Engineer |
| 抽屉编辑/保存 | L1-隔离 保存改 title/status/priority | 保存回显 + 统计同步 | PASS；FAIL → Engineer |
| 子任务 | L1-隔离 建父子任务 | 计数 + 展开 + 新增 | PASS；FAIL → Engineer |
| 写锁 403 | L1-隔离 非 owner 写 | 403 + 前端错误面 | PASS；FAIL → Engineer |
| 审计/复制派单/多项目 | L1 日志非空 / 复制反馈 / 项目切换 | 正常 | PASS；FAIL → Engineer |
| 接口/页面 | /ext 6×200 + /studio /board /根 4×200 | 全 200 | PASS=全 200；FAIL=任一非 200 |
| 线上 HTML 生效 | curl 8787/board 含新标记 | 新标记在 | PASS=在；FAIL=不在（先清缓存再判，非重启） |

> **回归结论红线**：K5 后端被改 或 详情按钮冒泡/统计口径/暗色持久化/删除 confirm/抽屉编辑/子任务/写锁 403/审计/复制派单 任一回归 → **整体 FAIL（退回 Engineer）**，即使 AC-1.1/1.2/1.3/1.8 全过。

---

## 四、判定矩阵

| 等级 | 定义 | 处置 |
|---|---|---|
| **PASS** | 该 AC 全部必过断言满足，无 FAIL 项 | 勾选 AC；进入下一 AC |
| **FAIL** | 任一必过断言不满足（期望按 PRD/参考范式/现状基线，非测试自身错误） | 记 `[BUG][S|P]`（复现/期望/实际/环境），**路由→ Engineer（源码 bug）**；修复后进 Round 2 回归 |
| **WARN** | 非阻断观察项：实现选择与契约细节不一致但行为正确；测试副作用；主理人待裁决项（如在线全 offline 时在线样式只做渲染断言） | 记录并报主理人裁决，不阻塞放行 |
| **N/A** | 实现未提供可选能力且契约标注可选/跟进 | 跳过并注明，不计 FAIL |

**缺陷路由规则（QA 职责）**：
- 断言期望正确（对照 PRD/参考范式/基线）但实际输出不符 → **源码 bug → Send to Engineer**。
- 断言本身写错（期望与契约不符）→ **测试 bug → QA 自修**（不派 Engineer）。

**轮次控制（STRICT · 最多 2 轮）**：
- Round 1：写用例→执行→分析。全 PASS → 退出（报主理人）。
- Round 2（Engineer 修复后或 QA 自修后）：回归重跑。全 PASS → 退出；仍有 FAIL → **立即退出，剩余问题记为 Known Issues 交主理人**，不进入 Round 3。

---

## 五、风险与已知边界（预登记 WARN）

1. **WARN-1 实现细节自由度**：泳道/统计条/暗色/toast/头像的 class 名、DOM 结构为 design 自由；L0 断言按**契约语义**（有 6 列分组/有统计口径/有 dark+localStorage/有 toast/有头像 on-off）写，不锁死 class 名；L1 Playwright 选择器执行时按实际 DOM 微调（脚本为参考）。列顺序：5 态须逻辑序 待办→进行中→待验证→已验证→完成；阻塞旁路位置 design 自由。
2. **WARN-2 统计条「其余态」归属**：PRD 统计格式 `总计 · 进行中 · 待验证 · 阻塞 · 完成` 不含 待办/已验证 主项；待办/已验证 只入总计属合规——QA 断言以「X/Y/Z/W/V 各自只计对应状态 + 总计=任务数组 length」为准；是否显示待办/已验证补充项（如旧 `renderProg` 的灰字括注）为 design 自由。
3. **WARN-3 浏览器缓存**：验证「线上已生效」以 **curl 抓 8787/board HTML** 为准（服务端直读磁盘）；浏览器侧需强制刷新（Ctrl+F5/清缓存）。若浏览器显示旧版而 curl 已含新标记 → 缓存问题非源码问题。
4. **WARN-4 项目 19 分布为基线非契约**：`12 条 = 完成×10 + 待办×2` 仅当前快照；执行时以 `/api/tasks?project_id=19` 实时返回为准（用例已写「逐条一致」，不锁死具体数字）。
5. **WARN-5 在线状态依赖 last_seen 时效**：线上 presence 三位 agent 均超 5min（§〇）→ 线上断言只保证「渲染不报错 + offline 样式正确」；**在线样式实测定性在 8799 造在线 agent**（§1.3 X-Agent touch）。若执行时恰好有 agent 在线，则以实际为准增强断言。
6. **WARN-6 子任务在泳道内的呈现形态**：PRD 允许「泳道内嵌展开」或「drawer 内」两种；断言以「子任务计数徽章正确 + 子任务可展开可见 + 新增子任务可用」为契约，不锁死形态；K1 详情按钮不冒泡的「展开状态」按实际形态取对应选择器。
7. **WARN-7 写路径测试副作用**：T-1.1-L1-写-1 / T-1.8-L1-写-1 / T-online-L1-写-1 / T-reg-L1-写-* 的临时任务/项目/agent 仅在 8799 临时 DB 副本执行（§1.3 清理）；线上零写路径，若执行中断导致临时实例残留，QA 负责清理后再判。
8. **WARN-8 复制派单 clipboard 权限**：headless 浏览器 clipboard 写权限可能受限；走 `fallbackCopy`（execCommand）或读取反馈文案断言，不锁死 clipboard API 路径。
9. **WARN-9 泳道卡数断言的口径**：若实现把子任务渲染为嵌套卡（泳道内嵌展开），「列卡数」以**列头计数徽章**为准（=该状态任务数，含子任务），顶层卡元素数为辅助；两口径不一致时以徽章 + API 交叉核对为准，记 WARN 报主理人。

---

## 六、执行产物（测试执行阶段产出，本阶段不产出）

- 本文件勾选版（逐 AC 标 PASS/FAIL/WARN/N/A）
- L0 grep 断言输出存档（泳道分组/统计口径/暗色/toast/新态配色/在线头像/详情 stopPropagation/drawer 结构/confirm/K5 git 净）
- L1 Playwright 运行输出（泳道卡数 vs 统计条 vs API、暗色持久化、详情开抽屉不冒泡、toast、在线头像、复制派单、删除弹窗取消）或人工点击路径记录
- 临时实例起停记录（8799 PID、临时 DB 路径、presence 造数 agent、清理确认）
- 缺陷清单（`[BUG][S|P]` 格式，如有）
- K1~K5 专项结论（K1 详情按钮不冒泡、K2 统计口径、K3 暗色持久化、K4 confirm 保留、K5 后端零改动）
- 汇总判定 → 经 SendMessage 回传主理人
