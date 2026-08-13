# T-20260813-08 开发设计 · 看板 UI 视图重做（T-08a：泳道视图 + 统计条 + 暗色 + toast + K1 迁移）

- **版本**：v2（T-08a 视图重做）｜ 2026-08-13 ｜ 开发（frontend-dev）出稿，待主理人双审
- **依据**：`PRD.md`（老板 22:26 拍板 K1/K2/K3/K4/K5）+ 老板 22:26 补充「在线状态 👤 样式化」
- **性质**：**设计稿，只读调研结论 + 改动设计，不含业务代码实现**；实现阶段由开发按本设计落地
- **历史**：v1（P0×3：详情按钮/进度概览/删除弱化）已实现并验收（commit `2055453`，AC-1.4/1.5/1.6 相关通过）——本版保留其结论，不推翻；本版覆盖 **T-08a 剩余主菜**
- **范围**：只动 `shared_board/index.html`（含内嵌 CSS/JS）；不碰 server.py / 后端 API / board.db / 8787 网关 / 其他页面；不引入新依赖；不重启服务
- **参考源**：`dev-work/reference_kanban.html`（326 行，样式底稿，已复制进项目）；现状 `shared_board/index.html`（272 行，T-07 5 态中文 + T-08 P0×3）

---

## 0. 设计结论一句话

**直接改造 `shared_board/index.html`（不新建文件）：把 reference_kanban.html 的样式层（CSS 变量亮/暗双主题、泳道布局、toast、flash、暗色 localStorage 机制）整体移植进现有文件，数据/交互层替换为我们的 API 与已验收能力；新增 6 列中文泳道（5 态 + 阻塞横向滚动）、统计条（吸收 K1 的 `renderProg` 逻辑）、🌙 暗色切换、toast 反馈、在线 👤 头像条；子任务采用「全量平铺入列 + 父引用 chip + 子任务计数徽章」方案（不做卡片内嵌递归展开），并保留「泳道 ⇄ 树」视图切换兜底层级全览。**

---

## 1. 改造策略（K2 核心）

### 1.1 文件组织结论：直接改 `shared_board/index.html`（不新建、不合并成新模板文件）

**结论：直接改造现有 index.html，参考模板只作"样式底稿"整体抄入。**

理由（可验证）：
1. **后端零改动铁律**：`server.py` L150-160 只托管 `index.html`（`GET /` 与 `/index.html` 同一文件），且 L153-157 含 `window.__BOARD_TOKEN__` 令牌注入逻辑。若新建 `kanban.html` 之类文件名，必须改 server.py 增加路由 → 违反 K4「后端零改动」。直接改 index.html 则零后端改动、刷新即生效（server.py L159 `Cache-Control: no-store`，L151 每次请求重读磁盘）。
2. **能力保留最小回归**：现有 index.html 已承载全部已验收能力（token/api 封装 L106-111、抽屉编辑 L171-192、树视图 build L194-225、renderProg L226-233、presence L243-260、audit L246-248、复制派单 L144-158、写锁走 api() 头）。同文件改造 = 这些函数原位保留，回归面最小。
3. **PRD 产出路径明确**（PRD「产出路径」）：`shared_board/index.html`（改造，原生 JS 零依赖）。

### 1.2 保留 / 替换 / 新增 三层清单（K2 落点）

| 层 | 参考 kanban.html 的什么 | 处置 |
|---|---|---|
| **保留（照抄）** | L9-18 `:root` 设计令牌（亮） | ✅ 整体移植进 index.html `<style>` |
| | L19-28 `.dark` 块（暗） | ✅ 整体移植（照 PRD 6.1 完整抄） |
| | L29-30 body/.app、L32-40 .header/.btn/.btn.active/.btn-refresh | ✅ 移植 |
| | L44-45 .stats/.stat b、L47-51 .board/.col/.col-header/.count/.col-body | ✅ 移植（board 改 6 列横向滚动，见 §3.1） |
| | L53-61 卡片组件（.card/.card-header/.card-id/.card-title/.card-meta/.priority-badge/.p-*） | ✅ 移植 |
| | L68-70 .card.blocked/block-pulse/.block-reason | ✅ 移植（阻塞旁路列内用） |
| | L85-87 .assignee/.avatar/av-* 角色色 | ✅ 移植（在线 👤 与作者头像复用） |
| | L103 .empty、L108 .toast、L110-111 .flash | ✅ 移植（flash 样式先落位，T-08b 启用） |
| | L105-106 响应式 | ⚠️ 改为横向滚动优先（见 §4.2） |
| | L313-319 暗色机制（.dark + localStorage('kanban-dark') + 🌙/☀️ 按钮） | ✅ 照抄逻辑（~7 行） |
| | L293-297 showToast | ✅ 照抄逻辑 |
| **替换（不照抄）** | L157 `DATA_URL='TASKS.json'` | ❌ 换为现有 `api("/api/tasks?project_id="+cur)`（index.html L120） |
| | L158-163 COLUMNS（4 列 backlog/inProgress/blocked/done） | ❌ 换为 6 列中文直映射（见 §2.1） |
| | L175-178 statusColumn（英文 + fallback） | ❌ 换为 6 态中文 1:1 映射，无 fallback |
| | L180 DEMO_DATA、L182-199 loadData | ❌ 换为现有 load()（index.html L114-123），保留参考的"失败提示/空态"文案思路 |
| | L201-246 renderCard（依赖 card.progress/deadline/dependsOn/blockedBy/isHotfix/milestones 等参考字段） | ❌ 换为我们的字段（title/status/priority/author/updated/parent_id/detail/id）；**无 progress/deadline/dependsOn/blockedBy/isHotfix 字段**，相关参考样式（L63-66 进度条、L72-73 hotfix、L75-79 done/overdue、L81-83 dep、L89-101 milestones）**不移植**（B 类 T-09 字段位） |
| | L300-307 filters 按钮组 | ❌ 本卡不做（T-08b K5 筛选），预留位置 |
| **新增（我们的能力融进去）** | — | ✅ 6 态列配色 token（待验证 amber / 已验证 purple）；在线 👤 头像条；K1 详情按钮迁入卡片；K1 统计条（renderProg 逻辑迁移）；视图切换「泳道 ⇄ 树」；toast 接入全部写操作 |

### 1.3 文件结构（改造后 index.html 的骨架）

```
<style>  参考设计令牌(:root/.dark) + 参考组件样式 + 我们的状态色/控件样式 + 暗色适配  </style>
<header>
  <div class="topbar">  现有项目控件：projSel/projName/projOwner/建项目/改归属/复制派单/+主任务（index.html L67-74）  </div>
  <div class="progbar" id="prog">  进度概览统计条（K1 迁移，吸收参考 .stats 形态）  </div>
  <div class="presbar" id="presence">  在线 👤 头像条（样式化）  </div>
</header>
<div class="view-toggle">  泳道 / 树 切换（新增）  </div>
<div class="board" id="board">  泳道容器（6 列横向滚动）  </div>
<div class="wrap" id="treeWrap" hidden>  #tree + #empty + #audit（树视图，保留）  </div>
<div class="mask" id="mask"></div>
<div class="drawer" id="drawer">  抽屉编辑（保留，样式适配暗色）  </div>
<div class="toast" id="toast"></div>
<script>  现有 api/写锁/抽屉/树/renderProg/presence/audit/复制派单 + 新增泳道渲染/暗色/toast/视图切换  </script>
```

---

## 2. 数据接入

### 2.1 status → 泳道列 1:1 映射（T-07 5 态中文 + 阻塞）

`GET /api/tasks?project_id=N`（server.py L180-183）返回全项目任务（**含子任务**，字段 `id,parent_id,title,detail,status,author,updated,priority`）。`STATUS_ENUM`（server.py L12）= {待办, 进行中, 待验证, 已验证, 完成, 阻塞}。

| 列（顺序） | 状态中文 | 列配色 token | 说明 |
|---|---|---|---|
| 1 | 待办 | 灰 `--st-todo` | 默认态 |
| 2 | 进行中 | 蓝 `--st-doing` | |
| 3 | 待验证 | **amber** `--st-verify`（新态） | 亮 `#a16207`/底 `#fef9c3`；暗 `#fbbf24`/底 `rgba(245,158,11,.15)` |
| 4 | 已验证 | **purple** `--st-verified`（新态） | 亮 `#4338ca`/底 `#e0e7ff`；暗 `#a5b4fc`/底 `rgba(99,102,241,.15)` |
| 5 | 完成 | 绿 `--st-done` | 参考 .col-done 降透明度（L75）沿用 |
| 6（旁路） | 阻塞 | 红 `--st-blocked` | 参考 .card.blocked 2px 红边 + pulse（L68-69）沿用 |

- **映射实现**：`status → 列` 为 1:1 直映射，**无 fallback**（参考 L175-178 的 fallback 逻辑丢弃）——6 态枚举即 6 列，`groups[t.status].push(t)`，无需 `statusColumn()` 中转。
- **列头**：状态中文 + 计数徽章（参考 L50 `.col-header .count`）。
- **空列**：`<div class="empty">暂无任务</div>`（参考 L103/L259）。

### 2.2 子任务在泳道的展示（最大设计难点 —— 方案结论）

**结论：方案 A「全量平铺入列」——所有任务（含子任务）按各自 status 归入对应列，子任务卡视觉降级（缩进 + 父引用 chip），父任务卡显示「子任务计数徽章」；不做卡片内嵌递归展开；层级全览由保留的「树视图」兜底。**

| 方案 | 做法 | 优劣 |
|---|---|---|
| **A 全量平铺（选）** | 子任务与根任务一样是独立卡片，按自己状态入列；子任务卡左侧缩进 + 顶部「↳ 父 #id」引用 chip；父卡显示 `N 子任务` 徽章（纯展示） | ✅ 列计数 = 统计条口径天然一致（AC-1.2 直接满足）；跨列子任务不隐藏（子任务状态 ≠ 父任务状态时仍可见）；renderCard 单层渲染、DOM 简单。❌ 层级不如树直观 —— 用父引用 chip + 树视图兜底 |
| B 仅根入列+内嵌展开 | 父卡内嵌子任务列表，点击展开 | ❌ 子任务若与父不同状态会被"锁"在父列，状态被隐藏；列计数口径被迫改为"只数根任务"，与 T-07 验收口径（总数=含子任务）冲突，破坏 K1 renderProg 迁移；DOM 递归复杂度高 |
| C 仅根入列+状态汇总 | 父卡显示子任务状态分布 | ❌ 子任务不可直接操作/查看，能力降级 |

**理由详述**：
- **口径一致性**：现有 renderProg（index.html L226-233）与 T-07 验收口径 = 总数含子任务（`tasks.length`，server.py L183 返回全项目行）。方案 A 下列计数 = 该状态任务数（含子任务），统计条同源，**AC-1.1/1.2 逐列可核对**。
- **不破坏 K1**：K1 要迁移 `renderProg` 逻辑，方案 A 下统计口径不变，迁移零歧义。
- **交互简单**：泳道视图里 单击卡片 = 开抽屉（PRD 二.1），无需展开手势；子任务管理（+ 子任务按钮在抽屉内，index.html L96-97 保留）与层级全览（树视图）互补。

**子任务卡渲染细节**（T-08a 实现要点）：
- `parent_id != null` 的任务 → 卡 class 加 `child-card`（左侧 2px 竖线 + `padding-left` 缩进，沿用现有树视图 `.children` L38 的竖线视觉），卡片头部加 chip `↳ #父id`（点击可后续 T-08b 做 flash 定位，本卡纯展示）。
- `parent_id == null` 且有子任务的任务 → 卡 meta 区加 `<span class="subcount">👥 N 子任务</span>` 计数徽章（纯展示，本卡不做点击行为；T-08b flash 定位时再挂 `scrollToCard`）。
- 计数计算：`tasks.filter(t=>t.parent_id==id).length`（复用 build() L195 的 hasKids 思路）。

### 2.3 统计条口径（与 T-07 / renderProg 一致）

- **总数 = 当前项目全部任务（含子任务）** = `tasks.length` = `GET /api/tasks?project_id=N` 全部行数（与现有 renderProg L229-230 一致）。
- **主行 5 项**（PRD 一.2 参考形态）：`总计 X · 进行中 Y · 待验证 Z · 阻塞 W · 完成 V`（其中 进行中/待验证/阻塞/完成 用状态色数字）。
- **muted 后缀 2 项**：`（待办 A · 已验证 B）`——沿用现有 renderProg L232 的"主行 + muted 后缀"模式，保证 6 态全部逐条可见、QA 可逐状态核对。
- **更新时机**：`render()` 入口统一调用（现有 L235 `renderProg()` 位置保留），覆盖全部改状态路径（saveDrawer→load→render、addRoot/addChild/delTask/changeOwner/切项目/5s 定时刷新）。未选项目 `!cur` → 清空。
- **K1 迁移**：统计条 = 参考 `.stats` 形态（L44-45 + L139-145 结构）承载 **renderProg 逻辑**；参考模板的 `.progress-bar`（L63-66 卡片内进度条）**不显示**——我们无 `progress` 字段（B 类 T-09 才加，PRD 一.6④），仅保留样式字段位。

### 2.4 数据流（复用现有，零后端改动）

```
现有 api()（index.html L111，带 X-Board-Token / 写锁）→ load()（L114-123）→ tasks 数组
→ render()（泳道分支 renderBoard / 树分支 build）→ renderProg()（统计条）
5s setInterval（L267）→ load + loadPresence + loadAudit（保持现有节奏，T-08a 不加开关，T-08b 13 才加）
```

---

## 3. 改动点清单（精确到行段）

> 行号均为现状（reference_kanban.html 326 行 / index.html 272 行）实测；「参考」= 从参考模板移植，「保留」= 现有 index.html 原位保留/适配。

### 3.1 CSS 层（index.html L7-63 的 `<style>` 重写）

| # | 内容 | 来源 / 落点 |
|---|---|---|
| C1 | `:root` 设计令牌（亮） | 参考 L9-18 整体移植；**新增 6 态列配色 token**：`--st-todo/--st-doing/--st-verify/--st-verified/--st-done/--st-blocked`（含色字 + 浅底 + 暗色底），对照 PRD 6.1/6.3 |
| C2 | `.dark` 块 | 参考 L19-28 整体移植；**每个状态补暗色 token**（见 §2.1 表）；drawer/presence/audit 等现有组件背景改 `var(--card-bg)` 系（当前写死 #fff/#eef2ff 在暗色下刺眼） |
| C3 | body/.app/.header/.btn 家族 | 参考 L29-40 移植；现有 `button` 基类（index.html L12-13）改接入参考 `.btn` 风格，保证 🌙/刷新/视图切换按钮视觉统一 |
| C4 | `.stats`/`.board`/`.col` | 参考 L44-51 移植；**board 改 6 列横向滚动**：`display:flex;overflow-x:auto`，`.col` `flex:0 0 260px`（替代参考 grid 4 列 L47；见 §4.2） |
| C5 | `.col-header .count` | 参考 L50 移植（列计数徽章） |
| C6 | 卡片组件 | 参考 L53-61 移植（.card/.card-header/.card-id/.card-title/.card-meta/.priority-badge/.p-*）；卡片内**新增 `.dbtn` 详情按钮样式**（现有 index.html L40 已有点状样式，适配卡片布局） |
| C7 | `.card.blocked` + `.block-reason` | 参考 L68-70 移植（阻塞列内卡片红边 + pulse） |
| C8 | `.assignee .avatar`/av-* | 参考 L85-87 移植（作者头像 + 在线头像复用）；**新增在线头像态**：`.avatar.on` 绿点 + 实色 / `.avatar.off` 灰点 + 半透明 |
| C9 | `.empty` / `.toast` / `.flash` | 参考 L103/L108/L110-111 移植（toast 用参考形态，flash 样式先落位 T-08b 启用） |
| C10 | 子任务卡样式 | 新增 `.child-card`（缩进 + 左侧竖线，参照 index.html L38 `.children` 竖线）+ `.parent-ref` chip + `.subcount` 徽章 |
| C11 | 现有组件暗色适配 | `.presbar`（L52-54）、`.progbar`（L55-56）、`.drawer`（L44）、`.auditbox`（L57）、badge 5 态（L24-29）背景色全部改 CSS 变量 + `.dark` 覆盖，保证暗色下可读（见 §4.3） |
| C12 | 视图切换 | 新增 `.view-toggle` 按钮组（复用参考 `.btn.active` L39 高亮形态） |
| C13 | 响应式 | 参考 L105-106 的 grid 降列**不采用**；改 `<600px` 时列宽 `flex:0 0 80vw`、统计条换行（见 §4.2） |

### 3.2 HTML 层（index.html L66-102）

| # | 内容 | 说明 |
|---|---|---|
| H1 | header 内保留现有 topbar（L67-74：projSel/projName/projOwner/建项目/改归属/复制派单/+主任务） | 原位保留，样式由 C3 统一 |
| H2 | header 内保留 `#prog`（L76，`.progbar`） | **K1 迁移**：形态升级为参考 `.stats` 风格（主行 5 项 + muted 后缀），仍随 header sticky |
| H3 | header 右侧新增：🌙 按钮（`#btnDark`）+ 手动刷新按钮（`#btnRefresh`）+ 视图切换（`#viewToggle`） | 参考 L123-124 的 btnRefresh/btnDark 形态；视图切换是新增能力（见 §4.4） |
| H4 | 保留 `#presence`（L78） | 内容改为 👤 头像条（见 J7） |
| H5 | 新增 `<div class="board" id="board"></div>` 泳道容器（在 header 后、treeWrap 前） | 泳道主视图 |
| H6 | 保留 `.wrap > #tree + #empty + #audit`（L79），包一层 `#treeWrap`（默认 `hidden`） | 树视图 + 审计流保留 |
| H7 | 保留 mask + drawer（L81-102） | 编辑能力原位保留；L85 详情 label 已是「详情」（v1 已去"长按"引导）；`#d_status` 6 项中文（L87-89）保留 |
| H8 | 新增 `<div class="toast" id="toast"></div>`（参考 L154） | toast 容器 |
| H9 | `<script>window.__BOARD_TOKEN__` 注入位 | 不动（server.py L153-157 注入逻辑依赖 `</head>`，保持） |

### 3.3 JS 层（index.html L105-268 + 参考脚本）

| # | 函数/逻辑 | 处置 |
|---|---|---|
| J1 | 现有 `api()`（L111）+ `ERR()`（L110） | 保留签名；**`ERR()` 内部 alert → showToast**（T-08a toast 替代 alert；网络/HTTP 错误也走 toast） |
| J2 | 现有 `load()`/`setProj()`（L114-125） | 保留；`load()` 内加 toast（加载失败时） |
| J3 | 新增 `renderBoard()` | **泳道渲染主函数**：按 §2.1 6 列分组 → `board.innerHTML`（参考 L248-286 结构，列/计数/统计条/空态）；卡片生成函数 `renderCard(t)` 用我们的字段 + 父引用 chip + 子任务计数徽章 + `.dbtn` 详情按钮（K1） |
| J4 | 现有 `build()`（L194-225） | **保留为树视图渲染**（含 单击展开/双击/长按/dbtn/addbtn，v1 已加 dbtn）；视图切换时复用，零改动 |
| J5 | 现有 `renderProg()`（L226-233）+ `render()`（L234-242） | **K1 迁移**：renderProg 逻辑并入统计条渲染（§2.3 口径不变）；render() 改为按 `viewMode` 分支：泳道 → renderBoard + 统计条；树 → build + 统计条 |
| J6 | 现有 `saveDrawer`（L175-182）/`openDrawer`/`closeDrawer`（L183-192） | 保留；saveDrawer 成功 → toast「已保存 #id」；失败 → toast 错误（原 `.catch(()=>{})` L181 补 toast）；**异步回显（保存不关抽屉不重置）归 T-08b 13**，本卡保持 关抽屉→load 现状 + toast |
| J7 | 现有 `loadPresence`/`renderPresence`（L243-245/L249-260） | **在线 👤 样式化（老板补充）**：从「圆点 + agent · ago」改为「头像（agent 首字，角色色映射）+ 名字 + 在线点 + ago」；在线判定（diff≤5 分钟，L256）保留；在线者实色 + 绿点，离线者灰点 + 半透明；复用参考 av-* 角色色（L87） |
| J8 | 现有 `loadAudit`/`renderAudit`（L246-248/L261-266） | 保留（审计流零改动） |
| J9 | 现有 `addRoot`/`addChild`/`delTask`（L159-174）/`addProject`/`changeOwner`/`copyDispatch`/`fallbackCopy`（L127-158） | 保留；alert 全部换 toast（成功/失败），delTask 的 `confirm`（L172）**保留原生**（PRD 未要求改）；delTask 删除后 toast |
| J10 | 现有 5s setInterval + init（L267-268） | 保留（T-08a 不加开关；T-08b 13 加自动刷新开关） |
| J11 | 新增暗色逻辑 | 参考 L313-319 照抄：`localStorage('kanban-dark')==='1'` → body.dark；🌙/☀️ 切换 |
| J12 | 新增 `showToast()` | 参考 L293-297 照抄（2s 淡入淡出） |
| J13 | 新增视图切换 | `viewMode` 变量（'kanban'|'tree'，默认 'kanban'）；`#viewToggle` 按钮组切换 + `localStorage` 记忆可选；切换后 render() |
| J14 | 新增 `statusToColumn` | 6 态中文 1:1 映射（§2.1），替代参考 L175-178 fallback 逻辑 |
| J15 | 不移植 | 参考 filters（L129-136/L300-307）→ T-08b；参考 scrollToCard/flash 定位（L288-291）→ T-08b 启用（样式已落位 C9）；参考 milestones/dep/hotfix/overdue/进度条 → B 类 T-09 字段位 |

### 3.4 diff 估算

| 块 | 行数（约） |
|---|---|
| CSS：令牌 + 6 态色 + 组件 + 暗色适配 + 子任务样式（C1-C13） | ≈ 200 |
| HTML：header 右侧按钮 + board 容器 + treeWrap + toast（H1-H8） | ≈ 30 |
| JS：renderBoard/renderCard/statusToColumn + 暗色 + toast + 视图切换 + 各写操作接 toast（J3/J5/J7/J11-J14/J1/J6/J9） | ≈ 180 |
| 保留现有（api/写锁/抽屉/树/审计/在线/presence/复制派单/init） | ≈ 250 |
| **改造后 index.html 总量** | **≈ 560-620 行**（现 272 行） |

> 说明：这是视图级重做（参考样式整体移植 + 泳道渲染新增），**不是** v1 那种 37 行小 diff；但**新增逻辑集中在渲染层**，写锁/抽屉/审计/复制派单等能力函数原位不动。

---

## 4. 风险点

### 4.1 子任务层级展示（最大设计难点）→ 已定方案 A
- 见 §2.2 结论与对比。残余风险：泳道视图下父子关系不如树直观。缓解：① 子任务卡缩进 + `↳ 父 #id` chip 显式标注；② 父卡 `N 子任务` 计数徽章；③ **保留「泳道 ⇄ 树」切换**，树视图提供完整层级全览 + 展开动画（现有 L194-225 零改动）；④ drawer 内「+ 子任务」（L96-97）保留，可随时给任意任务加子任务。
- 注意：**列计数含子任务**（全量平铺），QA 核对用 `SELECT status,COUNT(*) FROM tasks WHERE project_id=N GROUP BY status`（与前端 tasks 同源），勿只数根任务。

### 4.2 6 列横向滚动 vs 响应式
- 参考模板是 4 列 grid + 2 档降列（L105-106）；我们 6 列（5 态 + 阻塞）在 ≤1560px 宽屏下 grid 单屏放不下，**采用横向滚动优先**（`.board{display:flex;overflow-x:auto;padding-bottom:8px}`，`.col{flex:0 0 260px}`），保证 6 列同时可达、不破坏泳道语义。
- `<600px` 移动端：列宽 `flex:0 0 80vw`，仍横向滑动（泳道交互移动端友好）；统计条与 topbar 自然换行（参考 L32-34 的 flex-wrap 思路）。
- 风险点：横向滚动在桌面端需要滚动条可见性（加 `scrollbar-width:thin` 或轻量滚动条样式），避免"以为只有 5 列"。

### 4.3 暗色下 6 态配色对比度
- 参考 .dark 只覆盖 4 色优先级（L23-26），**无状态色 token**；我们 6 态在暗色下若沿用亮色浅底会刺眼。方案：每个状态定义亮/暗两套 token（§2.1 表），暗色底全部用 `rgba(色,0.1-0.15)` + 亮色字（对照参考 L23-26 手法）。
- 对比度检查项（QA）：待验证 amber（暗 `#fbbf24` on `rgba(245,158,11,.15)`）、已验证 purple（暗 `#a5b4fc` on `rgba(99,102,241,.15)`）文字在 `--card-bg:#1e293b` 上可读；toast 在暗色下仍是深底白字（参考 L108 深底，暗色下加 `box-shadow` 区分）。
- 现有组件硬编码色（drawer #fff、presbar #eef2ff、progbar #eef2ff、badge L24-29）必须全部改变量，否则暗色下白块突兀——这是实现时最易漏的点，QA 需逐组件扫暗色。

### 4.4 K1 迁移与树视图切换的取舍（结论：保留切换，默认泳道）
- **结论**：T-08a **保留「泳道 ⇄ 树」视图切换**，默认进泳道。
- 理由：① 树视图是 T-07 已验收交互，**直接删除违反零回归**（AC-1.5 子任务/层级管理不破）；② 泳道平铺方案（A）牺牲了层级全览，树视图是天然兜底（成本≈0，build() 原位保留）；③ 实现成本低：viewMode 分支 + 一个按钮组。
- 取舍：两个视图点击语义不同（泳道：单击卡片=开抽屉；树：单击=展开子任务）——属**预期差异**，在视图切换按钮旁加 title 提示即可，不视为缺陷；QA 按视图分别验收。
- 不做的选项：T-08a 移除树视图（破坏已验收能力）、泳道内做复杂嵌套（§4.1 已否）。

### 4.5 其他
- **token/写锁**：`api()`（L111）头注入逻辑保留，`window.__BOARD_TOKEN__` 注入位（H9）不动；避免重写 api() 导致写锁/403 回归。
- **toast 替代 alert 的边界**：`confirm`（删除二次确认 L172、建项目输入校验 L128/131 等）仍用原生；仅"操作结果/错误"反馈走 toast。
- **生效方式**：server.py L151/L159 每次重读 + no-store → 改文件刷新即生效，不重启服务；浏览器侧建议强刷（Ctrl+F5）。

---

## 5. AC 映射（T-08a）

| AC | 验收点 | 本设计如何满足 |
|---|---|---|
| AC-1.1 | 泳道按 5 态正确分组（+阻塞列），每列计数对 | §2.1 6 列直映射（status→列 1:1，无 fallback）；§3.3 J3 renderBoard 按 6 态分组 + 列头计数徽章（参考 L50/L261）；全量平铺（含子任务）使计数与数据同源 |
| AC-1.2 | 统计条数字与泳道各列一致 | §2.3 统计条与列计数同源于 `tasks` 数组；renderProg 口径（含子任务）不变（K1 迁移）；主行 5 项 + muted 后缀 2 项，6 态逐条可核对 |
| AC-1.3 | 暗色切换生效且 localStorage 持久化（刷新后保持） | §3.3 J11 照抄参考 L313-319（`.dark` + `localStorage('kanban-dark')` + 🌙/☀️ 按钮）；§3.1 C2 全部组件/状态色暗色 token 化 |
| AC-1.8 | 新态配色可见：待验证=amber、已验证=purple | §2.1 新态 token（亮/暗两套）；C1/C2 落 CSS；列头、卡片徽章、统计条同色系 |
| 在线样式（老板 22:26 补充） | 现有 /api/presence 数据改成人头+名字，谁在线一眼可见 | §3.3 J7 renderPresence 改造：头像（agent 首字 + 角色色）+ 名字 + 在线点 + ago；在线（diff≤5min）实色绿点，离线灰点半透明；复用参考 av-*（L87） |
| K1 迁移 | 详情按钮（点击开抽屉）/ 进度概览（renderProg）迁入新 UI | 详情按钮：renderCard 卡片内 `.dbtn`（§3.3 J3，复用现有 `openDrawer` L183-192 + `stopPropagation`，参考 v1 §2.1 手法）；进度概览：renderProg 逻辑迁入统计条（§2.3/J5），口径与 T-07 验收一致不丢 |
| （零回归侧写）AC-1.4/1.5/1.6 相关 | 单击开详情；增删改/子任务/写锁/审计/复制派单不破；toast 出现 | 抽屉编辑/写锁/审计/复制派单函数原位保留（§6）；toast 接入保存成功/失败/手动刷新（J1/J6/J9） |

---

## 6. 零回归清单（T-08a 交付核验）

**后端零改动**：
- `server.py` / `board.db` / 8787 网关 / docs.html / migrate 脚本：全部不碰。
- `GET /api/tasks /api/projects /api/presence /api/audit` 消费方式不变（仍是现有 api()/load()）。

**能力保留清单（实现时逐项核验）**：

```
1. 抽屉编辑：openDrawer/closeDrawer/saveDrawer（L175-192）保留；5 态下拉 + 阻塞 6 项中文（L87-89）；保存 → toast + 刷新
2. 子任务：addChild（L165-170）保留（抽屉内 + 子任务按钮）；delTask（L171-174）保留（confirm 二次确认 L172）
3. 删除弱化：delbtn（L99/L61-62）保留（v1 已验收，不退化）
4. owner 写锁：api() 带 X-Board-Token（L111）+ 服务端 403 逻辑不动；ERR 仅由 alert→toast
5. 审计流：loadAudit/renderAudit（L246-248/L261-266）保留，随 header/页脚展示
6. 复制派单：copyDispatch/fallbackCopy（L144-158）保留，alert 换 toast
7. 多项目：projSel 切换 + addProject/changeOwner（L127-143）保留
8. 在线条：loadPresence 保留（仅 renderPresence 样式化，判定逻辑 L256 不动）
9. 树视图：build()/render() 树分支（L194-242）保留（视图切换兜底）
10. 自动刷新：5s 轮询（L267）保留（开关 T-08b 13 再加）
11. 令牌注入：window.__BOARD_TOKEN__（server.py L153-157 + index.html L108）不动
12. 空态/未选项目：!cur / 无 root 提示保留
```

---

## 7. 边界 / 明确不做（T-08a）

- **归 T-08b（本卡不做，但预留）**：筛选按钮组（K5）、卡片状态快捷切换（K5）、指导留言栏 /ext/notes、完成时间戳、flash 定位、进度字段位启用、自动刷新开关、保存异步回显。
- **归 T-09（B 类数据层扩展）**：deadline/逾期、progress%、blockedBy、dependsOn、里程碑——参考模板相关样式（L63-66/L72-79/L81-83/L89-101）不移植。
- **不引入框架/依赖**；**不删已验收能力**；**不改后端**；**不重启服务**。
- **自决记录**：① 子任务展示选方案 A（全量平铺 + 父引用 chip + 计数徽章，§2.2）；② 保留泳道 ⇄ 树视图切换（§4.4）；③ 统计条主行 5 项 + muted 后缀 2 项（§2.3，延续 renderProg 口径）；④ 列计数与统计条均含子任务（与 T-07 验收一致）；⑤ 删除确认仍用原生 confirm，仅结果/错误反馈走 toast。
