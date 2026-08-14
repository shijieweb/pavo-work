# PRD · T-16 训练面板三项优化（点击放大 / 中英对照 / 写法号层级采纳+双图处理）

> **需求基线闸：老板已签 ☑**
> 依据：2026-08-14 23:41 老板指令「需要优化：1 图片点击能放大；2 提示词需要有中文部分；3 如果两张都可以怎么办没给处理方案」。
> 白名单核验：仅改 `build_training_panel.py` + 重新生成 `training_panel.html`（同路径）；只读 `prompts_zh.csv`（新增，阿编已译）；不改 `out/` 原始数据、不调 AGNES。属老板显式授权优化。
> 任务类型：A 类团队调度（前端优化 + QA 验收）。

## 数据源（已落盘）
- `01_配方训练/实验批次/batch-001/out/prompts.csv`（英文，54 行）
- `01_配方训练/实验批次/batch-001/out/prompts_zh.csv`（**新增·阿编译**，54 行，列 `file,写法号,prompt_zh`，与英文 file 集合一致、0 空）
- 54 张 `out/wXX_Y.png` + 角色参考图（同 T-15）

## 产物（覆盖 T-15 同路径）
- 改 `build_training_panel.py`：读 `prompts_zh.csv` 合并进数据；新增 lightbox + 写法号层级采纳模型。
- 重新生成 `training_panel.html`（同路径 `C:\Users\67972\projects\short-drama-training\training_panel.html`），保留 T-15 所有能力。

## 功能与验收锚点（AC）
- **AC-1** 点击任意缩略图弹出 **lightbox 全尺寸大图**；点空白区域 / 按 ESC 关闭；lightbox 内同时显示该图**中英文 prompt**。
- **AC-2** 每张卡显示**中文 prompt**（取自 `prompts_zh.csv`，与英文原文上下对照），中文全文不截断；若某 file 缺中文则降级显示英文（不应发生，因 54 全有）。
- **AC-3** 采纳模型**上移到写法号层级**：每组（写法号 1–27）有 `不采纳 / 待定 / 采纳` 三态；组内每张图有 `主图 / 备选 / 弃` 三态。
- **AC-4「两张都可以」处理方案（老板点名缺口）**：
  - 一组要标「采纳」，必须 ≥1 张为主图或备选；
  - 若两张都标记为好（主图或备选）→ 组自动「采纳·双图优」，并**强制你点选 1 张「主图」**，另 1 张自动归「备选」（避免歧义）；
  - 导出时每组记录：组决策 + 主图文件名 + 备选文件名（若有）。
- **AC-5** 统计条新增：**写法号采纳数 / 双图优数**；保留 总图数 / 已采纳图 / 未采纳图 / 采纳率。
- **AC-6** localStorage 持久化「组状态 + 每张图状态」；导出 JSON/CSV 含组层级信息（写法号、组决策、主图、备选）。
- **AC-7** **铁律不变**：54 图仍全量显示（0 缺失 / 0 截断 / 0 base64 内嵌），不破坏 T-15 已验收项。
- **AC-8** 顶部阶段说明 + 角色参考图区 保留。

## 边界禁止项
- 不改 `out/` 原始数据（只读）；不调 AGNES。
- 不破坏 T-15 已验收能力（筛选/批量/导出/角色参考图/阶段说明）。
- 中文翻译为一次性数据文件，生成器只读合并，不在生成时调用翻译 API（保持离线自包含）。

## 产出路径
- `C:\Users\67972\projects\short-drama-training\build_training_panel.py`（改）
- `C:\Users\67972\projects\short-drama-training\training_panel.html`（重新生成）
- 四文档：`dev-work/tasks/T-16/{design,test,acceptance}.md`
