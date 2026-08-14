# PRD · T-14 团队执行 #2-4（G4 Hotfix标签 + P0-4跨seed一致性 + S4 YAML warning）

> **需求基线闸：老板已签 ☑**
> 依据：2026-08-14 22:29 对话指令「先把2-4 让团队干完」+「然后做训练面板」。属 boss 显式授权。
> 白名单核验：#2 为看板新增 `is_hotfix` 字段+样式（新增功能，但 boss 已授权范围内）；#3 触生成逻辑（seed）→ 测试必 L1 免费KEY；#4 为 loader 加 warning（不改对外行为）。三件均在老板指令范围内，不触碰接口/鉴权/AGNES 网关。
> 任务类型：A 类团队调度（写码 + QA 验收）。

## 子任务 A · #2 G4 Hotfix 热修标签
**待改文件**：`shared_board/index.html`（卡片渲染）、`shared_board/server.py`（数据读写）、`shared_board/board.db`（数据模型）
**需求**：看板卡片支持"热修/Hotfix"标记，视觉上红左边框 + 🚨 角标（参照 `dev-work/reference_kanban.html` L204 `if (card.isHotfix) cls.push('hotfix')`、L225 `hotfixHtml` 的已有实现风格，移植到我们的字段模型）。
**验收锚点（AC）**：
- AC-A.1 数据模型新增 `is_hotfix` 布尔字段（默认 false）；旧卡片（无此字段）读取不报错、默认 false。
- AC-A.2 `index.html` 卡片渲染：`is_hotfix=true` 时左侧红边框 + 🚨 角标，风格与 reference_kanban 一致。
- AC-A.3 现有字段（title/status/priority/author/updated/parent_id/detail/id）渲染不受影响。
- AC-A.4 `node --check` 语法 OK；浏览器可加载、卡片可见（QA 截图核产）。

## 子任务 B · #3 P0-4 跨 seed 一致性
**待改文件**：`short_drama_workflow/scripts/diag/prompt_training.py` + `templates/*.yaml`
**需求**：在 P0-1 已闭环的 YAML 模板机制（build_variants）上做"跨 seed 一致性"校验。
**验收锚点（AC）**：
- AC-B.1 工程师先读 `prompt_training.py` + `templates/*.yaml` 明确 P0-4 具体定义（跨 seed 指什么、一致性判据），在 design.md 报告定义后再实现（不盲写）。
- AC-B.2 实现一致性校验：同一写法号/writing 在跨 seed 生成时，角色关键属性（人物描述 / seed 锁定 / 关键帧）保持一致，输出可观测的一致性报告（哪些一致、哪些漂移）。
- AC-B.3 若实现需调用 AGNES 生成 → 测试必 L1 免费KEY（`AGNES_TEST_API_KEY`），绝不烧 VIP。
- AC-B.4 提供可重跑命令 + stdout（无输出=未测=不通过）。

## 子任务 C · #4 S4 YAML 缺字段 warning
**待改文件**：`short_drama_workflow/scripts/diag/prompt_training.py`（YAML 加载器）
**需求**：加载器在 YAML 缺 `variants`/字段时，当前静默返回 `{}` / 空列表，改为 `logging.warning` 明确提示缺哪个字段，便于排错。
**验收锚点（AC）**：
- AC-C.1 缺 `variants` 或关键字段时，加载器 emit `logging.warning`（写明缺哪个字段），不再静默返回空。
- AC-C.2 有字段时正常加载行为不变（回归不受损）。
- AC-C.3 提供可重跑命令 + stdout：构造一个缺字段 YAML 触发 warning 作为证据。

## 边界禁止项
- 禁烧 VIP（测试一律 `AGNES_TEST_API_KEY`）。
- 禁改无关文件（只动上述指定文件）。
- 禁改 AGNES 网关 / 鉴权 / 接口。
- 动源码前先 `git commit before:`（G0-9）。

## 产出路径
- `shared_board/index.html` / `server.py`（#2）
- `short_drama_workflow/scripts/diag/prompt_training.py`（#3/#4）
- 四文档：`dev-work/tasks/T-14/{design,test,acceptance}.md`
