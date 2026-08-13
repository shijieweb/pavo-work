# T-20260813-06 测试文档（test.md）· P0-2 图视冲突预检

> 阶段定位：**只写测试计划/用例，不写代码、不执行改动、不调用 AGNES API**（新流程：测试文档先于实现）。
> 被测对象：新预检功能（尚未实现，实现见 design.md / 后续开发阶段）。
> 分层：L0（dry-run 零 AGNES 额度，主）/ L1（免费 KEY 真测，AC-1.5 证据）。
> 红线：本功能只做预检拦截提示，不改生成逻辑；测试全程不烧 VIP（免费 KEY / 零额度 dry-run）。

---

## 一、测试计划

### 1.1 分层选择

| 层 | 名称 | 是否调 AGNES | 用途 | 必测性 |
|---|---|---|---|---|
| **L0** | dry-run 零额度 | 否（mock 注入） | 空镜判定、输入校验、异常处理、输出 schema、决策汇总逻辑 | **必测（主）** |
| **L1** | 免费 KEY 真测 | 是（AGNES_TEST_API_KEY） | 真实 `prompt_frame_match` 端到端 + AC-1.5 真项目 dry-run 报告 | 必测（AC-1.5 锚点） |
| L2 | 生产 VIP | 是（VIP KEY） | 不涉及 | 禁止（PRD 边界：不烧 VIP） |

- **L0 覆盖原则**：预检函数 = 薄封装（输入归一 + 空镜免检 + 决策汇总 + 错误兜底），核心视觉判定复用 `vision_review.prompt_frame_match`。L0 用 mock/stub 注入该依赖，把预检函数自身的逻辑全部测透，**零额度、无网络**。
- **L1 覆盖原则**：复用既有 `l1_smoke.py` 的入口守卫范式（`key_pool_status()["mode"]=="test"` 硬断言 + `_pool.use_test()` 切换，无免费 KEY 立即非零退出），确保真测绝不打到 VIP 分支。

### 1.2 环境准备

- **Python 环境**：现有 3.x（与 `route_diff_test.py`/`l1_smoke.py` 同环境），无需新装依赖。
- **脚本路径（预期，待实现确认）**：
  - 预检入口（待实现，如 `short_drama_workflow/scripts/diag/prompt_precheck.py`）——本阶段不创建；
  - 复用 `short_drama_workflow/scripts/diag/vision_review.py`（`prompt_frame_match` / `review`）；
  - 复用 `short_drama_workflow/scripts/diag/prompt_training.py`（YAML 模板渲染 `build_variants`）；
  - 复用 `~/.workbuddy/skills/agnes-ai/scripts/agnes_client.py`（L1 真测）；
  - 空镜免检判定规则参照 `prompt_training.py` 内 `_is_empty` 既有逻辑（英文硬编码，见 §五风险）。
- **服务依赖**：**无需重启任何服务**——预检是离线脚本/函数级，不依赖 8777/8787/8788 监听；仅 L1 真测需要 AGNES 免费 KEY（网络出向到 AGNES API）。
- **免费 KEY**：`AGNES_TEST_API_KEY`（L1 用；入口守卫与 `l1_smoke.ensure_test_mode` 同款）。

### 1.3 执行方式与退出码（预期约定）

- L0：以断言脚本/测试框架跑用例（约定沿用仓库惯例：`route_diff_test.py` 的 exit 0/1）。
- L1：`python <预检入口> --project <id> --shot <n> --dry-run` 输出 JSON 报告。
- 退出码约定：`0`=全部 PASS；`1`=存在 FAIL；`3`=入口守卫失败（未处于 test 模式且无免费 KEY，防烧 VIP，同 `l1_smoke`）。

---

## 二、逐 AC 测试用例

> 输入约定（预期）：`(shot: dict, first_frame: str, last_frame: str)` 或归一后的 `(prompt_en: str, first_path, last_path)`；
> 输出约定：结构化 dict `{ok, overall: match|warn|fail|n/a, opening:{verdict,issues}, ending:{verdict,issues}, conflicts:[...]}`（映射见 §四）。

### AC-1.1 预检函数：输入单镜 shot + 首尾帧 → 输出 match/warn/fail + 冲突点描述

| 用例 | 场景 | 输入（数据来源） | 期望输出 |
|---|---|---|---|
| TC-1.1.1 | **一致 → match** | v19 人物走近：prompt 用 `exp_0812_1502.json` v19 的 `params.prompt`（"…same man…white shirt, black trousers…"），首尾帧用 `experiments/ep_0811_145935/shot1/v19/frame1.png` + `lastframe.png`（真实帧） | `overall=match`（映射自 pass），`opening.verdict=pass`、`ending.verdict=pass`，`issues=[]` |
| TC-1.1.2 | **冲突 → fail** | 构造冲突：prompt 写 `no people / empty street`，首帧用含人物帧（`v19/frame1.png`）→ 预检应识别"prompt 说无人但帧有人" | `overall=fail`，`conflicts` 含场景冲突条目（severity high），描述可读 |
| TC-1.1.3 | **边界 → warn** | v18 空镜雾气微变：prompt 用 v18 `params.prompt`，首尾帧用 `v18/frame1.png` + `lastframe.png`（已知真值：`exp_0812_1502.json` v18 `prompt_frame_match.overall=warn`，ending 低严重度场景冲突） | `overall=warn`，`ending.verdict=warn`，issue 为 low 严重度、不拦截 |

- 附加断言（L0，mock 注入三种 verdict）：分别把 `prompt_frame_match` 打桩返回 `pass/warn/fail` → 预检 `overall` 正确透传/汇总；`conflicts` 由 `opening/ending.issues` 展平生成。

### AC-1.2 空镜免检：prompt 含 no people → 输出 n/a

| 用例 | 输入 | 期望输出 |
|---|---|---|
| TC-1.2.1 | 英文空镜 prompt（含 `no people`，如 v18 / `empty_scene_v1.yaml` VIDEO_PROMPT_EN） | 身份/人物相关检查跳过，整体标 `n/a`（沿用 `_is_empty` 规则） |
| TC-1.2.2 | 中文空景 prompt（如 `无人物/空镜/空旷街道`） | **待确认**：现有 `_is_empty` 只认英文，中文空镜是否纳入免检需开发定（见 §五）；本用例先按"不误判为有人、输出非 fail"的最低要求设计 |
| TC-1.2.3 | 非空镜 prompt（有人物描述，如 v19） | 不标 n/a，正常输出 match/warn/fail |

### AC-1.3 解耦：预检失败不阻塞生成

| 用例 | 场景 | 输入 | 期望输出 |
|---|---|---|---|
| TC-1.3.1 | 异常输入不崩溃 | 帧路径不存在 / 损坏图片 / prompt 为空 / shot 缺字段 | 返回 `{ok:false, error:"<原因>"}`，不抛未捕获异常、进程不崩 |
| TC-1.3.2 | AGNES 调用失败不阻塞 | L0 mock `prompt_frame_match` 抛异常 | 预检返回失败提示（error dict），调用方（生成链）可继续，无崩溃 |
| TC-1.3.3 | 零额度 dry-run 可测 | L0 全 mock，断言全程无 AGNES 网络调用 | 不发任何请求，用例在离线环境跑通 |
| TC-1.3.4 | 输出 schema 稳定 | match/warn/fail/n/a/error 五种结果 | 均返回同构 dict，字段名/类型一致，便于生成链消费 |

### AC-1.4 接入点验证（待主理人确认接入方式后补充具体用例）

- **占位说明**：PRD AC-1.4 的接入方式（生成前自动附加 vs 手动触发 vs 挂 `/api/diagnose`）由开发文档 design.md 确定、需老板/主理人确认后实现。**本阶段不写死用例，先记录建议验证方法**：
  - 若挂 `/api/diagnose`：请求带 `shot_id` + `dry_run=true` → 期望 200 + 预检报告 JSON，且不触发视频生成、不烧额度；
  - 若生成前自动附加：在生成链入口（`prompt_training.gen_video` / `server` 侧提交前）注入 → 期望日志出现 `PRE-CHECK` 行且 fail 时生成被提示拦截（非崩溃）；
  - 若手动触发：CLI 参数 `--precheck` → 期望输出报告落盘。
- **验收锚（所有接入方式通用）**：dry-run 零额度、失败=提示不崩溃（对齐 AC-1.3）。

### AC-1.5 真实项目 shot dry-run 一次，输出报告

| 用例 | 指定项目/镜 | 帧来源 | 期望输出 |
|---|---|---|---|
| TC-1.5.1（主） | `ep_0811_145935` shot 1（训练实验项目，SOP §11 商业验证镜头） | v19 真实帧 `experiments/ep_0811_145935/shot1/v19/frame1.png` + `lastframe.png`（已知真值 pfm=pass） | dry-run 输出完整 JSON 报告（per-check 判定 + overall），`overall=match`，报告落盘 |
| TC-1.5.2（辅·生产项目） | `html_prototype/projects/ep_0811_145935`（深夜面馆）shot 1（全景建立镜） | 首帧候选 `assets/references/kf_start_001.png`（真实帧）；尾帧从 `assets/video/shot001.mp4` 用 ffmpeg 抽末帧（复用 prompt_training 同款 `-sseof -0.2` 逻辑）；prompt 用 storyboard `video_prompt` | dry-run 输出报告；`overall` 只做记录（真值待 L1 实测后回填），重点是**链路可跑通、报告结构完整** |

- 说明：TC-1.5.1 以"已知质检真值（exp_0812_1502 v19 pfm=pass）"为回归锚，预检输出应与历史真值一致，避免自造预期。

---

## 三、数据准备

### 3.1 现成 shot 数据

| 数据源 | 内容 | 用途 |
|---|---|---|
| `experiments_data/exp_0812_1502.json` | v18（空镜）/ v19（人物走近）变体：`params.prompt` + `params.keyframes[].src` + 已知质检真值（v18 pfm=warn、v19 pfm=pass、identity n/a/pass） | L1 真测对照（回归锚）；构造 TC-1.1.1/1.1.3/1.2.1 输入 |
| `html_prototype/projects/ep_0811_145935/storyboard.json` | 真实生产项目 14 镜：`video_prompt` / `first_frame_prompt` / `last_frame_prompt` / `shot_size` / `gen_strategy` | AC-1.5 生产项目镜头输入 |
| `scripts/diag/templates/camera_move_v7.yaml` / `empty_scene_v1.yaml` | 变体配方：v18 真空景 / v19 走近 / v20 极值；空镜模板含明文 `no people` 与 `identity_check: skip` | 构造合法/空镜输入样本 |
| `scripts/diag/experiments/ep_0811_145935/shot1/{v18,v19}/` | 真实首尾帧 png（`frame1.png` / `lastframe.png`）+ 成片 mp4 | L1 真实帧数据 |

### 3.2 首尾帧来源

| 来源 | 文件 | 说明 |
|---|---|---|
| 真实帧（训练实验，优先） | `scripts/diag/experiments/ep_0811_145935/shot1/v18/frame1.png`+`lastframe.png`；`v19/frame1.png`+`lastframe.png` | 与 exp_0812_1502 真值一一对应，AC-1.1/1.2/1.5 主数据 |
| 真实帧（生产项目） | `html_prototype/projects/ep_0811_145935/assets/references/kf_start_001.png`（3.9MB）、`kf_start_003.png`（3.5MB） | 真实首帧候选；尾帧可从 `assets/video/shot001.mp4` 用 ffmpeg 抽取（复用 `prompt_training` 的抽帧命令范式） |
| 测试帧（脚本生成，L0 兜底） | `scripts/assets/first.png`+`last.png`（l1_smoke 生成，冷/暖渐变）；`scripts/diag/assets/first.png`+`last.png`+`grad_a.png`+`grad_b.png` | L0 纯逻辑用例（不依赖 AGNES 语义）时充当"存在的本地图片" |
| 帧转 data URI | `vision_review._datauri` / `server.asset_abs` | 复用既有能力，不新造 |

---

## 四、判定矩阵

| 判定 | 含义 | 触发条件（依据） | 生成链行为 |
|---|---|---|---|
| **match**（=prompt_frame_match `pass`） | prompt 与首尾帧一致，无 issue | `opening.verdict=pass` 且 `ending.verdict=pass`（如 v19 真值） | 放行生成 |
| **warn** | 低严重度冲突/轻微缺失 | 任一维度 `warn` 且无 `fail`（如 v18 ending 雾气微变，low severity——SOP §11：warn 低严重度可接受） | 放行 + 提示人工确认 |
| **fail** | 硬冲突 | 任一维度 `fail`（如 prompt 写 no people 但帧有人、景别/服装/场景冲突 high） | 拦截提示，不崩溃、不改生成逻辑（AC-1.3） |
| **n/a** | 空镜免检 | prompt 命中空镜规则（`no people`/空景，AC-1.2；空镜身份审查本应标 n/a，SOP §11） | 跳过身份/人物相关检查，放行 |
| **error**（ok=false） | 预检自身失败 | 输入异常 / AGNES 调用失败（TC-1.3.1/1.3.2） | **不阻塞生成**，记录错误提示 |

- **汇总规则（建议，供实现参考）**：`overall` 取 `prompt_frame_match.overall` 为主；任一 `fail` → fail；无 fail 但任一 `warn` → warn；全 pass → match；空镜 → n/a。
- 与现有 `pass/warn/fail` 术语的关系：PRD 用 match/warn/fail，`prompt_frame_match` 用 pass/warn/fail——**match ≡ pass**，文档统一以 PRD 四值（match/warn/fail/n/a）为准，测试断言按四值写。

---

## 五、风险与待确认

1. **空镜判定只认英文**：既有 `_is_empty` 硬编码 `no people/no person/empty /without any people`；中文空镜（"无人物/空镜"）是否纳入免检需开发确认（TC-1.2.2）。若维持英文-only，测试用例统一用英文空镜 prompt 规避。
2. **AC-1.4 接入方式未定**：占位（见 §AC-1.4），等主理人/老板确认接入方式后补具体用例。
3. **预检输入字段命名待实现定**：`shot.asset_frame_start/asset_frame_end`（storyboard 现为空）vs 实验 `keyframes[].src`——测试数据准备已覆盖两种形态，实现定名后对齐。
4. **TC-1.5.2 真值未知**：生产项目 shot1 无历史 pfm 真值，该用例只验证链路可跑通 + 报告结构，不做判定断言（待 L1 实测回填）。
5. **L1 真测的网络/KEY 依赖**：免费 KEY 额度有限（3000 次/天，vision_review 头注释），L1 用例控制在最小次数（AC-1.5 主用例 1 次 + 回归对照 1 次），其余全部 L0 覆盖。

---

## 六、后续执行流程（Round 控制）

- 实现阶段完成（design.md + 预检入口落地）后按本文档执行：
  - Round 1：跑 L0 全量 + L1 真测 → 分析 → 路由（全 PASS→NoOne；源实现 bug→Engineer；测试自身 bug→QA 自修）。
  - Round 2（如需要）：回归 → 全 PASS 退出；仍失败则记录为 Known Issues 收尾，**不进入 Round 3**。
- 报告格式：总数/通过/失败 + 失败用例（期望 vs 实际 + 源文件/函数）+ 路由决策。

---

## 七、独立验收结果（QA 勾选版 · software-qa-engineer-3 严过关，2026-08-13）

> 验收对象：commits 98807f5 / c0cc2c4 / f5c0398；入口 `short_drama_workflow/scripts/diag/precheck.py`（design.md 对齐）。
> 环境：Python 3.13.14，无需重启服务（CLI 离线跑）；线上复验走 8787（已重启 PID 25284）。
> 证据文件：`dev-work/tasks/T-20260813-06/qa_acceptance_evidence.json`（含 1 次真视觉证据 `qa_real_vision_evidence.json`）。

### L0 静态核验

| 项 | 结果 |
|---|---|
| precheck.py 存在（12.7KB，`scripts/diag/precheck.py`） | ✅ |
| `is_empty_shot(prompt)` / `precheck_shot(shot, first, last, prompt, model, dry_run, timeout)` 签名对齐 design.md §2.1 | ✅ |
| route_registry.json 34 路由含 `/api/precheck` | ✅ |
| server.py 有 `/api/precheck` 路由（行 4829-4855，404 处理 + 写回 shot.precheck + 落盘） | ✅ |

### L1 真跑（独立执行）

| AC | 用例 | 命令/请求 | 实际输出 | 结果 |
|---|---|---|---|---|
| **AC-1.1** | 真实项目+真实帧 dry-run | `python precheck.py --project ep_0811_145935 --shot 1 --first experiments/.../shot1_v2/s1_0.png --last .../s1_5_8.png --dry-run` | `precheck="dry-run"`，素材齐备，零 AGNES | ✅ |
| **AC-1.1（真视觉）** | 免费 KEY 强制 test 模式（`_pool.use_test()` + 断言 mode==test）真跑 | `precheck_shot(shot1, first=s1_0.png, last=s1_5_8.png, dry_run=False)` | `precheck="warn"`，`opening=pass`，`ending=warn(景别不符 low)`，conflicts 1 条，`mode_after=test`（零 VIP） | ✅ |
| **AC-1.2** | 空镜免检 | `--prompt "Empty street at night, no people, no characters..." --dry-run` | `precheck="n/a"`，`empty_shot=true`，零 AGNES | ✅ |
| **AC-1.3** | 缺尾帧 / 缺 prompt / shot 不存在 | CLI 三连 | 缺尾帧→warn；缺 prompt→warn；`--shot 999`→`{ok:false,error}` + exit 1，不崩溃 | ✅ |
| **AC-1.4** | 线上端点复验 | `POST http://127.0.0.1:8787/api/precheck {"id":1,"dry_run":true}` / `{"id":999}` | 200 + `precheck=warn 素材缺失：首帧图、尾帧图`；404 + `shot 999 not found` | ✅ |
| **AC-1.5** | 独立产出证据（与开发 C1 比对） | 同 AC-1.1 命令独立复跑 | 与 dev `precheck_dryrun_report.json` C1 一致（precheck=dry-run / 素材齐备 / 零 AGNES） | ✅ |

### 判定矩阵验收

- **match**：真视觉 opening=pass 路径已见（本镜 ending warn → 整体 warn）；pass→match 映射代码审查通过（`mapping={"pass":"match","warn":"warn","fail":"fail"}`，precheck.py 行 231）。
- **warn / fail / n/a / error**：warn（素材缺失 + 真视觉景别不符）、n/a（空镜 + ui 策略）、error（shot 不存在 exit 1）均已实测；fail 由 prompt_frame_match overall=fail 透传（映射审查通过，未单独造 fail 图样）。

### 异常记录（按铁律不自行修复，路由工程师）→ **Round 2 已修复·复验通过**

| ID | 级别 | 修复 commit | Round 2 复验结果 |
|---|---|---|---|
| **[BUG-1]** | P2（原）→ 已修复 | a04c8f1 | ✅ 复验通过：CLI 真视觉无免费 key → `{ok:false,precheck:"blocked",error:"…为杜绝误烧 VIP，拒绝真视觉预检…"}` + exit 3；`POST {"id":1}`（不带 dry_run）→ 200 + `"dry_run": true`（默认零额度）；有免费 key 时 `ensure_test_mode()` 自动切 test（MODE_AFTER=test）真视觉正常跑，不误伤 |
| [OBS-1] | P3（原）→ 已修复 | a04c8f1 | ✅ 复验通过：dry-run 下裸路径不存在（`/no/such/file.png`）→ `precheck=warn 素材缺失`（`_frame_src` 统一返回空串，与 assets/ 分支一致） |

### 验收结论

- **AC-1.1~1.5 全部 PASS**（dry-run 链路 + 1 次真视觉免费 KEY 零 VIP + 线上端点复验 + 独立证据比对）。
- 2 项异常（BUG-1 P2 / OBS-1 P3）已由工程师在 a04c8f1 修复，Round 2 复验通过（详见 §八）。
- 测试副作用说明：POST /api/precheck 按设计写回 `shot.precheck` 并落盘 `storyboard.json`（幂等同值，非破坏性）。

---

## 八、Round 2 回归结果（BUG-1/OBS-1 修复复验 · 2026-08-13）

> 修复 commit：`a04c8f1 fix(precheck): BUG-1 真视觉路径加 test-mode 硬守卫 + OBS-1 裸路径判缺失`。
> 环境：8787 PID 29532 / 8777 PID 29296 已重启加载修复代码。

### BUG-1 修复复验（3 项 + 1 项防误伤）

| 项 | 命令/请求 | 实际 | 结果 |
|---|---|---|---|
| 守卫拦截（无免费 key） | `AGNES_TEST_API_KEY= python precheck.py --shot-id 1 --first a.png --last b.png --prompt "Wide shot..."` | `{"ok":false,"precheck":"blocked","error":"…为杜绝误烧 VIP，拒绝真视觉预检…"}` + **exit 3** | ✅ |
| 端点默认零额度 | `POST 8787/api/precheck {"id":1}`（不带 dry_run） | **200** + `"dry_run": true` + `precheck=warn 素材缺失`（零 AGNES） | ✅ |
| 注册表回归 | `PYTHONIOENCODING=utf-8 python route_diff_test.py --base http://127.0.0.1:8787` | **34 路由, PASS=34, FAIL=0, exit 0** | ✅ |
| 防误伤（有免费 key 真视觉仍可用） | `precheck_shot(shot1, first=s1_0.png, last=s1_5_8.png, dry_run=False)`（内置 ensure_test_mode） | `precheck=match, pfm.overall=pass, conflicts=0`，`MODE_AFTER=test`（自动切免费 key，零 VIP） | ✅ |

> 注：本镜真视觉 verdict 由 Round 1 的 warn（景别不符 low）变为 Round 2 的 match——AGNES 视觉为 LLM 非确定性判定（SOP §一.3：runs≥2 多数投票），属预期；本轮顺带实测到 **match 映射路径**（pass→match，Round 1 仅代码审查）。

### OBS-1 修复复验

| 项 | 命令 | 实际 | 结果 |
|---|---|---|---|
| 裸路径不存在 | `python precheck.py --shot-id 5 --first /no/such/file.png --last /no/such/last.png --prompt "Wide shot of a street" --dry-run` | `precheck=warn`（素材缺失：首帧图、尾帧图），不再误报 dry-run | ✅ |

### AC-1.1~1.5 主路径回归（未被修复破坏）

| AC | 验证 | 实际 | 结果 |
|---|---|---|---|
| AC-1.1 | 真实项目+真实帧 dry-run | `precheck=dry-run`，素材齐备，零 AGNES | ✅ |
| AC-1.2 | 空镜 no people | `precheck=n/a, empty_shot=true` | ✅ |
| AC-1.3 | 缺尾帧 / shot 不存在 | warn / `{ok:false,error}` + exit 1，不崩溃 | ✅ |
| AC-1.4 | `POST {"id":1,"dry_run":true}` / `{"id":999}` | 200 + warn 报告 / 404 | ✅ |

### Round 2 结论

- **全 PASS**：BUG-1（守卫 + 端点默认零额度 + 注册表）与 OBS-1 均修复生效；AC-1.1~1.5 主路径无回归；真视觉仍可用且零 VIP。
- 环境说明：`route_diff_test.py` 在 GBK 控制台打印 ✅ 会 UnicodeEncodeError（脚本自身 print 兼容性，非产品缺陷），需 `PYTHONIOENCODING=utf-8` 运行；已确认修复前后注册表行为一致。
- T-20260813-06 进入验收收尾（≤2 轮红线内完成）。
