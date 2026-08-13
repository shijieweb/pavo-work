# T-20260813-08 开发设计 · 看板 UI P0×3（详情入口 / 进度概览 / 删除弱化）

- **版本**：v1 ｜ 2026-08-13 ｜ 开发（寇豆码）出稿，待主理人双审
- **依据**：`PRD.md`（AC-1.1~1.4，老板 19:57 拍板只做 P0×3）+ 分析师留言 #5（UI 友好度研究）
- **性质**：**设计稿，只读调研结论 + 改动设计，不含业务代码实现**；实现阶段由开发按本设计落地
- **调研基线**：`shared_board/index.html`（253 行，T-07 后 5 态中文版）；`server.py` 只读（本卡不碰）
- **范围**：只动 `shared_board/index.html`（含内嵌 CSS/JS）；不碰 server.py / 后端 API / board.db / 8787 网关 / 其他页面；不引入新依赖；不重启服务

---

## 0. 设计结论一句话

看板 P0×3 全部收敛在 `index.html` 一处约 **36 行** diff：**卡片加显式「详情」按钮（复用现有 `openDrawer`，保留单击展开/双击/长按）＋ header 内新增实时进度概览条（`renderProg()` 挂到 `render()` 入口，5 态逐条一致）＋ 删除按钮视觉降级为 ghost 小字（`confirm` 二次确认原样保留）**。

**方案 A/B 选择结论：选 A（推荐）。** 加显式「详情」按钮、现有单击展开/双击(桌面)/长按(手机) 行为全部不动。理由：改动收敛在 `build()` 内约 5 行；不触碰 `card.onclick` 展开逻辑（L198）与 `children` 动画容器（L206-208）；手机/桌面统一可用；方案 B（单击=详情、展开改箭头）需重构 L198/L206/L210 多处交互、改变用户肌肉记忆，PRD 亦标注不推荐，风险收益不划算。

---

## 1. 现状调研（只读 · 全部基于真实代码行号）

### 1.1 文件总览

`shared_board/index.html`（253 行，单文件 HTML + 内嵌 CSS + 内嵌 JS）。T-07 后状态已全中文：徽章配色用 `data-status` 属性选择器（L24-29），抽屉下拉 6 项中文 value（L80-83），`build()` 徽章直显中文（L195），无英文映射层。

### 1.2 顶部区域结构（L61-73）

| 行号 | 内容 | 说明 |
|---|---|---|
| L10 | `header{position:sticky;top:0;...;z-index:10}` | header 吸顶 |
| L61-71 | `<header><div class="topbar">…项目选择/新建/改归属/复制派单/+主任务…</div></header>` | L70 `</div>` 收 topbar，L71 `</header>` |
| L72 | `<div id="presence" class="presbar">` | 在线状态条（自身 sticky，z-index:9，L51-53） |
| L73 | `.wrap > #tree + #empty + #audit` | 任务树 / 空提示 / 操作日志容器 |

**结论**：顶部目前只有项目操作行 + 在线状态条，**无任何任务进度/统计元素**——进度概览需要新增 DOM。

### 1.3 任务树渲染函数 `build(id)`（L186-215，递归）

- L187 `const kids=tasks.filter(t=>t.parent_id==id)`：按 parent_id 取子节点，**任务树数据源 = 全局 `tasks` 数组（含全部层级）**。
- L191 卡片 `card`（class="card"，L18 有 `cursor:pointer` + `:active` 高亮）。
- L192-195 组装：三角 `tri`（L192，`expanded.has(t.id)` 控制 `.open` 旋转）、标题 `tt`、优先级 `pr`（L194）、状态徽章 `b`（L195，`b.dataset.status=t.status`）。
- **L196** `card.append(tri,tt,pr,b)`：卡片内容 = 三角 + 标题 + 优先级 + 状态，**无任何"详情"入口元素**。
- L198 `card.onclick=()=>{ if(hasKids){expanded.has(t.id)?expanded.delete(t.id):expanded.add(t.id);render();} }`：**单击=展开/收起子任务**（有子任务时）。
- L199-202 长按看详情（移动端）：`card.ontouchstart` 起 500ms timer → `openDrawer(t.id)`；`card.ontouchend` 清 timer。
- L203 `card.ondblclick=()=>openDrawer(t.id)`：**双击看详情（桌面）**。
- L204-205 元信息 `det`（作者 + 更新时间，class="meta"）。
- L206-208 子任务容器 `ch`（`grid-template-rows:0fr/1fr` 过渡动画，L36-38），`ch.append(inner); inner.append(build(t.id))` 递归。
- L209 `node.append(card,det,ch)`。
- L210-211 有子任务时追加 `+ 子任务` 按钮（class="addbtn"，**append 到 node、在卡片外下方**，非卡片内）。

**结论**：卡片交互三通道——单击展开（L198）、双击详情（L203）、长按详情（L199-202），均无视觉提示（PRD AC-1.1 所指"引导倒置"）。`openDrawer(id)`（L175-183）是唯一详情函数，复用即可。

### 1.4 详情抽屉（L75-94）

- L75-76 mask + drawer（右侧滑出，`.drawer.show` L43-44）。
- L79-83 标题 / 状态下拉（**6 项中文**，T-07 已改）/ 优先级下拉。
- **L87** `<label>详情（长按卡片看这里）</label><textarea id="d_detail">`——文案仍引导"长按"，AC-1.1 落地后应顺带修正（避免引导倒置残留）。
- L88-91 操作行：保存（`saveDrawer()`，蓝色实底 flex:1）+ 子任务（ghost）。
- **L92** `<button class="danger" onclick="delTask()">删除此任务及子任务</button>`：红色实底（`.danger` L15：`#fee2e2` 底 + `#dc2626` 字），紧跟保存行下方，**视觉强度与保存同级甚至更强**（PRD AC-1.3 所指误触风险）。

### 1.5 删除 / 保存 / 详情函数（L163-184）

- **L163-166 `delTask()`**：`if(!curTask) return; if(!confirm("删除此任务及所有子任务？")) return;` → DELETE → closeDrawer → load。**二次确认逻辑在 L164，必须保留**。
- L167-174 `saveDrawer()`：取 d_title/d_status/d_priority/d_detail → PUT → closeDrawer → load。
- L175-183 `openDrawer(id)`：`curTask=tasks.find(t=>t.id==id)` → 回填 4 字段 → 加 `.show`。**详情函数唯一入口**。
- L184 `closeDrawer()`：去 `.show` + `curTask=null`。

### 1.6 渲染入口 `render()`（L216-223）与状态变更路径

- L217 `tree.innerHTML=""`；**L218 `if(!cur){...return;}`（早退 1）**；L220 取 roots；**L221 `if(!roots.length){...return;}`（早退 2）**；L222 `tree.append(build(null))`。
- **所有会改 `tasks` 的路径全部经 `load()` → `render()`**：

| 路径 | 位置 | 是否经 render |
|---|---|---|
| 首次加载 / 定时刷新（5s） | L106-115 load / L248 setInterval | ✅（L113） |
| 切换项目 | L116-117 setProj → load 或 render | ✅ |
| 新建主任务 | L151-156 addRoot → load | ✅ |
| 新建子任务 | L157-162 addChild → load | ✅ |
| 删除任务 | L163-166 delTask → load | ✅ |
| **状态切换/保存** | L167-174 saveDrawer → load | ✅ |
| 改归属 | L128-135 changeOwner → load | ✅ |

**结论**：`render()` 是唯一重绘漏斗，进度条挂在 `render()` 入口即可覆盖全部更新时机（含状态切换）。

### 1.7 服务端交付方式（只读确认，本卡不碰）

- `server.py` L150-160：`GET /` 与 `/index.html` **每次请求从磁盘重读 index.html**（L151 `open(...).read()`），且 **L159 `Cache-Control: no-store`** → 改文件后刷新即生效，**无需重启 8788**；浏览器侧理论上不缓存，但为稳妥仍建议强刷（见 §4.3）。
- `GET /api/tasks?project_id=`（L180-183）返回**全项目任务（含子任务）**，字段：`id,parent_id,title,detail,status,author,updated,priority` → 前端 `tasks` 数组与任务树逐条同源，进度统计直接用 `tasks` 即可与树**逐条一致**。

---

## 2. 改动点清单（精确到函数/行段）

### 2.1 AC-1.1 详情入口显式化（方案 A）

**A. 新增 CSS `.dbtn`**（插在 L39 `.addbtn` 之后，~4 行）：

```css
.dbtn{font-size:12px;color:#2563eb;background:#eef2ff;border:none;padding:6px 10px;min-height:auto;border-radius:8px;flex:none}
```

- 与 `button` 基类（L12-13）冲突面：需覆盖 `background`（L13 蓝底）与 `min-height:44px`（L12）——已覆盖。触达高度 ≈ 30px，移动端可点（配合卡片整体可点）。
- 视觉：浅蓝底蓝字，是"次入口"但不是隐藏入口（一眼可见），弱于保存、不抢主操作。

**B. `build()` 内加按钮**（改动 L196 前插入 5 行，L196 改为追加 dt）：

```js
const dt=document.createElement("button"); dt.className="dbtn"; dt.textContent="详情";
dt.onclick=(e)=>{e.stopPropagation();openDrawer(t.id);};
...
card.append(tri,tt,pr,b,dt);   // 原 L196 追加 dt
```

- **复用现有 `openDrawer(id)`（L175-183），不新写详情函数**。
- `e.stopPropagation()` 阻断冒泡到 `card.onclick`（L198），点按钮只开抽屉、不触发展开/收起。
- **L198 单击展开、L199-202 长按、L203 双击全部保留不动**。

**C. 文案修正**：L87 `<label>详情（长按卡片看这里）</label>` → `<label>详情</label>`（1 行，消除"长按"引导残留）。

### 2.2 AC-1.2 顶部进度概览

**A. DOM**：在 L70 `</div>`（topbar 收尾）与 L71 `</header>` 之间插入（1 行，随 header sticky，滚动始终可见）：

```html
<div id="prog" class="progbar"></div>
```

**B. 新增 CSS `.progbar`**（~6 行，插在 L53 `.dot.off` 之后）：

```css
.progbar{margin-top:8px;background:#eef2ff;border:1px solid #e0e7ff;border-radius:10px;color:#3730a3;font-size:13px;padding:6px 12px;display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.progbar b{font-weight:700}
```

**C. 新增函数 `renderProg()`**（插在 `render()` 前，L216 之前，~9 行）：

```js
function renderProg(){
  const box=document.getElementById("prog");
  if(!cur){box.innerHTML="";return;}
  const c={}; tasks.forEach(t=>{c[t.status]=(c[t.status]||0)+1;});
  const total=tasks.length;
  box.innerHTML='<b>'+(c["进行中"]||0)+' 进行中</b> · '+(c["待验证"]||0)+' 待验证 · '+(c["完成"]||0)+' 已完成 / '+total
    +'<span class="muted">（待办 '+(c["待办"]||0)+' · 已验证 '+(c["已验证"]||0)+' · 阻塞 '+(c["阻塞"]||0)+'）</span>';
}
```

**D. 挂钩**：`render()` 开头（L217 `tree.innerHTML=""` 之前）插 1 行 `renderProg();`。

**口径（design 定，QA 按此核对）**：
- **总数 = 当前项目全部任务（含子任务）**，即 `tasks.length` = `GET /api/tasks?project_id=N` 全部行数；理由：任务树渲染的就是全量（`build()` L187 按 parent_id 递归所有层级），"逐条一致"只能以树同源数组为准。
- **主行**按 PRD：`X 进行中 · Y 待验证 · Z 已完成 / 总数`。
- **待办 / 已验证 / 阻塞单列 muted 后缀**（不并入主行）：保证 5 态逐条可见、QA 可逐状态核对；阻塞是旁路态（T-07 口径），不计入"已完成"，也不冒充"进行中"。
- **更新时机**：`render()` 入口统一调用（§1.6 已证所有改状态路径都经 render），含状态切换（saveDrawer→load→render）、新建、删除、切换项目、5s 定时刷新。
- **空项目/未选项目**：`!cur` → 清空；`cur` 但无任务 → 显示 `0 进行中 · 0 待验证 · 0 已完成 / 0`（renderProg 在 render 早退分支 L218/L221 之前调用，天然覆盖）。

### 2.3 AC-1.3 删除按钮弱化

**A. 新增 CSS `.delbtn`**（~7 行，插在 L57 `.muted` 之后）：

```css
.delbtn{background:none;border:none;color:#dc2626;font-size:12px;padding:6px 4px;min-height:auto;font-weight:400;cursor:pointer;opacity:.75;text-decoration:underline}
.delbtn:hover{opacity:1}
```

- 覆盖 L12/L13 基类（背景透明、小字、去粗、去 44px 高度），视觉从"红色实底大字按钮"降为"红色小字链接"，**明显弱于保存**（保存仍是 L13 蓝底 + L89 flex:1）。

**B. 位置调整**：L92 整行替换为分隔行 + 小字按钮（net +2 行）：

```html
<div style="border-top:1px solid #f3f4f6;margin-top:4px;padding-top:10px">
  <button class="delbtn" onclick="delTask()">删除此任务及子任务</button>
</div>
```

- 保持位于抽屉底部（本就是 `.db` 最后一项），加细分隔线形成"底部独立一行"的弱化视觉，与上方保存/子任务操作区明确分层。

**C. 确认逻辑保留**：`delTask()`（L163-166）**零改动**——L164 `confirm` 二次确认原样保留；AC-1.3 只动按钮外观与位置，不动删除行为。

### 2.4 diff 估算

| 块 | 行数 |
|---|---|
| CSS：`.dbtn` + `.progbar` + `.delbtn` | ≈ 17 |
| HTML：`#prog` 1 行 + L92 删除行替换 | ≈ 4 |
| JS：build() 详情按钮 5 + renderProg() 9 + render 挂钩 1 + L87 文案 1 | ≈ 16 |
| **合计** | **≈ 37 行**（< 200 目标，零新依赖，仅 index.html） |

---

## 3. 风险点

### 3.1 双击/长按与新增详情按钮的交互冲突

- **桌面**：点「详情」→ `stopPropagation` 阻断 `card.onclick`（L198），只开抽屉；双击按钮会触发 `ondblclick` → `openDrawer` 两次（同一抽屉，幂等无害）。单击卡片展开、双击卡片详情行为不受影响。
- **移动端**：按钮上 `touchstart` 仍会 arm 长按 timer（L201），但 `touchend` 清除（L202），普通点击 <500ms 不触发长按；点击后 click 事件由按钮处理。长按按钮本身 ≥500ms → timer 触发 `openDrawer`（与点击结果相同，无害）。
- **回归验证点**：四种入口（点详情 / 单击展开 / 双击详情 / 长按详情）QA 逐项复测。

### 3.2 进度条更新遗漏（哪些路径会改状态）

- 已枚举（§1.6）：状态变更只有 `saveDrawer`（PUT 改 status）一条业务路径，它经 `load()→render()`；新建/删除/切项目/定时刷新同理。**只要 `renderProg()` 在 `render()` 入口调用（早退分支之前），不存在遗漏路径**。
- 唯一易错点：`render()` 有两条早退（L218/L221），若把调用放在早退之后会漏更（如"有 root 但早退/未选项目"时进度条残留旧数字）——设计已钉死调用位置在 L217 之前。

### 3.3 纯静态文件生效方式

- `server.py` L151 每次请求重读 `index.html`、L159 `Cache-Control: no-store` → **改文件即生效，无需重启 8787/8788**（PRD 铁律：不得因本卡重启）。
- 浏览器侧为稳妥建议 **Ctrl+F5 强刷 / 手机清缓存或换隐身**；若线上仍见旧版，先查浏览器缓存而非服务（服务端已 no-store）。

### 3.4 口径核对风险

- QA 用 sqlite/API 交叉核对时须**含子任务**：`SELECT status,COUNT(*) FROM tasks WHERE project_id=N GROUP BY status`（与前端 `tasks` 同源，L182-183 返回全项目行）。若 QA 只数根任务会造成总数不一致——design 已在 §2.2 明示口径，test 文档应同步此口径。
- 阻塞态：单列 muted，不计入主行三态（T-07 旁路口径延续）；如主理人后续要求并入，仅改 `renderProg()` 一行。

---

## 4. AC 映射

| AC | 验收点 | 本设计如何满足 |
|---|---|---|
| AC-1.1 | 桌面上明确看到「详情」按钮并点击打开详情；展开/收起/双击不回归 | §2.1：每张卡片内新增 `.dbtn`「详情」按钮（L196 追加 dt），点击 `stopPropagation` + 复用 `openDrawer`（L175-183）；L198 单击展开 / L203 双击 / L199-202 长按**全部保留**；L87 文案同步去"长按"引导 |
| AC-1.2 | 进度数字与任务树状态分布逐条一致；随状态切换实时更新 | §2.2：header 内 `#prog` 概览条；`renderProg()` 基于全局 `tasks`（与树同源，含子任务）统计 5 态；挂在 `render()` 入口（L217 前）覆盖所有状态变更路径（saveDrawer→load→render 等，§1.6）；口径含"总数=全项目任务"与阻塞/待办/已验证单列，QA 可逐状态核对 |
| AC-1.3 | 删除按钮视觉明显弱于保存；点击仍弹确认；确认后删除正常 | §2.3：L92 改为 `.delbtn` 小字红色链接 + 分隔线独立行（背景透明、12px、underline），弱于保存；`delTask()` L163-166 **零改动**（L164 confirm 保留），删除行为不变 |
| AC-1.4 | 展开/收起/状态切换/保存/新建/5 态/阻塞/操作日志零回归；后端零改动 | §2 全部改动仅新增元素/样式/函数，不触碰 L198 展开逻辑、L206-208 children 动画、L167-174 saveDrawer、L242-247 操作日志、L24-29 徽章配色；server.py 及后端**零改动**（只读确认 L150-160 交付方式）。回归清单见 §5 |

---

## 5. 回归清单（实现阶段交付物）

```
1. 交互：单击卡片展开/收起（L198）→ 正常；双击卡片详情（L203）→ 正常；长按卡片详情（L199-202）→ 正常；点「详情」按钮 → 打开抽屉且不展开。
2. 状态切换：抽屉改状态 → 保存 → 徽章/进度条同步变化；5 态 + 阻塞各自验证。
3. 保存/新建：saveDrawer / addRoot / addChild → 树与进度条同步。
4. 删除：点删除 → confirm 弹窗 → 确认 → 删除 + 进度条更新；取消 → 无操作。
5. 顶部进度条：与 GET /api/tasks?project_id=N 逐状态核对（含子任务）完全一致；空项目显示 0/0；未选项目不显示。
6. 操作日志（renderAudit L242-247）与在线状态（renderPresence L230-241）不回归。
7. 后端零改动：server.py / board.db / 8787 网关不涉及；L0 静态核验 `git diff` 仅 index.html。
```

---

## 6. 边界遵守与偏差记录

- **遵守**：只动 `shared_board/index.html`；不碰 server.py / 后端 API / board.db / 8787 / 门户 / 工作台；不引入新依赖；不重启服务；目标 diff ≈ 37 行（<200）。
- **偏差/澄清**：无功能性偏差。两处设计自决（PRD 授权 design 定）：① AC-1.2 口径——总数含子任务、阻塞/待办/已验证单列 muted（§2.2）；② AC-1.3 采用"视觉降级 + 底部独立分隔行"双管齐下（PRD 两个可选项都做，均为弱化手段，确认逻辑保留）。
