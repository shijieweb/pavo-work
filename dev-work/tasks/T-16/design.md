# T-16 训练面板三项优化 — 实现说明 + 自测证据

- **任务**：在已验收的 T-15 训练面板基础上做三项优化（点击放大 / 中英对照 / 写法号层级采纳）
- **角色**：研发（engineer-t16）
- **状态**：**待验证**（研发无 done 权，已推「待验证」即停）
- **改动范围**：`build_training_panel.py`（生成器）+ 重新生成 `training_panel.html`
- **未改动**：`out/` 原始数据（54 PNG + prompts.csv + prompts_zh.csv 均未写入）、未调 AGNES、未联网

---

## 1. 落地文件清单

| 文件 | 位置 | 说明 |
|---|---|---|
| `build_training_panel.py` | `C:\Users\67972\projects\short-drama-training\` | 生成器，重写（T-15 → T-16），1522 行 |
| `training_panel.html` | `C:\Users\67972\projects\short-drama-training\` | 重新生成，**163,729 bytes (159.9 KB)**，自包含 |
| `design.md` | `dev-work\tasks\T-16\` | 本文件（实现说明 + 自测证据） |
| `test_panel_logic.js` | `dev-work\tasks\T-16\` | 面板 JS 逻辑自测（Node，95 条断言） |
| `selftest_generator_output.txt` | `dev-work\tasks\T-16\` | 生成器自检输出原文（证据）|
| `selftest_logic_output.txt` | `dev-work\tasks\T-16\` | 逻辑自测输出原文（证据）|

> 证据文件用 `.txt` 而非 `.log`：仓库 `.gitignore:12` 忽略 `*.log`，为让 QA 能在仓库里直接看到自测原文，
> 按仓库约定改用 `.txt` 落盘（未用 `git add -f` 绕过 ignore 规则）。

> 训练项目目录（`projects\short-drama-training`）**无 git 仓库**，生成器与 HTML 仅落盘；
> 本 `design.md` 与两份测试脚本/日志在 `C:\Users\67972\WorkBuddy\workbuddy` 仓库提交。

---

## 2. AC 逐条实现说明

### AC-1 点击放大（lightbox）
- HTML 新增 `#lightbox` 容器：`.lb-backdrop`（点空白关闭）+ `.lb-panel`（左大图右文案）+ `.lb-x` 关闭按钮。
- 事件委托：`#groups` 上监听 click，命中 `[data-role="thumb"]` → `openLightbox(file)`，加载**全尺寸原图**（`rel_path`，与缩略图同源但不受 260px 高度约束）。
- lightbox 内同时显示该图 **中文 prompt + English prompt**（AC-1 要求）。
- 关闭三途：点 backdrop 空白处、点 × 按钮、按 **ESC**（`document` keydown）。
- 纯 CSS/JS，零外部请求，`file://` 双击可用。
- 附加：角色参考图（`[data-role="ref-thumb"]`）也可点击放大。
- **关键实现约束**：lightbox 的大图元素由 JS `document.createElement("img")` 动态创建并 append 到 `#lb-stage`，**不写死在 HTML 文本里**——否则静态 `<img` 计数会变成 57，破坏 AC-7 铁律锚点（必须恰好 56）。

### AC-2 中英对照
- 生成器新增 `read_zh_map()`：以 `utf-8-sig` 读 `prompts_zh.csv`，按 `file` 建字典（54 条，0 空）。
- `build_items()` 每项新增 `prompt_zh` + `zh_fallback` 字段。
- 每张卡上下双栏对照：**中文 prompt 在上**（`.prompt.zh`，绿色左边框）、**English prompt 在下**（`.prompt.en`，蓝色左边框）。
- **中文全文不截断**：`.prompt.zh` 不设 `max-height`，完整铺开；英文块给 150px 可滚动（文本全量在 DOM，非截断）。
- 降级：某 file 缺中文 → `prompt_zh` 回落为英文原文，并在标签处标注「（缺中文，降级显示英文）」。本批次 `zh_fallback = 0`，未触发。

### AC-3 写法号层级采纳
- 双层状态模型：
  - `groupState[写法号] ∈ {reject, pending, adopt}`，默认 `pending`；
  - `imgState[file] ∈ {primary, backup, discard}`，默认 `discard`。
- 每组渲染「组状态栏」：状态角标 + 双图优角标 + `不采纳/待定/采纳` 三按钮 + `主图：xx　备选：xx` 实时 meta。
- 每张图渲染「`主图/备选/弃` 三按钮」+ 右上角状态角标；主图绿框、备选蓝框。
- **默认态取舍**：图片默认 `discard`（弃）而非另设第 4 个「待定」态——严格遵守 AC「图三态」，且天然满足 AC-4「未标好图不得采纳」的门槛。视觉上 `discard` 用中性灰（非告警红），面板初始读作「尚未挑选」。

### AC-4「两张都可以」处理方案（重点）
在 `normalizeGroup(g)` 中集中实现 4 条派生规则，任何状态写入后立即调用：

| 规则 | 行为 |
|---|---|
| R1 唯一主图 | 把某图设为「主图」时，同组其它主图**自动降级为「备选」**；若从 localStorage 读回多主图脏数据，保留首张、其余降备选 → **主图恒唯一** |
| R2 双图都好 | 组内 ≥2 张为「主图/备选」→ 组**自动置为 `adopt`** 并打「**双图优**」标；若此时 0 主图（两张都备选），**首张好图自动升为主图**（强制恰好 1 主图） |
| R3 采纳门槛 | 组要标 `adopt` 必须 ≥1 张「主图/备选」；否则 `alert` 阻断、状态不变 |
| R4 采纳必有主图 | 组为 `adopt` 且有好图但无主图 → 首张好图升主图（保证导出「主图文件名」永不为空）|

- 双图优组改判为「待定/不采纳」时，因「双图优」是派生态，会 `confirm` 提示并把该组图片重置为「弃」，避免状态自相矛盾。
- 导出每组记录：**组决策 + 主图文件名 + 备选文件名**（见 AC-6）。

### AC-5 统计条
6 格实时统计：`总图数` / `已采纳图`(primary+backup) / `未采纳图`(discard) / `采纳率` + **新增** `写法号采纳数`(x/27) / `双图优数`。

### AC-6 持久化 + 导出
- localStorage 键 `training_panel_adoption_batch001_v2`，结构 `{imgState:{file:state}, groupState:{写法号:state}}`。
- 兼容迁移：若无 v2 记录但存在 T-15 的 v1 键，把 v1 的 `adopt` 迁为「备选」并将相应组置 `adopt`，再走归一化补主图（控制台提示复核）。
- **导出 JSON**：`summary`（含 `adopted_groups`/`dual_good_groups`）+ `groups[]`（写法号/组决策/双图优/主图/备选/图片数/采纳图片数）+ `images[]`（图状态/中英文 prompt/url/相对路径）。
- **导出 CSV**：**1 行/组**，列 = `写法号,组决策,主图文件名,备选文件名,图片数,采纳图片数`，带 UTF-8 BOM（Excel 中文不乱码）。

### AC-7 铁律不变
54 图全量静态预渲染（Python 端出 `<img>`，JS 禁用也可见）、0 缺失、0 截断、0 base64 内嵌、图片走本地相对路径。详见第 3 节数字。

### AC-8 保留项
顶部「阶段说明」+「采纳门槛（三闸并行）」+ 角色参考图区**全部保留**；另新增「两张都可以怎么办」规则说明块。同时保留筛选（写法号/图片状态/**新增组决策**）、批量（全选采纳/全部清除）、导出、页脚。

---

## 3. 自测证据（必做，数字均为实测）

### 3.1 生成器自检（`python build_training_panel.py`，46 项断言全过）
> 原文见 `selftest_generator_output.txt`

| 检查项 | 实测 | 期望 | 结论 |
|---|---|---|---|
| 内联索引 ITEMS 长度 | 54 | 54 | ✅ |
| 磁盘 PNG 实际数量 | 54 | 54 | ✅ |
| 缩略图 `img.thumb[data-role]` | 54 | 54 | ✅ |
| 参考图 `class=ref-img` | 2 | 2 | ✅ |
| **HTML `<img` 标签总数** | **56** | **56** | ✅ |
| **唯一 `wXX_Y.png` 文件名** | **54** | **54**（0 缺失）| ✅ |
| **`data:image/...;base64` 出现次数** | **0** | **0** | ✅ |
| 文件名全部出现在 HTML | 54/54 | 54 | ✅ |
| 英文 prompt 全文未截断 | 54/54 | 54 | ✅ |
| 中文 prompt 全文未截断 | 54/54 | 54 | ✅ |
| 中文块 `data-role=prompt-zh` | 54 | 54 | ✅ |
| 英文块 `data-role=prompt-en` | 54 | 54 | ✅ |
| **中文锚点「同一个齐肩黑发」出现** | **54** | **54** | ✅ |
| 中文缺失降级为英文条数 | 0 | 0 | ✅ |
| **`data-writing` 去重** | **27** | **27** | ✅ |
| 分组容器 `.group` | 27 | 27 | ✅ |
| **lightbox 容器/关闭钩子/舞台/中文位/英文位** | 全 True | True | ✅ |
| **组三态按钮** adopt/pending/reject | 27/27/27 | 27 | ✅ |
| 组状态角标 / 双图优角标 | 27 / 27 | 27 | ✅ |
| 图三态按钮 primary/backup/discard | 54/54/54 | 54 | ✅ |
| 图状态角标 | 54 | 54 | ✅ |
| 统计 6 格 + 筛选 3 项 + 批量 2 项 + 导出 2 项 | 全 True | True | ✅ |
| 阶段说明区 / 角色参考图区 | True / True | True | ✅ |
| 相对路径可解析且文件存在 | 54/54 | 54 | ✅ |

**产出**：`training_panel.html` = 163,729 bytes (159.9 KB) < 5MB ✅（图片未内嵌）

### 3.2 独立 grep 复核（不依赖生成器自检，交叉验证）
```
1. <img 标签总数              : 56
2. 唯一 wXX_Y.png             : 54
3. base64 内嵌图片            : 0
4. 中文锚点「同一个齐肩黑发」 : 54
5. data-writing 去重          : 27
6. lightbox 容器              : 1
7. 组采纳按钮 data-group-set  : 27
8. 图主图按钮 data-set        : 54
9. 中文 prompt 块             : 54
10. 文件大小(bytes)           : 163729
```
> 与生成器自检数字**完全一致**。

**计数口径说明（一个真实踩坑，已修）**：首版自检把 `data-role="thumb"` 直接计数得 **55**（多 1），原因是 JS 里的选择器字符串 `closest('[data-role="thumb"]')` 也被算进去了。已改为「渲染标签级」精确串 `class="thumb" data-role="thumb"` 计数，得 54。同理组状态角标/双图优角标也改用完整标签串计数。**该 off-by-one 是自检真实抓出来的，非事后补写。**
> 另：`prompt` / `prompt_zh` 全文在 HTML 中**只出现一次**（只在图卡 DOM，不再重复灌进内联 JSON），lightbox 与导出的文案一律用 `readPrompt()` 从 DOM 读取。这既让中文锚点计数恰好等于 54（口径干净），也让 HTML 更小。

### 3.3 面板 JS 逻辑自测（`node test_panel_logic.js`，95 条断言全过）
> 原文见 `selftest_logic_output.txt`。做法：从**实际生成的 HTML** 中抽出 `<script>` 块，用最小 DOM stub **真实执行**，被测代码就是面板里跑的那份（未 mock 任何被测逻辑）。

| 分组 | 覆盖内容 | 结果 |
|---|---|---|
| [0] 载入 | JS 无异常执行；ITEMS=54；GROUP_KEYS=27 | ✅ 3 |
| [1] 初始态 | 总图 54 / 已采纳 0 / 未采纳 54 / 写法号采纳 0/27 / 双图优 0 | ✅ 7 |
| [2] AC-4 | 单张标好**不**触发自动采纳（组仍 pending，非双图优）| ✅ 4 |
| [3] AC-4 | 两张都好 → 组**自动 adopt + 双图优**，主图恰好 1，角标/meta 正确 | ✅ 8 |
| [4] AC-4 | **唯一主图**：改设另一张为主图 → 原主图自动降备选，主图仍 1 张 | ✅ 5 |
| [5] AC-4 | **两张都标备选** → 仍强制恰好 1 主图（首张好图自动升主图）| ✅ 4 |
| [6] AC-4 | **采纳门槛**：无好图点采纳 → alert 阻断，状态不变 | ✅ 2 |
| [7] AC-4 | 单张备选 + 手工采纳 → 自动补主图，导出主图非空 | ✅ 5 |
| [8][9] AC-4 | 双图优改判：confirm=false 不动；confirm=true 图片重置并改判 | ✅ 5 |
| [10] AC-6 | localStorage 写入含 `imgState`+`groupState`，组决策正确持久化 | ✅ 4 |
| [11] AC-3/5 | 全选采纳 → 54/0/100%/27组/27双图优；**27 组均恰好 1 主图** | ✅ 7 |
| [12] AC-6 | CSV **1 行/组**：28 行(1 表头+27)、6 列、表头精确匹配、含 BOM | ✅ 6 |
| [13] AC-6 | JSON：groups=27、images=54、summary 各数正确、中英文 prompt 齐 | ✅ 11 |
| [14] AC-1 | lightbox 开/关、大图 src、中英文 prompt、meta、**ESC 关闭**、**点空白关闭**、点缩略图经事件委托打开 | ✅ 14 |
| [15] | 事件委托：图三态按钮、组三态按钮均生效 | ✅ 2 |
| [16] | 全部清除归零；**400 次随机操作后不变量总扫**：无多主图 / 采纳组必有唯一主图 / 双图优组必为采纳 | ✅ 8 |

**关键不变量（400 次随机操作模糊测试后仍成立）**：
- `每组主图数 ≤ 1`（违例 0）
- `组为 adopt ⇒ 主图数 == 1`（违例 0）
- `双图优 ⇒ 组为 adopt`（违例 0）

### 3.4 其它质量校验
| 检查 | 结果 |
|---|---|
| HTML 标签良构（Python `HTMLParser` 全量解析）| 未闭合标签 0，结构错误 0 ✅ |
| 生成器幂等性（连跑两次 diff）| 仅「生成时间」1 行不同 ✅ |
| 原始数据未被改动 | `prompts.csv` mtime 仍 Aug 14 14:46、`prompts_zh.csv` Aug 14 23:45、PNG 仍 54 ✅ |
| 无网络/无 AGNES 调用 | `requests/urllib/httpx/socket/agnes/api_key/subprocess/aiohttp` 命中数**全为 0**；import 仅 `csv,html,json,os,re,sys`（纯标准库）✅ |

---

## 4. 实现取舍与遗留说明

1. **模板拼接方式**：T-15 用 `str.format()` 渲染，导致 CSS/JS 里所有 `{}` 必须写成 `{{}}`，极易出错。T-16 改为 `HTML_HEAD + HTML_BODY + HTML_SCRIPT` 三段拼接 + `@@TOKEN@@` 占位替换，彻底免除花括号转义。
2. **图片默认态 = `discard`**：严格遵守 AC「图三态」不引入第 4 态；视觉上用中性灰表达「尚未挑选」，并天然构成 AC-4 采纳门槛。
3. **采纳率口径**：因图片无「待定」态，采纳率 = 已采纳图 / 总图数（T-15 为 已采纳/已决策）。已在统计条标签明示为「采纳率」。
4. **双图优是派生态**：不可手工取消，只能通过降级图片状态改变，避免「两张都好但组不采纳」这类自相矛盾状态。
5. **待老板/QA 验证项**：真实浏览器中的视觉呈现（本地 `file://` 双击打开）、54 图肉眼可见性、lightbox 实际观感与大图清晰度。逻辑与计数已由上述 46 + 95 条断言覆盖，但**浏览器渲染需人工过目**。

---

## 5. 结论

三项优化（AC-1 点击放大 / AC-2 中英对照 / AC-3+AC-4 写法号层级采纳与双图优）全部实现，AC-5/6/7/8 一并满足。
**自测数字**：生成器自检 46 项全过 + 逻辑自测 95 条全过 + 独立 grep 交叉复核一致 + 400 次随机操作不变量零违例。
铁律未破：`<img>` 56 / 唯一 PNG 54 / base64 0 / 中文锚点 54 / 写法号 27。

**状态：待验证**（研发无 done 权，交 QA 与老板闸）
