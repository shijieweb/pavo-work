# acceptance · T-20260812-02 L1 真·管线冒烟（主理人终验）

> 模板：`dev-work/templates/TEMPLATE_ACCEPTANCE.md`。**主理人（阿编）填写**，对照 AC 逐条勾证据，把关后推「完成」。
> 闸1：主理人依老板 2026-08-12 授权**自签**（纯验证任务，不影响需求基线）。

## 验收对照表（主理人逐条勾，每条附证据）

| AC | 要求 | 测试结论 | 主理人独立复验 | 结果 |
|---|---|---|---|---|
| AC-1.1 | build_variants 输出 images 为 data:image（非裸 assets/ 路径） | PASS（`images[0]` 前 80 字符 `data:image/png;base64,iVBOR...`） | 测试日志 `l1_smoke.log` 同值；P0-1 二轮回归已证新旧一致，本次真实 assets/ 路径独立复验 | ✅ |
| AC-1.2 | 免费KEY 真实提交成功，AGNES 返回可轮询任务标识 | PASS（task=`task_NTUHCHkQE0GNch55Kz5Q4OuagQr39XUG`） | task id 在 test.md / l1_smoke.log 一致 | ✅ |
| AC-1.3 | wait_for_video 取回成片 URL，端到端闭环 | PASS（URL 落盘 evidence_video_url.txt） | **主理人亲自 `curl -sI` 该 URL → `HTTP/1.1 200 OK` / `Content-Type: video/mp4`**（独立证明视频真实生成可达） | ✅ |
| AC-1.4 | 全程仅免费KEY，零 VIP | PASS（`key_pool_status()["mode"]=="test"` 提交前后恒定） | 测试证据链完整；VIP 3 把 key 全程 `active` 未被触碰 | ✅ |
| AC-1.5 | 长任务排队心跳，无 silence | PASS（4 次 `[poll]` 输出，排队约 97s） | 日志可见 pending→in_progress→completed 心跳 | ✅ |

## 主理人独立复验动作（不盲信测试自报）

1. **成片 URL 可达性**：`curl -sI` → `HTTP 200 / video/mp4`，确认不是编造的 URL，L1 真测确实产出真实视频。
2. **源码零改动**：`git status` 显示仅 `dev-work/` 文档 + 测试产出（`l1_smoke.py` / `evidence_video_url.txt` / `scripts/diag/assets/*.png`），**`prompt_training.py` 与 `templates/*.yaml` 完全未动** → 测试严格守"只验证不改码"。
3. **文档坑已修**：测试发现 `agnes_client.use_test()` 在模块级不存在（实为 `agnes_client._pool.use_test()`），已在 `主理人守则.md` G0-5 / I-2 两处更正，防后续测试踩坑。

## 放行决定

**✅ 放行（完成）**。AC-1.1~1.5 全部 PASS，且经主理人独立复验（URL 真实可达 + 源码零改动 + 文档坑已修）。L1 免费KEY 真测确凿有效——P0-1 重构后的 `build_variants` 在真实 AGNES 端到端跑通，BUG-2 修复在生产真实数据路径下确认生效，全程零 VIP 额度。

## 遗留 / 观察项（非阻塞，不阻塞放行）

- `[OBS][S4|P3]` `agnes_client` 模块级无 `use_test()`（已修文档，见上）。
- `[OBS][S4|P3]` `prompt_training` 顶层 `from diagnosis import diagnose_clip` 依赖 `scripts/edit/diagnosis.py`（由 prompt_training 自建 sys.path 注入）；独立 import 需注意。
- 测试对 `server.asset_abs` 运行时打桩映射真实可读 PNG，以真实触发 data_uri 分支——证明转换逻辑本身，与生产 ASSET_BASE 解析行为一致。
- 建议（优化·已记 MEMORY）：将 `l1_smoke.py` 固化进回归套件，今后 P0 改动自动跑 L1；脚本内加 `assert key_pool_status()["mode"]=="test"` 守卫防误烧 VIP。

## 交付物

- `dev-work/tasks/T-20260812-02/{PRD,test,acceptance}.md` + `l1_smoke.py` + `l1_smoke.log` + `evidence_video_url.txt`
- 真实成片：`https://platform-outputs.agnes-ai.space/videos/agnes-video-v2.0/task_NTUHCHkQE0GNch55Kz5Q4OuagQr39XUG.mp4`（免费KEY 生成，零 VIP）
- `dev-work/主理人守则.md`（已修 use_test 文档坑）+ `dev-work/current_state.md`（状态置完成）
