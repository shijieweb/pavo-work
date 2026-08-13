# T-20260813-08b 功能融合 · 实现方案（design.md）

- **目标文件**：`shared_board/index.html`（原生 JS 零依赖，仅增量修改，后端 `server.py` 零改动）
- **基线**：在已验收的 T-08a（泳道 6 列 / 统计条 / 暗色 / toast / 新态配色 / 👤 在线 / 编辑抽屉迁移）之上融合功能。
- **改动规模**：新增约 130 行 JS + 约 30 行 CSS + 少量 HTML 结构；既有函数仅小幅增量修改，无删除。

---

## 1. 整体结构（复用 T-08a 既有能力）

| 模块 | 既有 | 本次增量 |
|---|---|---|
| 顶部栏 | 项目切换/建项目/改归属/复制派单/+主任务/视图切换/刷新/暗色 | 新增「🔄 自动」开关按钮 |
| 统计条 `#prog` | `renderProg()` | 统计口径改为「跟随当前筛选」一致 |
| 在线条 `#presence` | `loadPresence()` | 不变（tick 仍刷新） |
| 泳道 `#board` | `renderBoard()`/`renderCard()` | 卡片加状态徽章(可点)、完成时间戳、进度字段位、父任务可点定位 |
| 树视图 `#tree` | `build()` | 节点过滤接入 `matchFilter` |
| 操作日志 `#audit` | `renderAudit()` | 不变 |
| 抽屉 `#drawer` | `openDrawer`/`saveDrawer` | 不变（保存异步回显由 tick 保证不打断） |

---

## 2. 九项功能实现要点

### 9. 筛选按钮组（状态/优先级/作者，纯按钮组，无关键词搜索）
- HTML：顶部新增 `.filterbar`（三个 `.fgroup`：状态/优先级/作者 + 「✕ 清除筛选」）。
- 状态维度固定 6 值 `FILTER_STATUSES=['待办','进行中','待验证','已验证','完成','阻塞']`；优先级固定 4 值；**作者**由当前 `tasks` 的 `author` 去重动态生成。
- 状态：`filterStatus/filterPriority/filterAuthor` 三个全局状态；点击按钮 toggle 选中（再点取消），active 高亮（`.fbtn.active`）。
- 事件委托：`#filterbar` 上 `click` → 读 `data-dim/data-val` → 更新状态 → `renderFilterButtons()+render()`。
- **与泳道协同**：`renderBoard()` 中若 `filterStatus` 命中，则只渲染该状态对应的那一列（聚焦），其余列隐藏；优先级/作者维度作为卡片级谓词 `matchFilter()` 隐藏不匹配卡片。统计条 `renderProg()` 同样用 `matchFilter()`，保证「统计数字与泳道一致」（AC-1.2）。

### 10. 卡片状态快捷切换（点徽章，不开 drawer）
- `renderCard()` 卡片头部新增状态徽章 `<span class="badge" data-status onclick="openStatusMenu(id,event)">`，`stopPropagation` 不触发抽屉。
- `openStatusMenu()`：在点击处弹出 `#statusMenu`（fixed 浮层，6 个状态按钮，带色点）。点选项 → `quickSetStatus(id,st)` → `PUT /api/tasks/{id}`（仅传 `{status}`）→ `load()` 异步回显 + toast。
- 文档级 `click` 监听关闭浮层；徽章点击 `stopPropagation` 防止立即被关闭。
- **设计决策**：快捷菜单包含「阻塞」共 6 态（PRD 文字列举 5 态，但为保留「切换为阻塞」能力、与抽屉 6 态一致，做超集，已在汇报中说明）。

### 11. 指导留言栏（消费 `/api/ext/notes`）
- HTML：操作日志下方新增「📌 指导留言」面板，复用 `.auditbox/.ahead/.arow` 样式，标题可点击 `toggleNotes()` 折叠。
- `loadNotes()`：`GET /api/ext/notes?project_id=cur`，最新置顶（服务端已 `ORDER BY id DESC`）。空数组显示「暂无指导留言」空态；未选项目显示「选择项目后查看指导留言」。
- 渲染 `renderNotes()`：每行 `[ts] agent：text`。错误时保留上一次缓存，不打断看板。
- **后端零改动**：直接消费既有 GET 端点（server.py 第 240 行附近），写接口由外部网关带 token 调用，前端不写。

### 12. 功能融合 A 类
- ① **完成时间戳**：`renderCard()` 中 `status==='完成'||'done'` 时显示 `.done-stamp`（✅ + `updated`，因无 `completedAt` 字段，用 `updated` 近似，符合 PRD）。
- ② **flash 高亮定位**：实现 `scrollToCard(id)`（参考 reference_kanban.html），`el.scrollIntoView({smooth,center})` + 加 `.flash` 类 2s。卡片内父任务引用 `↳ 父 #N` 改为可点击 `onclick="scrollToCard(parent_id)"`（stopPropagation）。（当前无 `dependsOn` 数据，父任务引用即「关联标签」载体，T-09 接入依赖后同结构可复用。）
- ③ **进度字段位**：`renderCard()` 中 `typeof t.progress==='number'` 才渲染进度条；当前任务无该字段 → 不显示，结构已留好（T-09 启用）。

### 13. 自动刷新开关 + 保存异步回显
- 默认开：顶部「🔄 自动」按钮（`.active`）。点击 toggle `autoOn` + `startAuto()/stopAuto()`。
- `tick()`（每 5s）：`if(cur)` 异步拉 `tasks` 并 `render()`，再 `loadPresence/loadAudit/loadNotes`。**只刷新数据，不触碰抽屉 DOM**（抽屉输入框独立），故编辑态不重置（满足 AC-1.4 / AC-1.7）。
- 关闭 → `clearInterval` 停轮询。
- **保存异步回显**：`saveDrawer()` 不变（PUT→closeDrawer→load）。auto-refresh 的 `tick()` 持续异步回显看板，无需额外处理。

---

## 3. 关键代码位置（行号随编辑后浮动，以函数名为准）
- `matchFilter()` / `renderFilterButtons()` / `#filterbar` 事件 —— T-08b 筛选
- `openStatusMenu()` / `quickSetStatus()` / `#statusMenu` —— 状态快切
- `loadNotes()` / `renderNotes()` / `toggleNotes()` —— 留言栏
- `scrollToCard()` / 卡片 `parent-ref` onclick —— flash 定位
- `renderCard()` 内 `doneHtml`/`prog`/`stBadge` —— A 类①②③
- `tick()` / `startAuto()` / `stopAuto()` / `#btnAuto` —— 自动刷新开关

## 4. 偏差与决策记录
1. 状态快切菜单含 6 态（含阻塞），超集于 PRD 文字的 5 态，以保留全能力、与抽屉一致。
2. 作者筛选项动态生成（非写死角色），更贴合实际数据。
3. 状态/优先级/作者三种筛选现已**统一**为「保留全部 6 列、由 `matchFilter` 在卡片级隐藏不匹配项」（`renderBoard()` 始终 `const cols = COLUMNS`）。即状态筛选「完成」时 6 列都在，仅完成卡片可见、其余列显示各自非完成卡片——与优先级/作者筛选行为完全一致，符合 PRD 〇.9「隐藏不匹配卡片」（列保留、卡片隐）。（初版曾让状态筛选隐藏其他列，第 2 轮主理人检查指出与 PRD 偏离，已修正统一。）
4. 完成时间戳用 `updated` 近似（PRD 明确允许）。
5. `tick()` 不重拉项目下拉（仅拉 tasks），减少闪烁且不影响抽屉；手动刷新仍全量。

## 5. 自测结论（详见 test.md）
- L0 语法：通过（Node `new Function` + `vm` 实跑脚本）。
- DOM 桩 harness 实跑真实脚本：13 项逻辑断言全 PASS（渲染/筛选/留言/状态菜单）。
- curl：`GET /api/ext/notes?project_id=19` 返回 JSON 数组（前端消费路径 OK）。
- 既有能力（抽屉/删除/顶部栏/在线/多项目/写锁/`/ext` 6 端点）零回归。
