# test.md · T-16 训练面板三项优化 · QA 独立验收

> 角色：qa-t16（测试）｜研发/测试分离铁律：**只验收、绝不改代码**，无 done 权，结论仅到「已验证 / 打回」。
> 验收时间：2026-08-15｜被测产物：`C:\Users\67972\projects\short-drama-training\training_panel.html`（163,729 B / 159.9 KB，自包含）
> 生成器：`build_training_panel.py`（1,524 行，未改动、未重跑，见 OBS-4）

## 0. 验收结论

**建议放行（已验证）**，0 个 BUG，4 个观察项（均非缺陷）。

| 证据来源 | 命令 | 通过 | 失败 | 退出码 |
|---|---|---|---|---|
| 研发自写逻辑测试（复跑） | `node dev-work/tasks/T-16/test_panel_logic.js` | **95** | 0 | 0 |
| QA 独立结构核验（QA 自写） | `python dev-work/tasks/T-16/qa_verify_structure.py` | **40** | 0 | 0 |
| QA 独立行为核验（QA 自写） | `node dev-work/tasks/T-16/qa_verify_behavior.js` | **53** | 0 | 0 |
| **合计** | — | **188** | **0** | — |

其中 QA 自有断言 **93 条**（40 结构 + 53 行为），与研发脚本手法刻意不同以保证独立性：
研发用手写 `El` 类模拟真实 DOM 树（覆盖 UI 同步路径）；QA 用 **Proxy 万能 stub 吞掉视图层**，把状态机+导出当纯模型拷问，专打对抗性边界（confirm 取消 / 脏 localStorage 注入 / 采纳门槛回落 / 自定种子 1200 次 fuzz）。

### 关键数字一览

| 核验点 | 期望 | 实测 | 结果 |
|---|---|---|---|
| `<img>` 标签总数 | 56（54 缩略图 + 2 参考图） | **56** | PASS |
| tag 级 `data-role="thumb"` | 54 | **54** | PASS |
| HTML 中唯一 `wXX_Y.png` | 54，0 缺失 | **54 / 缺失 0 / 幽灵 0** | PASS |
| 54 个 thumb src 磁盘存在性 | 全部存在、互不重复 | **54 存在 / 54 唯一** | PASS |
| `data:image/*;base64` | 0 | **0** | PASS |
| HTML 体积 | < 1MB | **159.9 KB** | PASS |
| 中文锚点「同一个齐肩黑发」 | 54 | **54** | PASS |
| `data-writing` 去重 | 27（1–27 连续） | **27 / 1–27 连续无跳号** | PASS |
| 组规模 | 27 组 × 2 图 | **{2:27}，全组==2** | PASS |
| 54 条中文 prompt 全文内联 | 0 截断 0 缺失 | **54/54 全文命中** | PASS |
| 54 条英文 prompt 全文内联 | 0 截断（对照） | **54/54 全文命中** | PASS |
| `zh_fallback` 降级数 | 0（54 全有中文） | **true:0 / false:54** | PASS |
| PNG 文件完整性（独立解头） | 签名+IHDR 合法 | **54/54 合法，1472×2624，共 193.8MB** | PASS |
| 不变量 fuzz | 零违例 | **研发 400 次 + QA 1200 次 = 零违例** | PASS |

---

## 1. AC 覆盖矩阵（逐条判定）

### AC-1 点击放大 lightbox（点空白/ESC 关闭 + 灯箱内中英文 prompt）→ **PASS**

| 验证手段 | 命令 / 位置 | 证据 | 结果 |
|---|---|---|---|
| DOM 结构静态核验 | `qa_verify_structure.py` [6][6d] | `id="lightbox"` ×1；含 `lb-backdrop[data-role=lb-close]`、`lb-x` 关闭钮、`lb-stage`、`lb-file`、`lb-meta`、**`lb-zh`（中文 prompt）+ `lb-en`（English prompt）** 双栏；`Escape` 锚点存在；`lightbox` 出现 8 次 | PASS |
| 缩略图入口 | 同上 | 每卡含 `<span class="zoom-hint">点击放大</span>`（54 张卡 + 1 处 JS/说明引用 = 55） | PASS |
| 真实行为（打开/关闭/内容） | 复跑 `test_panel_logic.js` [14] 段 14 条断言 | 初始隐藏 → 点缩略图（事件委托）打开 → 大图 src 指向该图相对路径 → 显示文件名 `w07_1.png`、写法号+状态 meta、**中文 prompt、英文 prompt** → 打开锁 body 滚动 → **ESC 关闭** → **点空白处关闭** → 关闭恢复滚动 → 可再次打开 | PASS |
| 参考图灯箱 | grep `openRefLightbox` | 角色参考图亦可点开放大 | PASS |

> 注：无头环境不做真机像素渲染，**lightbox 实际观感**见 OBS-1（观察项，非 BUG）。

### AC-2 每卡中文 prompt 与英文上下对照 + 中文全文不截断 → **PASS**

| 验证手段 | 证据 | 结果 |
|---|---|---|
| 结构计数 | `data-role="prompt-zh"` = **54**，`data-role="prompt-en"` = **54**，成对上下排布（`prompt-label zh` / `prompt-label en`） | PASS |
| 中文真实性抽查 3 条（含点名的写法号 24） | 写法号 **24**（w24_1.png，中文 79 字）、写法号 **5**（w05_1.png，82 字）、写法号 **19**（w19_1.png，85 字）→ 三条 `prompt_zh` **全文字符串完整出现在 HTML**（非前缀/非截断） | PASS |
| 全量强校验（比抽查更严） | 从 `prompts_zh.csv` 逐行取全文做 `in html`：**54/54 全部完整内联，未内联 0 条** | PASS |
| 英文对照 0 截断 | `prompts.csv` 54 条英文全文亦 **54/54 完整内联** | PASS |
| 数据源一致性 | `prompts_zh.csv` 54 行、列 `['file','写法号','prompt_zh']`、**无空值**；中英 file 集合**完全一致**（仅英 0 / 仅中 0） | PASS |
| 降级路径 | 生成器有 `zh_fallback` 降级分支；本次产物 `zh_fallback": true` = **0**，`false` = **54** → 无一条降级为英文 | PASS |

### AC-3 采纳模型上移到写法号层级（组三态 + 图三态）→ **PASS**

| 验证手段 | 证据 | 结果 |
|---|---|---|
| 分组结构 | `data-writing` 去重 **27**，1–27 连续；每组 `（2 张）`，组规模分布 `{2:27}` | PASS |
| 组三态按钮 | `data-group-set="reject|pending|adopt"`，`adopt` 计数 **27**（每组一套）；组态标签 `data-role="group-state-tag"` 27+1 | PASS |
| 图三态按钮 | `data-set="primary"` = **54**（每图一套），另有 `backup`/`discard`；图态标签 `data-role="state-tag"` 54+1 | PASS |
| 状态机行为 | `qa_verify_behavior.js` [0][2]：`GROUP_KEYS`=27、每组恰好 2 图；组/图状态读写与联动生效；研发 [15] 段验证按钮事件委托生效 | PASS |
| 术语齐备 | `主图`(193) / `备选`(236) / `弃`(168) / `不采纳` / `待定` / `采纳` 全部存在 | PASS |

### AC-4「两张都可以」处理方案（老板点名缺口）→ **PASS**（含 3 条子规则）

| 子规则 | 验证手段 | 证据 | 结果 |
|---|---|---|---|
| ① 组标「采纳」须 ≥1 张主图/备选 | `qa_verify_behavior.js` [1] 对抗测试 | 全弃组点「采纳」→ **被拒**，组态保持默认 `pending`；弹出 alert「无法采纳写法号 1：…必须至少有 1 张图被标为「主图」或「备选」」；[2] 单主图组则采纳成功 | PASS |
| ② 两张都好 → 自动「采纳·双图优」+ 强制唯一主图 | [3][4] | [3] 两张都设**备选**（无主图）→ 组**自动升级 adopt**、`isDualGood=true`、**强制恰好 1 张主图**、另 1 张为备选；[4] 两张都点**主图** → 主图**唯一**（=后点击那张）、先点者**自动降备选**、组态 adopt、双图优 | PASS |
| ③ 导出记录 组决策 + 主图 + 备选 | [10][11] | CSV 表头 `写法号,组决策,主图文件名,备选文件名,图片数,采纳图片数`；27 组导出行**全部带主图文件名**（缺主图行数 0）；JSON 组记录含 `writing_no/group_state_label/primary_file/backup_files`，「采纳却无主图」的组 = **0** | PASS |
| 一致性维护（自愈） | [5][6][7][8] | [5] 双图优改判「不采纳」+ **confirm 取消 → 状态完全零变更**；[6] confirm 同意 → 两图重置为弃、无残留主图、无矛盾；[7] 采纳组撤掉唯一好图 → 组态**自动回落**默认、零违例；[8] **脏 localStorage 注入**（采纳无好图 / 双主图 / 组态与双图优矛盾 / 不存在的 file 与组）→ normalize 后**全部自愈、全局零违例** | PASS |
| 不变量 fuzz | [12] + 研发 [16] | QA 自定种子 **1200 次**随机操作（其中 623 次随机同意二次确认、其余取消）→ I1 每组主图≤1 / I2 采纳组必有唯一主图且≥1好图 / I3 双图优必为采纳 / I4 状态值合法 → **零违例**；研发 **400 次** fuzz 亦零违例 | PASS |
| 规则对老板可见 | grep HTML | 面板内「**「两张都可以」怎么办**」规则说明块存在（①②③ 三条，含「系统强制每组恰好 1 张主图」「导出时每组记录组决策+主图+备选」） | PASS |

> 实现方式与 PRD 措辞的差异见 **OBS-2**（不影响判定：唯一主图不变量成立、可随时切换、导出无歧义）。

### AC-5 统计条新增 写法号采纳数 / 双图优数 → **PASS**

| 验证手段 | 证据 | 结果 |
|---|---|---|
| DOM 核验 | 统计条 6 格：总图数 / 已采纳图 / 未采纳图 / 采纳率 / **写法号采纳数** / **双图优数**（`id="stat-dual"`，`.stat-box.hl` 高亮） | PASS |
| 行为核验 | 研发 [11]：写法号采纳数 = **27/27**、双图优数 = **27**；QA [13]：`bulkAdoptAll` 后 27 组全采纳、`bulkClearAll` 后 0 采纳组 / 0 好图 | PASS |
| T-15 四项保留 | 总图数 / 已采纳图 / 未采纳图 / 采纳率 均在 | PASS |

### AC-6 localStorage 持久化 + 导出含组层级 → **PASS**

| 验证手段 | 证据 | 结果 |
|---|---|---|
| 持久化往返 | QA [9]：写入 `localStorage` 成功 → `loadStore()` 重载后**主图/备选/组态（采纳）全部保持**；key `training_panel_adoption_batch001_v2`（含 V1 迁移常量 `STORAGE_KEY_V1`） | PASS |
| 脏数据健壮性 | QA [8]：非法/矛盾状态注入后自愈、零违例 | PASS |
| CSV 导出 | QA [10]：1 表头 + **27** 行（1 行/组）、**UTF-8 BOM**（首字符码 0xFEFF，Excel 中文不乱码）、6 列、首行组决策含「采纳」、含 `wXX_Y.png` 主图名 | PASS |
| JSON 导出 | QA [11]：`groups`=**27**、`images`=**54**、`summary` 含 `total_groups/adopted_groups/dual_good_groups/adopted_images`、组记录四要素齐备；研发 [13] 另验图记录含中英文 prompt（自 DOM 读取，避免重复灌数据） | PASS |
| 清除 | 研发 [16]：清除后 localStorage 键**已移除**、54 图回 `discard` | PASS |

### AC-7 铁律：54 图全量显示（0 缺失 / 0 截断 / 0 base64）→ **PASS**（重点项）

| 验证手段 | 证据 | 结果 |
|---|---|---|
| `<img>` 总量 | **56** = 54 缩略图 + 2 参考图（非 thumb 的 2 个 src 实测为 `01_配方训练/角色参考图/charA_front.png`、`charA_side.png`） | PASS |
| thumb 数 | tag 级 `data-role="thumb"` = **54**（按标签解析，非全文计数） | PASS |
| 文件覆盖 | 磁盘 54 张 ↔ HTML 唯一文件名 54 个；**缺失 0**、**幽灵文件名 0** | PASS |
| src 可达性 | 54 个 thumb src 相对路径**逐一在磁盘存在**（不存在 0），且 **54 个互不重复** | PASS |
| 禁 base64 | `data:image/*;base64` = **0**；HTML 仅 **159.9 KB**（194MB 未被内嵌） | PASS |
| 文本 0 截断 | 中文 54/54 + 英文 54/54 全文完整内联 | PASS |
| 图片文件本身完整 | 独立解 PNG 头：54/54 签名 `\x89PNG` + `IHDR` 合法、无 0 字节/过小文件、分辨率统一 **1472×2624**（9:16 竖屏，符合训练配方），合计 193.8MB | PASS |
| 懒加载 | 缩略图带 `loading="lazy"`（54 张大图不阻塞首屏） | PASS |

### AC-8 顶部阶段说明 + 角色参考图区保留 → **PASS**

| 验证手段 | 证据 | 结果 |
|---|---|---|
| 阶段说明 | 「阶段说明：本面板服务于「配方训练线」的人工采纳环节…」+「采纳门槛（三闸并行）①②③」块存在 | PASS |
| 角色参考图区 | 「角色参考图」出现 8 次，2 张参考图 `<img>` 在位；磁盘核验 `charA_front.png`(1094 KB)、`charA_side.png`(1067 KB) 均存在 | PASS |
| T-15 能力不回退 | `导出`(8)、`localStorage`(4)、筛选/批量（`applyFilters`、`bulkAdoptAll`、`bulkClearAll`）均在；研发 [15][16] 验证按钮与批量行为生效 | PASS |

---

## 2. 缺陷清单

**无 BUG。** 本轮 188 条断言 0 失败，`54 图未全显 / 中文缺失 / 双图规则矛盾` 三类高危均已定量排除。

> 轮次说明（QA 两轮上限）：
> - **Round 1**：QA 行为核验出现 1 条 FAIL —— 「弹出规则 alert 提示」。定位为 **测试代码自身缺陷**（QA 正则写 `至少 1 张`，源码文案实为「必须至少有 1 张图」），**源码行为正确**（组确实被拒绝采纳且弹出正确提示）。按路由规则由 QA 自行修正断言，**未向研发提单、未改任何源码**。
> - **Round 2**：回归 53/53 PASS，退出码 0。结束。

## 3. 观察项（非 BUG，不阻塞放行）

| 编号 | 内容 | 建议 |
|---|---|---|
| **OBS-1** | 无头环境无法真机解码 PNG 渲染、无法评估 lightbox 实际观感（放大清晰度、遮罩层级、长 prompt 侧栏滚动、54 张大图滚动流畅度）。已用「PNG 头合法 + src 磁盘可达 + 相对路径正确 + lazy 加载」间接兜底。 | **`file://` 双击打开后 54 图渲染 + lightbox 实际观感，需老板/主理人开浏览器确认**（观察项，非 BUG） |
| **OBS-2** | AC-4 措辞为「**强制你点选** 1 张主图」，实现为：两张都好且无主图时**自动指派组内首张为主图**（另一张备选），并允许随时点另一张改判、组头 `group-meta` 显示「主图：xxx　备选：xxx」、亮「双图优」徽标。属非阻塞式实现，面板规则说明块已如实描述该行为，唯一主图不变量成立、导出无歧义。 | P3 体验建议（非缺陷）：双图优首次触发时给一次轻提示「已自动指定 wXX_1 为主图，可点另一张改判」，降低老板误认风险 |
| **OBS-3** | 写法号 24 的**英文** prompt 原始数据本身中英混排（`…about to push the door open，中景，傍晚街头…`），源 `prompts.csv` 即如此，面板忠实透传。 | 属上游数据特征，**非 T-16 引入**；如需清洗另开任务（涉改 `out/` 只读数据，须老板授权） |
| **OBS-4** | **未重跑生成器** `build_training_panel.py`——重跑会覆盖正在验收的产物 `training_panel.html`（同路径输出），QA 不对被验收物做写操作。生成器可复现性以研发 `selftest_generator_output.txt` 为参考证据。 | 如需验可复现性，建议放行后由研发改临时输出路径再跑 diff |

## 4. QA 产出资产（本次新增，均为只读验证脚本，不属源码）

| 文件 | 说明 |
|---|---|
| `dev-work/tasks/T-16/qa_verify_structure.py` | QA 自写结构核验：独立正则/csv 重新解析 HTML，40 条断言 |
| `dev-work/tasks/T-16/qa_verify_behavior.js` | QA 自写行为核验：Proxy stub 直取状态机 + 导出，53 条对抗性断言（含 1200 次自定种子 fuzz） |
| `dev-work/tasks/T-16/test.md` | 本文件（覆盖矩阵） |

## 5. 复现命令

```bash
# 1) 研发自写逻辑测试（复跑，cwd = workbuddy 仓库根）
node dev-work/tasks/T-16/test_panel_logic.js          # 95 PASS / 0 FAIL / exit 0

# 2) QA 独立结构核验
python dev-work/tasks/T-16/qa_verify_structure.py     # 40 PASS / 0 FAIL / exit 0

# 3) QA 独立行为核验
node dev-work/tasks/T-16/qa_verify_behavior.js        # 53 PASS / 0 FAIL / exit 0
```

---

**QA 结论：三项优化（点击放大 / 中英对照 / 「两张都可以」处理方案）功能齐备，AC-1~AC-8 全 PASS，AC-7 铁律（54 图全量显示、0 缺失、0 截断、0 base64）定量成立且未破坏 T-15 已验收能力 → 建议放行。**
**剩余唯一开放事项为 OBS-1：真机浏览器观感确认（需老板/主理人本机打开）。QA 无 done 权，最终采纳待老板闸。**
