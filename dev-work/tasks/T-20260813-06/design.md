# P0-2 图视冲突预检 · 开发设计文档

- 任务：T-20260813-06（P0-2 图视冲突预检）
- 作者：软件工程师 寇豆码（software-engineer-2）
- 日期：2026-08-13
- 前置依赖：P0-1 YAML 模板已闭环（`prompt_training.py` 的 `build_variants` + templates/*.yaml）
- 本阶段交付：**仅本文档**（文档先于代码；主理人审过 → 才进入实现阶段）
- 铁律遵守：本阶段未写任何业务代码、未改动任何现有文件、未调用任何 AGNES 生成/视觉 API（仅读代码）

---

## 1. 现状调研结论（基于真实代码，非臆造）

### 1.1 可复用能力清单

| 能力 | 路径 | 函数签名 | 返回结构 | 说明 |
|---|---|---|---|---|
| 智能抽帧 | `short_drama_workflow/scripts/edit/diagnosis.py` | `extract_frames_smart(video, out_dir=None, width=480, interval=0.5, tail_margin=0.2)` | `[(path, t), ...]`（首帧 0s 必抽 + 尾帧 dur-0.2s 必抽 + 中段 0.5s 间隔） | 0812 老板方法论：保证首尾帧覆盖。**本次预检用不上**（预检输入是首尾帧图，不是视频），但可在"生成后回读视频抽帧"场景复用 |
| 图片转 data URI | `vision_review.py` | `_img_src(path)` | 字符串（http/data URI 原样；本地文件→`data:image/...;base64,...`） | AGNES 只收 URL/data URI（08 经验库：本地路径报错），`prompt_frame_match` 内部已用 |
| **提示词-帧匹配** | `vision_review.py` | `prompt_frame_match(prompt_en, first_path, last_path, model="agnes-2.5-flash", timeout=150)` | `{ok, opening:{verdict,issues}, ending:{verdict,issues}, overall}` | **本任务核心复用点**，详见 1.2 |
| 通用视觉审查 | `vision_review.py` | `review(paths, kind="quality"\|"identity"\|"internal"\|"continuity"\|..., context="", model=..., timeout=150)` | `{ok, kind, verdict:"pass\|warn\|fail", issues:[{type,severity,desc}], confidence, raw}` | 7 类审查引擎；本任务主用 `prompt_frame_match`，`review(kind="internal")` 可作扩展项（首尾帧图自身差异检查） |
| 变体渲染 | `prompt_training.py` | `build_variants(shot, ref, template="camera_move_v2")` | `{name: {images, keyframes, prompt, hyp, ...}}` | 从 YAML 注入变量渲染最终 prompt/keyframes；**预检的"对比 prompt"应取渲染后的最终 prompt 而非原始 shot.video_prompt**（若走生成链预检） |
| 空镜免检判定 | `prompt_training.py` main()（行 417-423） | 内联逻辑 | `{"verdict":"n/a", "issues":[], "note":"空镜镜头（prompt 无人物），免检尾帧脸型"}` | 关键词：`"no people" / "no person" / "empty " / "without any people"`（小写匹配）。**本次预检直接抽成独立函数复用** |
| AGNES 密钥双模式 | `~/.workbuddy/skills/agnes-ai/scripts/agnes_client.py` | `_pool.use_test()` / `_pool.use_prod()`；环境变量 `AGNES_TEST_API_KEY` / `AGNES_API_KEYS` | — | 测试用免费 key（无限额度限速）不占 VIP（08 经验库 E 节）；**零额度保障的关键** |
| 单镜诊断+PFM 后处理 | `html_prototype/server.py` 行 4751-4827（`/api/diagnose`） | POST `{id: shot_id, video?, frames?, runs?, face_check?, deep?}` | `res`（diagnose_clip 结果）+ `res["prompt_frame_match"]` | 已有"生成后" PFM 检查（抽视频首尾帧 vs video_prompt），**但不是"生成前"预检**——见 1.3 缺口 |

### 1.2 `prompt_frame_match` 现状（输入/输出/阈值）

**输入**：
- `prompt_en`：英文视频 prompt 文本（截断至 1200 字符）
- `first_path` / `last_path`：首/尾帧图（http URL / data URI / 本地路径均可，内部 `_img_src` 归一化）
- `model`：默认 `agnes-2.5-flash`（免费 3000 次/天）
- 内部构造审查 prompt（vision_review.py 行 123-136）并调用 `agnes_client.chat(..., images=[first, last])`，`temperature=0.2, max_tokens=1200, timeout=150`

**判定维度（prompt 内已内置，非代码阈值）**：
- ① 开场匹配：首帧 vs 提示词开场场景元素（场景类型/建筑/光线/氛围/时间）。**运镜镜头首帧空景属正常**，人物不在首帧不算不匹配；场景元素缺失→`warn`，完全冲突（如 prompt 写 no people 但首帧有人）→`fail`
- ② 结束匹配：尾帧 vs 提示词结束状态（人物姿态/景别/表情/场景）。尾帧应出现主要人物和关键元素；景别/姿态/服装应匹配；缺失→`warn`/`fail`
- issue type 枚举：opening=`场景缺失|场景冲突|其他`；ending=`人物缺失|景别不符|姿态不符|服装不符|场景冲突`

**输出结构**：
```json
{"ok": true,
 "opening": {"verdict": "pass|warn|fail", "issues": [{"type": "...", "severity": "high|low", "desc": "..."}]},
 "ending":  {"verdict": "pass|warn|fail", "issues": [...]},
 "overall": "pass|warn|fail"}
```
失败路径：`{"ok": false, "error": "...", "raw": "..."}`（解析失败/网络异常，不抛异常）。

**现有调用点**（证明思路已验证、结构已消费）：
1. `prompt_training.py` main()（行 384-400）：生成后抽视频首尾帧 → PFM → 写 report.prompt_frame_match
2. `server.py /api/diagnose`（行 4793-4817）：生成后抽视频首尾帧 → PFM → 写回 `shot.diagnosis.prompt_frame_match`
3. 前端 `studio.html`（行 713-721）已渲染 PFM 徽标（✅ 匹配 / ⚠ 部分 / ❌ 不匹配 + 开场/结束 verdict + issues 列表）
4. 数据契约 `03_数据契约.md`：experiments_data variants[].prompt_frame_match schema = `{overall, opening{verdict,issues}, ending{verdict,issues}}`（**本次预检输出沿用此 schema，前端/看板零改动可消费**）

### 1.3 关键缺口（P0-2 要补的"生成前"语义）

现有 PFM 全部是**生成后**：需要已有视频 → ffmpeg 抽帧 → 对比。PRD 要求**生成前**：用"首尾帧图"（`asset_frame_start`/`asset_frame_end`）直接对比，在烧视频额度之前拦截"prompt 描述 vs 首尾帧图实际内容"的矛盾（如 prompt 说近景、首帧却是远景）。

另外两点与生成后检查的差异：
1. **输入**：首尾帧图路径（或 data URI），而非视频
2. **空镜免检前置**：生成后检查里空镜免检只作用于 identity 审查（尾帧脸型）；生成前预检要把它提前到整个预检入口（空镜→整体标 n/a，不调视觉 API，零额度）
3. **与生成链解耦**：预检失败 = 拦截提示，绝不阻塞/不崩溃生成链

---

## 2. 预检设计

### 2.1 新增文件与函数（实现阶段产物，本文档只定设计）

**新增**：`short_drama_workflow/scripts/diag/precheck.py`（只读复用 diagnosis.py / vision_review.py / prompt_training.py，不改它们）

核心函数（设计签名，实现阶段落地）：

```python
def is_empty_shot(prompt: str) -> bool:
    """空镜免检判定：prompt 小写含 no people/no person/empty /without any people → True。
    抽取自 prompt_training.py 行 417-419 的内联逻辑，预检/生成链两处共用同一口径。"""

def precheck_shot(shot: dict, first: str = None, last: str = None,
                  prompt: str = None, model: str = "agnes-2.5-flash",
                  dry_run: bool = False, timeout: int = 150) -> dict:
    """生成前图视冲突预检（AC-1.1/1.2/1.3）。
    输入：shot（storyboard 单镜 dict）+ 首尾帧图路径/URL/data URI。
      - first/last 缺省时自动回退 shot["asset_frame_start"]/["asset_frame_end"]（http 或 assets/ 相对路径经 asset_abs 解析）。
      - prompt 缺省时取 shot["video_prompt"] 或 shot["prompt"]。
    处理：
      1) 空镜免检：is_empty_shot(prompt) → 返回 n/a（不调视觉 API，零额度）
      2) 素材自检：prompt 空 / 首帧缺 / 尾帧缺 → 返回 warn + 缺项描述（不调 API）
      3) dry_run=True → 只做 1)+2)，verdict 字段标 "dry-run"（不调 AGNES）
      4) 否则复用 vision_review.prompt_frame_match(prompt, first, last) → 结构透传
    输出：见 2.2。"""
```

可选扩展（默认不做，文档留档）：首尾帧图自身"物理可衔接/差异一致性"检查可复用 `review([first,last], kind="internal")`——但 08 经验库提示这是**生成前图片层面**的独立质检项，与 prompt-图一致性是两个维度，建议放 P0-3 评估，不在本任务范围。

### 2.2 输入 / 处理 / 输出

**输入**（单镜维度）：
- `shot`：storyboard.json 的单镜 dict（关键字段：`id / video_prompt / prompt / asset_frame_start / asset_frame_end / gen_strategy / scene_type / cn_story / first_frame_prompt / last_frame_prompt`）
- `first` / `last`：首/尾帧图路径（本地 `assets/...` 相对路径、绝对路径、http URL、data URI 均可——复用 `_img_src` 归一化）；缺省从 shot 字段回退
- `prompt`：要对比的提示词；缺省取 `shot.video_prompt`（**建议显式传渲染后的最终 prompt**，见 2.4 注）

**处理流程**：
```
precheck_shot(shot, first, last, prompt)
  ├─ 1. is_empty_shot(prompt) ──────────────► {"precheck":"n/a","reason":"空镜免检"}（零 API 调用）
  ├─ 2. 素材自检（prompt/首帧/尾帧任一缺失）──► {"precheck":"warn","issues":[缺项]}（零 API 调用）
  ├─ 3. dry_run=True ───────────────────────► {"precheck":"dry-run","checks":[...]}（零 API 调用，AC-1.3/1.5）
  └─ 4. 默认：prompt_frame_match(prompt, first, last)
         ├─ overall=="pass" ────────────────► {"precheck":"match"}
         ├─ overall=="warn" ────────────────► {"precheck":"warn","conflicts":[opening+ending issues]}
         └─ overall=="fail" ────────────────► {"precheck":"fail","conflicts":[...]}（拦截提示）
```

**输出结构**（沿用 experiments schema，前端/看板可零改动消费）：
```json
{
  "ok": true,
  "precheck": "match|warn|fail|n/a|dry-run",
  "prompt_frame_match": {"overall": "...", "opening": {"verdict":"...","issues":[...]},
                          "ending": {"verdict":"...","issues":[...]}},
  "conflicts": [{"stage": "opening|ending", "type": "场景缺失|场景冲突|人物缺失|景别不符|姿态不符|服装不符", "severity": "high|low", "desc": "..."}],
  "empty_shot": true|false,          // 空镜免检标记
  "inputs": {"shot_id": 1, "prompt": "...(前200字)", "first": "...", "last": "..."},
  "dry_run": true|false,             // 是否零额度模式
  "model": "agnes-2.5-flash"
}
```

**CLI 入口**（手动触发，AC-1.5 证据用）：
```bash
# 零额度 dry-run（不调视觉 API，可离线跑）
python precheck.py --project ep_0811_145935 --shot 1 --dry-run

# 真跑视觉（用 AGNES_TEST_API_KEY 免费 key，不占 VIP）
AGNES_TEST_API_KEY=<免费key> python precheck.py --project ep_0811_145935 --shot 1 \
    --first <首帧图路径> --last <尾帧图路径>

# 直接传图（不依赖项目）
python precheck.py --shot-id 1 --first a.png --last b.png --prompt "Wide shot, ..." --dry-run
```

### 2.3 空镜免检（AC-1.2）

- 判定复用 `is_empty_shot(prompt)`（口径与 prompt_training.py 完全一致：`no people/no person/empty /without any people`，小写匹配）
- 命中 → 整体返回 `precheck:"n/a"`，**不调用任何视觉 API**（比生成后检查更进一步：生成后检查只是 identity 免检，预检直接整镜免检，天然零额度）
- 中文空镜词（无行人/无人/空镜/空无一人/没有人的场景）在 shot 层由 `server._gen_first_frame_fallback` 已追加 "NO people" 英文强化（08 经验库 0812）；`is_empty_shot` 额外兼容中文关键词可作实现期增强项（默认先只收英文，与现有一致，避免口径漂移）

### 2.4 接入点方案（AC-1.4，需主理人确认后实现）

**方案 A（推荐）：独立端点 `/api/precheck` + 手动触发**
- 新增 `POST /api/precheck`（server.py 路由区，仿 `/api/diagnose` 写法）：body `{project_id?, id: shot_id, first?, last?, prompt?, dry_run?}`；返回 2.2 输出结构；`dry_run=true` 零额度
- 前端在单镜诊断区旁加"预检"按钮（复用 studio.html 已有 PFM 徽标渲染，零新 UI 体系）
- 优点：不改生成链主流程（08 经验库铁律：生成链稳定优先）；符合 PRD"预检不阻塞正常生成"；dry-run 证据可随时跑；视觉调用失败只影响预检按钮，不影响任何生成
- 代价：需人工点一下（非全自动）；需登记 `agnes_proxy.py` STUDIO_PREFIXES 白名单（08 经验库 A 节：新 /api/* 必须登记，否则 8787 404）

**方案 B：生成前自动附加（软附加，不推荐首期做）**
- 在 `server.video_submit` 后台任务内、`generate_keyframes_real` 之后、`create_video` 之前，插入 `precheck_shot(...)`；`fail` 只写 warning 到 shot.precheck 字段并记日志，**不阻断**生成
- 优点：全自动，无需人工
- 代价：改生成链（与"预检不阻塞正常生成"原则冲突面更大）；视觉调用有网络/延迟/失败风险，插在生成热路径上拖慢首尾帧→视频的衔接；上线节奏应晚于方案 A

**推荐**：**先方案 A**（独立端点 + 手动触发，生成链零改动）；方案 B 作为后续"老板要自动化"时的增强项，另行评审。AC-1.4 结论标注为"方案 A，待主理人/老板确认"。

> 注：无论 A/B，**对比 prompt 建议用渲染后的最终 prompt**（keyframes 模式 = `_transition_prompt(shot)` 组合身份锁/镜头/电影语法的成品；reference 模式 = `_clean_video_prompt + global_style + animate`），而非裸 `shot.video_prompt`——PFM 是拿"真正提交给 AGNES 的词"去对比首尾帧图。实现期在 precheck.py 内做轻量拼装（只读复用 server 的纯函数），或在方案 A 端点由调用方传入已渲染 prompt。此点记入实现清单。

---

## 3. 零额度保障（AC-1.3）

| 层级 | 机制 | 说明 |
|---|---|---|
| dry-run 模式 | `precheck_shot(..., dry_run=True)` | 只做空镜判定 + 素材自检，**不调用任何 AGNES API**，可离线跑（AC-1.5 证据用此模式也能跑通，只是不产出真视觉 verdict） |
| 空镜免检 | `is_empty_shot` 命中即返回 | 连 dry-run 的视觉调用都不需要，天然零额度 |
| 测试 key | `AGNES_TEST_API_KEY`（免费 key，无限额度限速） | 真跑视觉时用它，不占 VIP 500s/天（08 经验库 E 节）；`agnes_client._pool.use_test()` 自动切 test 模式 |
| 失败降级 | `prompt_frame_match` 异常返回 `{ok:false, error}` | 预检封装为"失败=提示，不崩溃"（AC-1.3 要求）；不抛异常进生成链 |
| 不触发生成 | dry-run 全程不调 `gen_video` / `_submit_video` / `create_video` | 预检输入是**已有的**首尾帧图，无需先生成视频 |

**dry-run 测试路径**（AC-1.5 执行草案，实现阶段执行）：
1. 取真实项目镜 + 真实首尾帧图（例如 experiments 目录已有帧图：`scripts/diag/experiments/ep_0811_145935/shot1_v2/s1_0.png` 作首帧、`s1_5_8.png` 作尾帧；或某 production 项目已生成 kf_start/kf_end 的镜）
2. `python precheck.py --project ... --shot N --first <图> --last <图> --dry-run` → 输出 JSON 报告（含 precheck 状态、素材自检结果）
3. 真视觉验证（可选，用免费 key）：同命令去掉 `--dry-run`，确认能产出 opening/ending verdict + conflicts
4. 报告存 `dev-work/tasks/T-20260813-06/` 下（如 `precheck_dryrun_report.json`），作为 AC-1.5 证据

---

## 4. AC 映射

| AC | 要求 | design 如何满足 |
|---|---|---|
| AC-1.1 | 预检函数：输入单镜 shot + 首尾帧 → 输出 match/warn/fail + 冲突点描述（复用 prompt_frame_match 思路） | `precheck_shot(shot, first, last, prompt)`（§2.1/2.2）：输入 shot dict + 首尾帧路径；复用 `vision_review.prompt_frame_match`（§1.2）输出 opening/ending/overall，并转成 `conflicts[]` 结构化冲突点；verdict 映射 overall→match/warn/fail |
| AC-1.2 | 空镜免检：prompt 含 no people/空景 → 跳过身份审查（标 n/a） | `is_empty_shot(prompt)`（§2.3）口径与生成后检查一致；命中 → `precheck:"n/a"`，跳过视觉 API |
| AC-1.3 | 与生成链解耦：预检不阻塞正常生成（失败=拦截提示，非崩溃）；零 AGNES 额度 dry-run 可测 | 方案 A 独立端点（§2.4）+ CLI 手动触发；`prompt_frame_match` 异常降级 `{ok:false}` 不抛异常；`dry_run=True` 零 API 调用；测试 key 走 `AGNES_TEST_API_KEY`（§3） |
| AC-1.4 | 接入点：生成前自动附加或手动触发（由开发文档定，需主理人确认后再实现） | §2.4 给出方案 A（手动端点，推荐）/方案 B（自动软附加）；推荐 A，**标注待主理人/老板确认**；确认前不实现 |
| AC-1.5 | 证据：用真实项目 shot 跑一次 dry-run 预检，输出报告 | §3 dry-run 测试路径：真实项目 + 真实首尾帧图 → dry-run 报告存 `dev-work/tasks/T-20260813-06/precheck_dryrun_report.json`（实现阶段执行） |

---

## 5. 文件改动边界（哪些要动、哪些不能动）

### 实现阶段要动的（最小集）
| 文件 | 动作 | 说明 |
|---|---|---|
| `short_drama_workflow/scripts/diag/precheck.py` | **新增** | 预检函数 + `is_empty_shot` + CLI dry-run 入口（§2.1） |
| `short_drama_workflow/html_prototype/server.py` | **改（仅方案 A 时）** | 加 `/api/precheck` 路由（仿 `/api/diagnose` 行 4751 写法）；只读 import precheck，不改任何生成函数 |
| `short_drama_workflow/html_prototype/agnes_proxy.py` | **改（仅方案 A 走 8787 时）** | STUDIO_PREFIXES 白名单登记 `/api/precheck`（08 经验库 A 节强制） |
| `short_drama_workflow/html_prototype/studio.html` | **改（可选增强）** | 单镜区加"预检"按钮；PFM 徽标渲染已有（行 713-721），无新 UI 体系 |

### 不能动的（只读复用）
- `short_drama_workflow/scripts/diag/diagnosis.py` —— 只读（`extract_frames_smart` 等）
- `short_drama_workflow/scripts/diag/vision_review.py` —— 只读（`prompt_frame_match` / `review` / `_img_src`）
- `short_drama_workflow/scripts/diag/prompt_training.py` —— 只读（`build_variants`；空镜免检逻辑**抽取**到 precheck 而非改它）
- `short_drama_workflow/scripts/edit/quality_check.py`、`face_qc.py` —— 只读
- **生成链主流程**（`server.py` 的 `video_submit` / `generate_keyframes_real` / `_gen_camera_start` / `_gen_first_frame_fallback` / `create_video` 调用段、`assemble.py`、`agnes_client._submit_video`）—— **不动**（方案 B 实现前不碰；方案 A 完全不碰）

### 本阶段（文档期）已遵守
- 零业务代码、零文件改动（仅新增 design.md）、零 AGNES API 调用

---

## 6. 实现清单（主理人批准后执行，供评审）

1. 新建 `precheck.py`：`is_empty_shot` + `precheck_shot` + `main()`（CLI：`--project/--shot/--first/--last/--prompt/--dry-run`）
2. （方案 A）`server.py` 加 `/api/precheck` + `agnes_proxy.py` 白名单
3. 渲染 prompt 拼接：keyframes 用 `_transition_prompt` 系成品词；reference 用 `_clean_video_prompt + global_style + animate`（只读复用 server 纯函数）
4. AC-1.5：真实项目 shot + 真实首尾帧图跑 dry-run → 输出 `precheck_dryrun_report.json`
5. 回报主理人：design.md 路径 + 实现摘要 + 证据报告

## 7. 风险与备注

- PFM 是 LLM 视觉判定（非确定性阈值），warn/fail 需人工复核；本预检定位为"拦截提示"而非"自动改判"（PRD 边界：只预检不改生成逻辑）
- 空镜关键词目前只收英文（与现有口径一致）；中文关键词扩展列为实现期可选增强，需确认口径避免与生成链不一致
- 若某镜首尾帧未生成（`asset_frame_start/end` 为空），预检返回 warn + "缺首尾帧素材，请先生成关键帧"——不阻断，符合 AC-1.3
