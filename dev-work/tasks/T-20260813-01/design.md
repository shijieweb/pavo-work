# design · T-20260813-01 l1_smoke 固化进回归套件

> 模板：`dev-work/templates/TEMPLATE_DESIGN.md`。**开发填写**（推「待验证」时交付）。
> 铁律：无输出 = 未测 = 不通过。

---

## 一、实现方案

- 新增独立回归守卫脚本 `short_drama_workflow/scripts/l1_smoke.py`，把「免费 KEY 真测（L1）」固化成单命令可跑的端到端冒烟：
  `build_variants` → `images_to_video(免费KEY)` → 轮询 → 取回成片 URL，打印 `PASS/FAIL + 成片 URL`。
- **入口守卫（PRD F2 / AC-1.2）**：在调用任何 `gen_video` 之前先确认 key-pool 处于 `test` 模式。
  实现为 `ensure_test_mode()`：读 `agnes_client.key_pool_status()["mode"]`；若非 `test` 则调用
  `agnes_client._pool.use_test()`（注意是 `_pool.use_test()`，不是不存在的模块级 `use_test()`）切免费 KEY；
  若没有免费 KEY（`use_test()` 返回 `False`）立即 `sys.exit(3)` 非零退出，绝不进入 VIP 分支；
  切回后仍 `assert mode=="test"` 做双重保险。提交前再 `assert mode=="test"` 一次。
- **真实 `assets/` 帧图（PRD F3 / 复刻 P0-1 BUG-2 的 data_uri 分支）**：脚本在自身 `assets/` 目录用
  标准库 `zlib` 写两张真实可读 PNG 帧图（`first.png`/`last.png`，零 Pillow 依赖），构造 shot
  `asset_frame_start="assets/first.png"` / `asset_frame_end="assets/last.png"`，运行时把 `server.asset_abs`
  打桩指向这两张本地真实 PNG（**不改任何源文件**，仅运行时替换返回值）。`build_variants` 据此走
  `content.startswith("assets/") → _datauri(server.asset_abs(...))` 分支，输出 `data:image/...` 关键帧，
  真正覆盖生产路径。
- **端到端真测（PRD F4）**：`import prompt_training as pt` → `pt.build_variants(shot, ref, "camera_move_v2")`
  取 `v0` 变体的 `images`(data URI 关键帧) + `prompt`，再 `agnes_client.images_to_video(images, prompt, ...)`
  （免费 KEY、仅排队，内置 `[poll]` 心跳每 `interval` 秒打印 status/progress），轮询取回成片 URL。
- **单命令（PRD F4）**：`python l1_smoke.py` 即可跑，参数（`--width/--height/--num-frames/--frame-rate/
  --timeout/--interval/--negative`）均有合理默认值；`argparse` 解析，无需手工拼。
- **自证可访问（AC-1.3）**：取到 URL 后做 HEAD/Range 探测，要求 HTTP 200/206 且 `Content-Type` 含 `video`，
  并打印 `curl` 复核用的 URL 落盘到 `l1_smoke.last_url.txt`。
- **红线遵守**：不改 `agnes_client.py`/`server.py`/`prompt_training.py` 任何既有逻辑，只 import 复用 +
  运行时打桩 `server.asset_abs`；全程 `mode=="test"`，零 VIP 额度消耗；不调用任何 VIP 路径。

---

## 二、接口契约

| 项 | 说明 |
|---|---|
| 函数签名 | `def ensure_test_mode() -> dict` |
| 输入字段 | 无（读 `agnes_client.key_pool_status()` 与 `agnes_client._pool.use_test()`） |
| 输出字段 | `dict`：key_pool_status 快照；非 test 且无法切免费 KEY 时 `sys.exit(3)` |
| 下游消费方 | `main()`：提交前必须返回 `mode=="test" 才继续` |

| 项 | 说明 |
|---|---|
| 函数签名 | `def main() -> None`（退出码：0=PASS / 1=FAIL 或异常 / 3=VIP 守卫中止） |
| 输入字段 | 命令行参数（均有默认）：`--width 448 --height 832 --num-frames 81 --frame-rate 24 --timeout 900 --interval 10 --negative <NEG_PROMPT>` |
| 输出字段 | stdout 打印 `✅ PASS \| 成片 URL: <url>` 或 `❌ FAIL ...`；并写 `l1_smoke.last_url.txt` |
| 下游消费方 | 回归/CI：据退出码与 stdout 判定；QA 用 `curl -sI <url>` 复核 `200 + video/mp4` |

- 复用的既有契约：`prompt_training.build_variants(shot, ref, "camera_move_v2") -> {name: {images, keyframes, prompt, ...}}`；
  `agnes_client.images_to_video(images, prompt, width, height, num_frames, frame_rate, negative_prompt, timeout, interval) -> url`；
  `agnes_client.key_pool_status()["mode"]`（"test"=免费KEY / "prod"=VIP）。

---

## 三、自测证据（铁律：无输出 = 未测 = 不通过）

### 3.1 改动文件清单（git diff --stat 5425fda..acfdc6f）
```
 short_drama_workflow/scripts/l1_smoke.py | 303 +++++++++++++++++++++++++++++++
 1 file changed, 303 insertions(+)
```
- 提交链（主理人核产确认，git log）：
  - `5425fda` before: T-20260813-01 l1_smoke
  - `ceb0d00` fix: HTML_PROTOTYPE 用 HERE 基准定位 server.py
  - `d590b06` fix: DIAG_DIR 用 HERE 基准定位 prompt_training
  - `7183432` fix: 桩 asset_abs 改 basename 鲁棒映射 + 自检
  - `acfdc6f` fix: 加载 server 后注册 sys.modules 使桩被 prompt_training 复用（关最后一道隐藏 bug）
- **红线核验**：`git diff --stat` 仅 `l1_smoke.py`（新增 303 行），**未碰 `agnes_client.py` / `server.py` / `prompt_training.py` 任何既有逻辑**（仅 import 复用 + 运行时打桩 `server.asset_abs`）。

### 3.2 本机跑测试的真实命令 + stdout

- 命令（主理人于 2026-08-13 02:12 在本会话可控后台实跑，task_id=V3gwmQ）：
  ```bash
  cd C:/Users/67972/WorkBuddy/workbuddy/short_drama_workflow/scripts && python l1_smoke.py
  ```
- 真实 stdout（完整，非研发自报）：
  ```
  == l1_smoke 开始: 2026-08-13 02:12:26 ==
  == 入口守卫通过: mode=test (免费KEY, 零 VIP) ==
  == 本地真实帧图: ...\scripts\assets\first.png , ...\scripts\assets\last.png ==
  == build_variants 变体: ['v0', 'v1', 'v4', 'v5'] ==
  == v0.images 数量: 2 ; 前 60 字符: data:image/png;base64,iVBORw0KGgo...
  ✅ AC-1.1 PASS: images 关键帧均为 data:image/...（走 data_uri 分支）
  == 提交中（免费KEY，仅排队，[poll] 为内置心跳）...
  [poll] task_BOikAsJFPLqTuYO95uO2YUqL71MvyzXb status=completed progress=100
  == 结束: 02:13:49 (耗时 82.7s) ==
  == 提交后 key_pool_status: {"total": 3, "active": 3, "bad": [], "switches": 1, "cooldown": [], "mode": "test", "has_test_key": true} ==
  ✅ PASS | 成片 URL: https://platform-outputs.agnes-ai.space/videos/agnes-video-v2.0/task_BOikAsJFPLqTuYO95uO2YUqL71MvyzXb.mp4
      探测: HTTP 200 , Content-Type: video/mp4
      全程 mode=test（免费KEY, 零 VIP 额度消耗）
  ```
- 退出码 `0`（PASS 分支）。运行期 `--- Logging error --- PermissionError ... server.log` 为 `server.py` 模块级 logging 与本机常驻 8777 服务竞争日志文件所致，**非致命、被 logging 内部吞掉**，不影响退出码与成片产出（已确认）。
> 注：本任务为真测（L1 免费KEY），允许真实提交 images_to_video（免费KEY 仅排队，属长任务）。

### 3.3 关键运行日志
- 运行日志：`short_drama_workflow/scripts/l1_smoke.run.log`
- 成片 URL 落盘：`short_drama_workflow/scripts/l1_smoke.last_url.txt`
- QA 复核命令：`curl -sI "$(cat short_drama_workflow/scripts/l1_smoke.last_url.txt)"` → 期望 `HTTP/1.1 200 OK`、`Content-Type: video/mp4`
- **主理人实跑状态（2026-08-13 02:12·task V3gwmQ）**：`l1_smoke.run.log` 已覆盖 01:54 失败版、写入成功输出；`l1_smoke.last_url.txt` 已生成（URL 见 §3.2）；`curl -sI` 复核 = `HTTP 200 + video/mp4`（见 §3.2 探测行）。全程 `mode=="test"`，零 VIP。

### 3.4 可真跑的启动 / 调用命令
```
cd short_drama_workflow/scripts && python l1_smoke.py
# 或带参数：python l1_smoke.py --num-frames 81 --timeout 900
```

---

## 四、提测说明（测试怎么接）

- 测试入口：`python l1_smoke.py`（单命令），退出码 0=PASS / 1=FAIL / 3=VIP 守卫中止。
- 待测范围：
  - AC-1.1：`build_variants` 输出的 `images` 关键帧均为 `data:image/...`（脚本内已 assert + 打印）。
  - AC-1.2：入口守卫——独立验证「构造 `mode!="test"`（如清空 `AGNES_TEST_API_KEY` 使 `use_test()` 返回 False）时脚本在 gen_video 前非零退出（exit 3），不烧额度」。
  - AC-1.3：成片 URL `curl -sI` → `200 + video/mp4`；且全程 `key_pool_status()["mode"]=="test"`（零 VIP）。
  - AC-1.4：单命令 `python l1_smoke.py` 即可执行（无需手工拼参数）。
- 已知限制：免费 KEY 仅排队，首次出片可能数分钟（长任务）；属非阻塞，脚本内置 `[poll]` 心跳续命。

---

## 五、文档回写

- [x] `design.md` 已填（本文件）
- [ ] 任务卡 AC 进度已更新到 `current_state.md`（待主理人/测试确认后回写）
- [ ] 其他四文档更新：P0 改动后跑 `l1_smoke` 的备注（建议在 current_state.md / 运行手册补一句，非强制）
