# PRD · T-20260813-01 l1_smoke 固化进回归套件

> 模板来源：`dev-work/templates/TEMPLATE_PRD.md`。阿编（主理人）填写。

- **需求基线闸：老板已签 ☑**（来源：2026-08-13 老板定"其他的按照计划开始把"；本任务属 A-1 闸1 自签白名单·纯验证类，老板 0812 授权主理人自决）
- **自签依据（G0-11）**：属「纯验证 / 固化测试」类 · 不改需求基线（不新增对外功能、不改 production 行为，仅新增独立回归守卫脚本）。
- **白名单核验（G0-11）**：未触碰 接口 / 数据 / 鉴权 / 生成逻辑 / 新增功能(生产侧) / 大额度。仅新增独立测试脚本 + assert 守卫。
- **目标**：把"免费 KEY 真测（L1）"固化成一个可重复运行的回归守卫脚本 `l1_smoke.py`，并在入口加 `assert key_pool_status()["mode"]=="test"` 守卫，杜绝今后误烧 VIP。
- **关联**：T-20260812-02（L1 免费KEY 真测收尾，提出固化建议）；current_state.md 阿编把关结论（2026-08-12 L1 真测）。

---

## 一、功能清单（要做哪些功能点，逐条）

- F1 新增 `l1_smoke.py`：端到端跑一次 L1 免费KEY 真测（build_variants → images_to_video → 轮询 → 取回成片），打印 PASS/FAIL + 成片 URL。
- F2 入口守卫：脚本开头 `assert key_pool_status()["mode"] == "test"`，非 test 模式（VIP）立即中止，绝不进入 gen_video。
- F3 用真实 `assets/` 帧图跑（复刻 P0-1 BUG-2 的 data_uri 分支），让 smoke 真正覆盖生产路径。
- F4 单命令可触发（`python l1_smoke.py`），便于今后 P0 改动后手动/CI 调用。

---

## 二、需求清单（验收标准 AC 锚点，开发/测试各持一份）

- [ ] AC-1.1 `l1_smoke.py` 存在且可端到端跑通：用免费KEY L1 真实出片，输出 PASS 且含可访问成片 URL（`curl -sI` → HTTP/1.1 200 OK、Content-Type: video/mp4）。
- [ ] AC-1.2 入口 `assert key_pool_status()["mode"]=="test"` 守卫生效：构造 `mode!="test"`（如 VIP）时脚本在调用 gen_video 前即中止（assertion / 显式 exit，非零退出），不烧额度。测试须独立验证该中止路径。
- [ ] AC-1.3 全程零 VIP 消耗：对比运行前后 VIP 额度无变化；或断言代码路径永不进入 VIP 分支。
- [ ] AC-1.4 单命令 `python l1_smoke.py` 即可执行（无需手工拼参数），便于固化进回归/CI。

> AC 写法要求：具体到"用什么命令/输入得到什么输出"，禁止"功能正常""无明显 bug"这类空话。

---

## 三、产出路径（改哪些文件/目录）

- 新增：`short_drama_workflow/scripts/l1_smoke.py`
- 不动：`agnes_client.py` / `server.py` / `prompt_training.py` 的逻辑（仅 import 复用）。
- 注册：在 current_state.md / 运行手册备注"P0 改动后跑 l1_smoke"即可（不强制改 CI）。

---

## 四、边界与禁止项

- 不改：production 行为、无关文件。
- 禁止：烧 VIP、改无关文件。
- L0 自测禁 `gen_video`；真测一律 L1 免费KEY（`agnes_client._pool.use_test()`，注意是 `_pool` 不是模块级 `use_test()`）。
- 已知坑（主理人提示，开发必须处理）：
  1. 函数名 `agnes_client._pool.use_test()`，不是 `agnes_client.use_test()`（会 AttributeError）。
  2. keyframe 提交用 `images_to_video(images, prompt, ...)`。
  3. 免费KEY 仅排队（长任务）→ 触发心跳（每 10 分钟；主理人对老板每分钟报平安）。
  4. 真实 shot 的 `asset_frame_start` 为 `assets/` 前缀时走 `data_uri` 分支（P0-1 BUG-2），smoke 须用真实 `assets/` 帧图覆盖该路径。
  5. 派活后主理人必验证产出（git log / 文件存在 / 跑通），空返回 = 未完成。

---

## 五、闸1 签核（老板）

- 老板确认验收标准（逐条）：☑ 已签（A-1 自签·纯验证类·老板 0812 授权主理人自决）
- 备注：推荐先做项，零风险，巩固 L1 真测纪律，防回归误烧 VIP。
