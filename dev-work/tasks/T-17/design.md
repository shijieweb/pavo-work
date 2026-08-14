# design · T-17 训练面板顶部「实验目的说明」块

> 模板来源：`dev-work/templates/TEMPLATE_DESIGN.md`。开发填写，推「待验证」时一并交付。
> 铁律：无输出 = 未测 = 不通过。以下每节均为真实内容。

---

## 一、实现方案

### 1.1 思路与关键改动点

面板由生成器 `build_training_panel.py` 单一产出（单源真理）。HTML 由三段拼接：

- `HTML_HEAD`：`<head>` + 全部 CSS（含 `:root` 暗色变量、`.rule-note` / `.gate` 等卡片样式）。
- `HTML_BODY`：`<body>` 内容，其中 `header.hero` 内依次渲染 `.stage-note` → `.gate` → `.rule-note`。
- `HTML_SCRIPT`：内联 JS（lightbox / 采纳状态 / 导出等，本次完全未动）。

本次改动**只落在生成器**，重跑即复现，杜绝「手改 HTML 下次重生成丢失」的已知坑：

- **改动 A（样式）**：在 `HTML_HEAD` 的 `<style>` 中、`.rule-note` 样式之后新增 `.exp-note` 暗色卡片类（沿用面板 `--accent` 蓝、`--dual` 等变量与 `.rule-note` 的 padding/圆角配色），保证视觉与既有卡片一致且一眼可见。
- **改动 B（内容）**：在 `HTML_BODY` 的 `header.hero` 内、`.rule-note` 的 `</div>` 之后、`</header>` 之前，新增 `.exp-note` 说明块，按 PRD 指定的「一句话目的 / 为什么 2 张图 / 4 个目的」中文结构渲染为标题 + 段落 + `<ul>` + `<ol>`。

### 1.2 与现有逻辑的兼容处理（不变量）

- 未改动 `main()` 调用约定、未改动任何生成/渲染逻辑、未改动导出/统计/持久化。
- 说明块为**纯静态文本**，不含任何 `<img>`、不内嵌 `base64`、不含 `data-role="thumb"`、不含字符串「同一个齐肩黑发」——因此 T-16 计数锚点（54 图 / 54 中文锚点 / 27 写法号 / `<img>`=56）全部保持。
- 说明块位置在 `header.hero` 内、`.rule-note` 之后，不挤占 `.card` / `.group` 的 DOM 与 JS 选择器，已验证 T-16 全部控件（lightbox / 双图优 / 主图 / 备选 / 弃 / 导出 / 筛选 / 持久化）不受影响。
- 代码注释特意写成「不引入 img 标签 / base64 内嵌 / 缩略图锚点」，避免注释里出现 `<img` 或 `data-role="thumb"` 字面量——否则会被 PRD 指定的 grep 计数脚本误判为破坏了锚点（已踩坑并修正，见 §3.2）。

---

## 二、接口契约

本次为纯静态 HTML 内容新增，无新增函数 / 模块 / 外部接口。

| 项 | 说明 |
|---|---|
| 改动位置 | `build_training_panel.py` 的 `HTML_HEAD`（CSS）+ `HTML_BODY`（说明块 HTML 字面量） |
| 输入字段 | 无（内容硬编码为中文说明，不读 CSV / 不出图） |
| 输出字段 | 重生成的 `training_panel.html` 含唯一 `class="exp-note"` 块 |
| 下游消费方 | 浏览器静态渲染（人工阅读）；不改任何 JS 消费链 |

---

## 三、自测证据（铁律：无输出 = 未测 = 不通过）

### 3.1 改动文件清单

> 训练项目**无 git**（PRD 明确），不 commit；以下为文件级改动清单 + 新增代码片段作为证据（落盘仅 `build_training_panel.py` + `training_panel.html`，未新增训练项目内文件）。

**改动 A — `HTML_HEAD`（CSS，插入于 `.rule-note b {…}` 之后、`.toolbar {` 之前）：**

```css
  /* ---- T-17 实验目的说明块 (纯静态文本卡片, 沿用暗色主题, 不引入 img 标签 / base64 内嵌) ---- */
  .exp-note {
    margin-top: 10px; padding: 12px 16px; background: rgba(76,141,255,.08);
    border: 1px solid rgba(76,141,255,.35); border-radius: 8px;
    font-size: 13px; max-width: 1100px; color: #cfe0ff;
  }
  .exp-note .exp-title { color: var(--accent); font-size: 14px; font-weight: 700; margin-bottom: 6px; }
  .exp-note b { color: #fff; }
  .exp-note ul, .exp-note ol { margin: 6px 0 6px 20px; padding: 0; }
  .exp-note li { margin: 3px 0; }
```

**改动 B — `HTML_BODY`（插入于 `.rule-note` 的 `</div>` 之后、`</header>` 之前）：**

```html
  <!-- T-17 实验目的说明块: 纯静态文本, 不引入 img 标签 / base64 内嵌 / 缩略图锚点, 不破坏 T-16 计数锚点 (54 图/54 中文锚点/27 写法号) -->
  <div class="exp-note">
    <div class="exp-title">🧪 这批图在测什么？（batch-001 实验说明）</div>
    <div class="exp-purpose"><b>一句话目的：</b>固定同一女主（底图锁脸）+ 同一场景（推咖啡馆门），<b>只换「描述写法」</b>，看 AGNES 认哪套写法、出图最稳最好。</div>
    <div class="exp-why"><b>为什么每写法有 2 张图、提示词看着一样？</b>
      <ul> …（同 §3.4 片段）… </ul>
    </div>
    <div class="exp-goals"><b>这批测试 4 个目的：</b>
      <ol> …（同 §3.4 片段）… </ol>
    </div>
  </div>
```

### 3.2 本机跑测试的真实命令 + stdout

**重生成命令**（开发手测 + 生成器自带 T-16 自检）：

```
cd C:/Users/67972/projects/short-drama-training
python build_training_panel.py
```

生成器自带自检关键输出（断言全过）：

```
[信息] PNG 文件数   : 54
[信息] 参考图数量   : 2 -> ['charA_front.png', 'charA_side.png']
[信息] 写法号分组数 : 27
  缩略图 img.thumb[data-role]   = 54 (期望 54)
  参考图 class=ref-img          = 2 (期望 2)
  HTML <img 标签总数            = 56 (期望 56)
  唯一 wXX_Y.png 文件名         = 54 (期望 54)
  base64 内嵌图片出现次数       = 0 (必须为 0)
  中文锚点「同一个齐肩黑发」出现  = 54 (期望 54)
  data-writing 去重             = 27 (期望 27)
  lightbox 容器 id="lightbox"    = True (必须 True)
  ……（其余控件 27/54 计数全部符合预期）……
[自检] 全部通过 ✔  (54 图全量 / 中英齐备 / 无 base64 / T-16 控件就位)
[产出] training_panel.html
[产出] HTML < 5MB ✔ (图片走本地相对路径, 未内嵌)
```

**PRD 指定计数复核脚本**（真实输出，逐字贴）：

```
size= 166302
<img            = 56
data-role=thumb = 54
unique wXX_Y    = 54
base64 count    = 0
zh 同一个齐肩黑发 = 54
data-writing uniq= 27
exp-note 存在    = True
这批图在测什么   = True
lightbox/双图优/主图/备选/弃 均在 = True
```

> 全部符合 PRD 期望（`<img>`=56、`data-role=thumb`=54、唯一图 54、base64=0、中文锚点 54、写法号 27、`exp-note` 与「这批图在测什么」均存在、lightbox/双图优/主图/备选/弃 均在）。
> 过程中曾因注释含字面量 `<img` 与 `data-role="thumb"` 导致计数虚高（58 / 55），已改为「img 标签 / 缩略图锚点」措辞后复测通过。

### 3.3 关键运行日志

- 生成器退出码 `Exit Code: 0`，`Stderr: (empty)`，HTML 大小 `166302 bytes (162.4 KB)`，`HTML < 5MB ✔`。
- 复核脚本退出码 `Exit Code: 0`，无异常。

### 3.4 可真跑的启动 / 调用命令

任何人照抄即可复现：

```bat
cd /d C:\Users\67972\projects\short-drama-training
python build_training_panel.py
python "C:\Users\67972\WorkBuddy\workbuddy\dev-work\tasks\T-17\_verify.py"
```

> 注：`_verify.py` 为本任务验证辅助脚本，放在 `dev-work/tasks/T-17/`（**非训练项目目录**），不违反「训练项目只落盘 build_training_panel.py + training_panel.html」。

---

## 四、提测说明（测试怎么接）

- **测试入口**：直接打开 `C:\Users\67972\projects\short-drama-training\training_panel.html`（双击即开，无外部请求），肉眼核对顶部 `header.hero` 内 `.exp-note` 卡片。
- **待测范围**：
  - AC-1.1：顶部存在唯一 `class="exp-note"` 块，标题含「这批图在测什么」。
  - AC-1.2：块内含「为什么每写法有 2 张图、提示词看着一样」解释（唯一变量=写法号；同写法内 prompt 相同仅变种子；故意测跨种子一致性）。
  - AC-1.3：列出 4 个测试目的（黄金配方 / 跨种子稳定性 / 反例对照 w2·3·12 / 沉淀首尾帧描述模板 v1）。
  - AC-1.4：全中文、无英文术语堆砌。
  - AC-1.5：跑 §3.2 的复核脚本，9 项计数全部符合预期（铁律不被破坏）。
  - AC-1.6：确认改动在生成器内——可二次 `python build_training_panel.py` 重生成，说明块仍在。
  - AC-1.7：点开任意图放大（lightbox）、切中英文对照、标记双图优 / 主图 / 备选 / 弃、导出 JSON/CSV、刷新后 localStorage 持久化均正常。
- **已知限制**：无。本次为纯静态内容新增，覆盖全部验收项。

---

## 五、文档回写

- [x] `design.md` 已填（本文件）
- [x] 改动落在生成器 `build_training_panel.py`（单源真理），重生成可复现
- [x] `training_panel.html` 已重生成，含 `.exp-note` 说明块
- [ ] 任务卡 AC 进度：由主理人更新到 `current_state.md`（开发无 done 权）
- [ ] 其他四文档：测试写 `test.md`、验收写 `acceptance.md`（开发不越权）

---

## 附：说明块 HTML 片段摘录（重生成后实际落盘内容）

```html
  <!-- T-17 实验目的说明块: 纯静态文本, 不引入 img 标签 / base64 内嵌 / 缩略图锚点, 不破坏 T-16 计数锚点 (54 图/54 中文锚点/27 写法号) -->
  <div class="exp-note">
    <div class="exp-title">🧪 这批图在测什么？（batch-001 实验说明）</div>
    <div class="exp-purpose"><b>一句话目的：</b>固定同一女主（底图锁脸）+ 同一场景（推咖啡馆门），<b>只换「描述写法」</b>，看 AGNES 认哪套写法、出图最稳最好。</div>
    <div class="exp-why"><b>为什么每写法有 2 张图、提示词看着一样？</b>
      <ul>
        <li>实验<b>唯一变量</b> = 写法号（w01~w27）。每种写法 = 在<b>同一基础场景</b>上追加不同描述词（风格 / 景别 / 光影 / 构图）。</li>
        <li>同一写法号内的 2 张图，提示词<b>完全相同</b>，只变了模型随机种子——这是<b>故意的</b>：用「同一写法跑 2 次」测这种配方稳不稳（<b>跨种子一致性</b>）。</li>
        <li>两张都好 → 写法稳，可「<b>双图优</b>」采纳；1 张好 1 张崩 → 写法不稳，只收好的当<b>主图</b>；2 张都崩 → 这写法废，整组不采纳。</li>
        <li>27 个写法号<b>之间</b>的提示词才不一样（各自追加的词不同）。</li>
      </ul>
    </div>
    <div class="exp-goals"><b>这批测试 4 个目的：</b>
      <ol>
        <li>找「AGNES 认哪套写法」的<b>黄金配方</b>（哪些描述词让锁脸角色既保身份一致、又出好图）；</li>
        <li>验证配方<b>跨种子稳定性</b>（每写法 2 张即为此）；</li>
        <li><b>反例对照</b>：写法 2/3 故意「缺风格词」、写法 12 故意「冷色与暖光冲突」，用来界定好配方边界；</li>
        <li>最终产出「<b>首尾帧描述模板 v1 + 好坏图样例</b>」，沉淀回主项目生成链，让量产稳定出角色一致的好图。</li>
      </ol>
    </div>
  </div>
```
