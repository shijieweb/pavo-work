# PRD · T-15 构建训练线采纳面板 HTML（显示全量测试数据 + 采纳开关）

> **需求基线闸：老板已签 ☑**
> 依据：2026-08-14 22:29 指令「把训练线整理需求做一个新的html训练面板给我让我可以在界面里面选择是否采纳」+「功能完整度所有测试数据都要显示否则影响我的判断」。属 boss 显式授权。
> 白名单核验：新增功能（面板+开关+持久化），但 boss 已授权；只读训练 out/ 数据（不改动生产管线）；采纳记录写回 04_采纳区（老板自有台账，预期行为）。不触碰接口/鉴权/AGNES 网关。
> 任务类型：A 类团队调度（前端构建 + QA 验收）。

## 数据源（真实路径，已读盘确认）
- `C:\Users\67972\projects\short-drama-training\01_配方训练\实验批次\batch-001\out\`
  - `prompts.csv`：列 = `file,写法号,prompt,url`（实测 54 张图数据，命名 `wXX_Y.png`，写法号 1–27 各 2 张）
  - 54 张 `*.png` 实测产物
- 角色参考图目录：`C:\Users\67972\projects\short-drama-training\01_配方训练\角色参考图\`

## 产物
- **生成器**：`build_training_panel.py`（读取 CSV + 扫描 PNG + 角色参考图 → 输出 HTML）
- **面板**：自包含 `training_panel.html`（**所有数据 inline 进 `<script>`，file:// 双击即可看，离线可用**）
- 落点建议：`C:\Users\67972\projects\short-drama-training\training_panel.html`（贴近数据，老板双击即开）

## 功能与验收锚点（AC）
- **AC-1.1** 生成器 `build_training_panel.py` 读取 `prompts.csv` 全部行 + 扫描 `out/*.png` + 角色参考图，输出 `training_panel.html`，数据 inline 进 `<script>`（无外部请求依赖）。
- **AC-1.2** 面板**显示全部 54 张图（一张不漏）**，按写法号分组展示。
- **AC-1.3** 每张图卡含：① 缩略图（优先 `url` 远程图，加载失败兜底本地 `out/` 路径或占位说明）② 写法号 ③ **完整 prompt 全文**（不可截断）④ `url` 原文。
- **AC-1.4** 每张图卡有「采纳 / 不采纳」双态开关，状态可切换并即时高亮（已采纳绿、不采纳红、待定灰）。
- **AC-1.5** 持久化：采纳结果存 `localStorage`（刷新不丢）+ 可「导出采纳记录」为 `.json`/`.csv`；导出文件写入 `04_采纳区/采纳记录`（供台账）。
- **AC-1.6** 筛选：按写法号 / 按采纳状态（全部 / 已采纳 / 未采纳 / 待定）。
- **AC-1.7** 批量：一键「全选采纳」/「全部清除」。
- **AC-1.8** 统计条：总图数 / 已采纳 / 未采纳 / 采纳率，随操作实时更新。
- **AC-1.9** 角色参考图区：展示角色参考图，作为一致性比对基准（老板据此判断人物是否一致）。
- **AC-1.10** 面板顶部展示训练线阶段说明 + 采纳门槛（2-3 新场景稳定 + 裁判 2.5-flash 均分 90+ + 老板抽验），给老板判断上下文。

## 边界禁止项
- 不改动 `batch-001/out/` 原始数据（只读）。
- 不调用 AGNES 生成（纯前端 + 静态读取）。
- 数据必须**全量显示**——任何"抽样/只显示前 N 张"都违反老板铁律，视为不通过。

## 产出路径
- `C:\Users\67972\projects\short-drama-training\build_training_panel.py`
- `C:\Users\67972\projects\short-drama-training\training_panel.html`
- 四文档：`dev-work/tasks/T-15/{design,test,acceptance}.md`
