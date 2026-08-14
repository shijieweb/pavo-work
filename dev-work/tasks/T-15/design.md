# design · T-15（研发填写，推「待验证」即停）

> 开发按此填：实现方式 + git diff（若改仓库）/ 生成器逻辑 + 自测证据 + 面板运行态截图。
> 无输出=未测=不通过。

状态：**待验证**（研发自测通过，等 QA 独立验收 + 主理人把关；研发无 done 权）

---

## 一、交付物清单

| # | 文件 | 大小 | 说明 |
|---|---|---|---|
| 1 | `C:\Users\67972\projects\short-drama-training\build_training_panel.py` | 29,765 B | 面板生成器（读 CSV + 扫 PNG + 预渲染 HTML + 内建自检） |
| 2 | `C:\Users\67972\projects\short-drama-training\training_panel.html` | 108,013 B (105.5 KB) | 采纳面板产物，自包含，`file://` 双击即开 |
| 3 | `C:\Users\67972\projects\short-drama-training\scripts\test_panel_logic.js` | 12,032 B | 无头逻辑测试（30 条断言，Node + 最小 DOM stub） |

**未改动**：`batch-001/out/` 原始数据全程只读；未调用 AGNES。

---

## 二、实现说明

### 2.1 数据读取（`build_training_panel.py`）

- **CSV 去 BOM**：`open(..., encoding='utf-8-sig')` + `csv.DictReader`。实测源文件首字节 `EF BB BF`（UTF-8 BOM）、行尾 CRLF，故用 `newline=''` 交给 csv 模块处理。额外对每个表头键做 `key.lstrip('\ufeff').strip()` 兜底，防止 BOM 残留导致 `file` 列取不到。
- **以磁盘 PNG 为主键（防漏关键设计）**：`scan_png_files()` 扫描 `out/*.png`，`build_items()` 用 **PNG 文件列表**做外层循环、CSV 仅作为 prompt/url/写法号的补充字典。即使 CSV 缺行，图仍会被收录（prompt 留空但卡片在）——保证「一张不漏」不依赖 CSV 完整性。
- **自然排序**：文件名按 `w(\d+)_(\d+)\.png` 正则解析成 `(写法号, 子序号)` 整型元组排序，避免字典序把 `w10` 排到 `w2` 前面。
- **写法号回退**：优先取 CSV 的 `写法号` 列，为空时从文件名解析，再兜底 `未知`。

### 2.2 相对路径（保证 file:// 离线可见）

```python
rel = os.path.relpath(abs_png, HTML_OUTPUT_DIR)   # HTML 输出目录 = 训练项目根
rel.replace(os.sep, '/')                          # 反斜杠 -> 正斜杠
```

产出形如 `01_配方训练/实验批次/batch-001/out/w01_1.png`、参考图 `01_配方训练/角色参考图/charA_front.png`。
统一转 POSIX 分隔符是必要的：Windows 的 `\` 在 HTML `src` 里会被当转义字符处理，浏览器解析不到。中文目录名在 UTF-8 声明的文档里可直接原样引用，无需 percent-encode。

### 2.3 关键决策：服务端预渲染，而非 JS 动态建卡

第一版把图卡交给 JS 循环 `ITEMS` 动态生成，功能正常但**静态 HTML 里只有 3 个 `<img>` 标签**，而 AC-1.3 要求「每张图卡含缩略图」、验收锚点要求 `<img` 数 == 54。为此重构为 **Python 端 `render_card()` / `render_groups()` 预渲染全部 54 张卡**：

- HTML 静态文本中**真实存在 54 个** `<img class="thumb" data-role="thumb">`，可被 `grep` 直接计数验证；
- JS 禁用时全部图片与 prompt 依然可见（渐进增强）；
- JS 职责收窄为：从 `localStorage` 恢复三态 → `syncCard()` 刷新视觉 → 事件委托处理点击。不再有 `innerHTML` 重建，批量操作只做状态同步，54 张卡不重排、无闪烁。

代价是 HTML 从 43.5 KB 增至 105.5 KB —— 远低于 5MB 阈值，可接受。

### 2.4 不内嵌图片（铁律）

图片一律走相对路径 `<img src="01_配方训练/...">`。生成器内建断言 `"data:image/png;base64" not in html_text`，若将来有人误改成内嵌会直接构建失败。
54 张原图共 194MB，base64 后膨胀 ~33% 约 260MB，内嵌必卡死浏览器 —— 已从构建层面封死这条路。

### 2.5 HTML 结构与 CSS/JS 转义

生成器用 `str.format()` 注入数据，故模板内所有 CSS/JS 字面花括号均写成 `{{ }}`。已加校验：产物中 `{{` / `}}` 残留计数均为 **0**，证明转义正确、无 `.format()` 泄漏。

页面结构：

```
header.hero      阶段说明 + 采纳门槛（AC-1.10）
div.toolbar      统计条(5格) + 筛选(写法号/状态) + 批量(全选采纳/全部清除) + 导出(JSON/CSV)  [sticky]
main
  section.refs   角色参考图 charA_front / charA_side（AC-1.9）
  div#groups     27 个 .group（写法号 1–27），每组 .grid 内 2 张 .card
footer           生成时间 + 数据源 + 「导出后存入 04_采纳区/」提示  [fixed]
```

单卡内容（AC-1.3）：缩略图（`object-fit: contain`，不裁切变形）、写法号角标、状态角标、文件名、**完整 prompt 全文**（`white-space: pre-wrap` + `max-height:160px` 内部滚动，是滚动条而非截断，全文始终在 DOM 里）、url 原文+可点击链接、三态按钮组。

### 2.6 三态 / 持久化 / 导出

- 三态 `pending`(灰) / `adopt`(绿) / `reject`(红)，切换即时更新卡片边框、状态角标、按钮高亮、统计条、筛选可见性。
- `localStorage` key = `training_panel_adoption_batch001`，`setState()` 每次写盘，刷新不丢。
- 导出 JSON：含 batch/导出时间/总数/采纳数/驳回数/待定数 + 54 条完整记录（file/写法号/state/prompt/url/rel_path）。
- 导出 CSV：**带 UTF-8 BOM**（`\ufeff`）保证 Excel 打开中文不乱码，字段按 RFC4180 双引号转义（`"` → `""`），CRLF 行尾。
- 文件名含日期时间戳 `采纳记录_batch-001_YYYYMMDD_HHMMSS.{json,csv}`，下载后 `alert` 提示存入 `04_采纳区/`。
- **采纳率定义**：`采纳 / (采纳 + 不采纳)`，即已判定项中的采纳占比，未判定的「待定」不计入分母（避免审阅初期采纳率被待定项稀释而失真）。

---

## 三、自测证据

### 3.1 生成器运行输出（`python build_training_panel.py`）

```
[信息] 项目根       : C:\Users\67972\projects\short-drama-training
[信息] CSV          : ...\batch-001\out\prompts.csv
[信息] 图片目录     : ...\batch-001\out
[信息] 参考图目录   : ...\01_配方训练\角色参考图
[信息] CSV 数据行   : 54
[信息] PNG 文件数   : 54
[信息] 参考图数量   : 2 -> ['charA_front.png', 'charA_side.png']
============================================================
[自检] 开始验证 (铁律: 54 张全量显示, 一张不漏)
------------------------------------------------------------
  内联数据 ITEMS 长度        = 54
  磁盘 PNG 实际数量          = 54
  缩略图 <img data-role=thumb> = 54
  参考图 <img class=ref-img>  = 2 (另计)
  HTML 全部 <img 标签总数     = 56 (期望 56)
  文件名全部出现在 HTML       = 54/54
  prompt 全文未截断           = 54/54
  是否存在 base64 内嵌 PNG    = False (必须为 False)
  相对路径可解析且文件存在   = 54/54
------------------------------------------------------------
[自检] 全部通过 ✔  (数据完整, 无抽样, 无 base64 内嵌)
============================================================
[产出] C:\Users\67972\projects\short-drama-training\training_panel.html
[产出] HTML 大小    : 108013 bytes (105.5 KB)
[产出] HTML < 5MB ✔ (图片走本地相对路径, 未内嵌)
```

生成器内建 7 组断言（数据长度 / thumb 数 / img 总数 / 文件名齐全 / prompt 未截断 / 无 base64 / 相对路径可解析），任一不满足直接 `AssertionError` 构建失败。

### 3.2 独立 grep 校验产物（不信生成器自述，直接查文件）

```
thumb <img> 数:          54
全部 <img 标签数:        56      （54 缩略图 + 2 参考图）
唯一 wXX_Y.png 文件名数: 54
分组 group 数:           27
三态开关组数:            54
base64 内嵌:             0
{{ / }} 残留:            0 / 0   （format 转义正确）
```

### 3.3 内联数据深度校验

```
内联 ITEMS 长度      = 54
唯一 file 数         = 54
写法号覆盖           = 1 - 27 共 27 个 连续
每写法号张数分布     = {2: 27}      （27 个写法号各 2 张，均匀无缺）
prompt 为空的条目    = 0
url 为空的条目       = 0
最短 prompt 长度     = 212
最长 prompt 长度     = 382
prompt 含省略号(疑截断) = 0
rel_path 解析失败    = 0
参考图 = ['01_配方训练/角色参考图/charA_front.png', '01_配方训练/角色参考图/charA_side.png']
```

### 3.4 JS 语法校验

```
$ node --check <提取的内联 script>
JS 语法校验通过 ✔   (JS 长度 32,736 字符)
```

### 3.5 无头功能测试（`node scripts/test_panel_logic.js`）

用 Node `vm` + 最小 DOM/localStorage/Blob stub 真实执行面板内联 JS，**30 条断言全 PASS，退出码 0**：

| 组 | 覆盖点 | 结果 |
|---|---|---|
| [1] 数据与 DOM 索引 | ITEMS=54 / card=54 / group=27 / CARD_MAP=54 / 唯一 file=54 | 5/5 PASS |
| [2] 初始统计 | 总数 54、待定 54、已采纳 0、采纳率 0% | 4/4 PASS |
| [3] 三态切换+持久化 | 切 adopt→状态/高亮/角标「已采纳」/统计+1/localStorage 落盘；再切 reject→旧高亮移除 | 8/8 PASS |
| [4] 批量 | 全选采纳→54/0/100%，全部 54 卡均高亮 | 4/4 PASS |
| [5] 导出 | JSON total/records/adopted=54、prompt 完整(最短 212)、url+rel_path 齐全、提示含「04_采纳区」；CSV 带 BOM、55 行(表头+54)、表头正确 | 9/9 PASS |
| [6] 筛选 | 状态=已采纳→可见 1；写法号=1→可见 2；复位→可见 54 | 3/3 PASS |
| [7] 刷新不丢 | localStorage 落盘 54 条，w01_1.png=adopt | 2/2 PASS |

```
====================================================
全部断言通过 ✔  (54 张全量, 三态/持久化/导出/筛选/批量 均正常)
====================================================
```

> 测试过程中修掉的 2 个问题均为**测试脚手架自身缺陷**、非产品缺陷：① DOM stub 的 `.` 前缀分支抢先匹配导致后代选择器 `.switch button` 失效 → 改为组合选择器优先；② stub 未把 `textContent` 强制转字符串（真实 DOM 会转）→ 加 getter/setter。产品代码未因此改动。

### 3.6 AC 逐条对照

| AC | 要求 | 落地 | 证据 |
|---|---|---|---|
| 1.1 | 读 CSV 全行 + 扫 PNG + 参考图，inline 无外部请求 | ✅ | 54 行/54 PNG/2 参考图；无 `<link>`/外部 `<script>`/CDN，CSS+JS 全内联 |
| 1.2 | **全部 54 张**，按写法号 1–27 分组 | ✅ | thumb `<img>`=54，group=27，写法号连续 1–27 各 2 张 |
| 1.3 | 缩略图+写法号+**完整 prompt**+url 原文 | ✅ | 54 卡齐全；prompt 未截断 54/54，最短 212/最长 382 字符 |
| 1.4 | 三态开关，可切换即时高亮 | ✅ | 测试组[3] 8 条 PASS，三色边框+角标+按钮高亮 |
| 1.5 | localStorage 持久化 + 导出 JSON/CSV（日期名，提示存 04_采纳区） | ✅ | 测试组[5][7]；CSV 带 BOM 防乱码 |
| 1.6 | 按写法号 / 按状态筛选 | ✅ | 测试组[6] 3 条 PASS，空组自动隐藏 |
| 1.7 | 全选采纳 / 全部清除 | ✅ | 测试组[4] 4 条 PASS，带 confirm 二次确认 |
| 1.8 | 统计条实时更新 | ✅ | 总数/已采纳/不采纳/待定/采纳率 5 格，每次操作后刷新 |
| 1.9 | 角色参考图区（本地相对路径） | ✅ | charA_front + charA_side，`class="ref-img"`×2 |
| 1.10 | 顶部阶段说明 + 采纳门槛 | ✅ | 「三闸并行」：2–3 新场景稳定 / 2.5-flash 均分 ≥90 / 老板抽验 |

---

## 四、视觉样片

已在预览器中打开产物确认渲染正常。视觉描述：

- **整体**：深色主题（背景 `#0f1115`，卡片 `#1e222b`，主色 `#4c8dff`），中文字体栈 `Microsoft YaHei`，减少长时间逐张审阅的视觉疲劳。
- **顶部 hero**：渐变底，标题「训练线采纳面板 · batch-001（共 54 张，全量显示）」，下方灰字阶段说明，再下方带边框的门槛卡（三闸，关键词蓝色高亮）。
- **工具条**：`position: sticky; top:0`，向下滚动时始终悬停可见 —— 逐张审 54 张时统计与筛选不脱手。左侧 5 个统计格（已采纳绿 / 不采纳红 / 采纳率蓝），右侧筛选下拉 + 批量 + 导出按钮。
- **参考图区**：两张 200×200 `contain` 卡片并排，作为角色一致性比对基准，位于图卡区上方便于对照。
- **图卡网格**：`repeat(auto-fill, minmax(300px,1fr))` 自适应列数，宽屏多列窄屏回落单列。每组前有蓝色左边框的「写法号 N（2 张）」标题。
- **单卡**：260px 高缩略图（`contain` 不裁切）；左上黑色半透明「写法 N」角标，右上状态角标（灰待定/绿已采纳/红不采纳）；下方文件名、深色 prompt 框（可内部滚动看全文）、蓝色 url 链接、三态按钮组。
- **状态反馈**：采纳卡整体绿边框 + 内发光，不采纳红边框，扫一眼即知全局进度。

---

## 五、git 提交

| 仓库 | 状态 | 说明 |
|---|---|---|
| `C:\Users\67972\projects\short-drama-training` | **无 git 仓库** | `git rev-parse` 返回 `fatal: not a git repository`，且无父级仓库。按任务约定「若无 git 仓库则跳过 git 仅落地文件」，故生成器/HTML/测试脚本仅落盘，未提交。如需纳入版本管理，建议 `git init` 并把 `out/*.png`（194MB）与 `training_panel.html` 一并加入 `.gitignore`（产物可由生成器一键重建，不必入库）。 |
| `C:\Users\67972\WorkBuddy\workbuddy` | 已提交 | 本 `design.md`，hash 见回报。 |

---

## 六、待 QA 关注点（研发主动提示）

1. **file:// 真机验收**：无头测试无法覆盖真实图片解码。请双击 `training_panel.html`，确认 54 张缩略图**全部真实显示**（非碎图/占位）。中文路径 + 单张 3–4.4MB 共 194MB，首屏已用 `loading="lazy"` 延迟加载，滚动时应逐步出图。
2. **HTML 与图片的相对位置绑定**：`training_panel.html` 必须留在训练项目根，移动到别处相对路径即失效（这是「不内嵌」的固有代价）。
3. **localStorage 作用域**：以 `file://` 协议 + 浏览器 profile 为界。换浏览器/无痕模式/清缓存会丢标记 —— 请提醒老板审完及时导出存 `04_采纳区/`。
4. **`04_采纳区/` 未写入**：浏览器安全模型下网页无法直写本地目录，导出走浏览器下载，需老板手动移入。台账落盘自动化如有需要，属后续任务。
