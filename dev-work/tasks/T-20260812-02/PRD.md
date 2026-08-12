# PRD · T-20260812-02 L1 真·管线冒烟（免费KEY 验证 P0-1 重构端到端）

> 模板：`dev-work/templates/TEMPLATE_PRD.md`。阿编填写，闸1 老板签。
> 背景：P0-1 把 `build_variants` 重构为 YAML 加载器，但**当时只做了 dry-run（L0）**，未真跑 AGNES。老板提醒：免费KEY（`AGNES_TEST_API_KEY`）**无限额度、仅排队**，真测必须用上。本任务即补这趟真测，验证重构没在真实管线上埋雷。

- **需求基线闸：主理人自签 ☑（老板 2026-08-12 授权：纯验证任务主理人可自签闸1，不需老板逐条认 AC）**（未签 → 开发卡 blocked，阿编不派活）
- **目标**：用免费KEY 真实跑一遍「`build_variants`（P0-1 重构后）→ `_submit_video` → `wait_for_video`」端到端，验证 keyframes/data_uri/prompt/negative/seed 真传到 AGNES 且返回可拼；全程零 VIP 额度。
- **关联**：上游 `T-20260812-01`（P0-1 模板 YAML 化，已完成）；依赖其 `templates/*.yaml` + 重构后的 `build_variants`。

---

## 一、功能清单（要做哪些功能点）

- F1 用免费KEY 生成/准备 1 张关键帧源图（参考图或本地测试 PNG 经 data_uri）。
- F2 调重构后 `build_variants`（camera_move_v2）产出变体，断言 `images` 含 data_uri（非裸路径，验证 P0-1 BUG-2 修复在生产真实数据下成立）。
- F3 调 `agnes_client._submit_video` 真实提交，断言 AGNES 接受 payload（返回 job / 任务标识）。
- F4 `wait_for_video` 拿到结果（视频 url / 本地路径），可被后续拼接待用 → 端到端闭环。
- F5 排队等待期心跳（每 10 分钟）+ 阿编对老板报平安，不闷头。

---

## 二、需求清单（验收标准 AC 锚点）

- [ ] AC-1.1 `build_variants` 输出的 `images` 中关键帧为 `data:image/...;base64,...`（非裸 `assets/` 路径），证明 P0-1 BUG-2 修复在真实管线成立。
- [ ] AC-1.2 `_submit_video` 用免费KEY 真实提交成功，AGNES 返回可轮询的任务标识（job id），即 payload（keyframes/prompt/negative/seed）被接受。
- [ ] AC-1.3 `wait_for_video` 成功取回结果（视频 url 或本地路径），端到端闭环达成。
- [ ] AC-1.4 全程仅用 `AGNES_TEST_API_KEY`，**零 VIP 额度消耗**（验证免费KEY 无限额度真可用，不占生产配额）。
- [ ] AC-1.5 长任务（排队）期间，测试按 §5 心跳回报、阿编对老板每分钟报平安，无 silence。

---

## 三、产出路径

- 新增：`dev-work/tasks/T-20260812-02/{design,test,acceptance}.md`（四文档）
- 改动：无源码改动（本任务只"消费" P0-1 产物做验证）；若发现 P0-1 真实管线 bug，按 `[BUG]` 提单，回 T-20260812-01 修复，不在此任务改码。
- 不动：`prompt_training.py` / `templates/*.yaml`（除非提单后另行闸2）。

---

## 四、边界与禁止项

- 不改：P0-1 已交付代码（发现 bug 走提单，不自行改）。
- 禁止：用 VIP KEY 烧生产额度（测试一律免费KEY）；禁止 silence（长任务必须心跳）。
- 已知坑（主理人提示）：
  1. 免费KEY 仅排队 → 视频生成可能数分钟，必须后台跑 + 心跳，禁止前台闷等。
  2. 真实 `assets/` 路径下 data_uri 转换是 P0-1 BUG-2 修复点，本任务 AC-1.1 即验证它。
  3. `wait_for_video` 需正确轮询；超时要有明确失败证据而非卡死。

---

## 五、闸1 签核（主理人自签 · 老板 2026-08-12 授权）

- 主理人确认验收标准（逐条）：☑ 已自签（纯验证任务，不影响需求基线，依授权自主推进）
- 备注：依老板授权"不影响需求的情况你可以自己做主"，本纯验证任务主理人自签闸1 并派测试用免费KEY 真跑，不烧 VIP。
