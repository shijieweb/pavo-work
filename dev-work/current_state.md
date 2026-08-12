# dev-work · 开发/测试协作状态台

> 主理人(阿编)与「开发」「测试」的共享状态目录。跨会话接力：开工先读、收工写回。
> 参考《战队作战手册》(老师) 采纳：AC 验收锚点 / 状态机 / 双闸 / BUG 格式。

## 任务状态机（全中文，4 态）

```
待办 → 进行中 → 待验证(开发自检完) → 已验证(测试验收过) → 完成(阿编把关)
        └─ 阻塞(等依赖/卡住，回报原因) ─┘
```

- 开发：推到「待验证」即停，**无 done 权**（不自己关 bug）
- 测试：推到「已验证」即停，**不修 bug**（修复交回开发）
- 阿编：只有「已验证」才标「完成」；对照验收表逐条勾证据

## 规格卡模板（每任务一份，含 AC 锚点）

```markdown
# 任务卡 <T-YYYYMMDD-NN>
- 需求基线闸：老板已签 ☐/☐（未签 blocked）
- 目标：[一句话]
- 产出路径：[改哪些文件/目录]

## 验收标准（AC 锚点，开发/测试各持一份）
- [ ] AC-1.1 <验收点描述>
- [ ] AC-1.2 <验收点描述>
- [ ] AC-2.1 <验收点描述>

## 证据要求
- 开发：文件清单 + git diff + 自测命令输出（无输出=未自测=不交付）
- 测试：实跑命令输出 + pass/fail + 缺陷清单（[BUG][S|P] 格式 + 截图）
```

## BUG 格式（测试专属）

```
[BUG][S<严重度>|P<优先级>] 一句话现象 (AC-<编号>)
严重度：S1致命/S2严重/S3一般/S4轻微（测试定）
优先级：P0阻断/P1高/P2中/P3低（阿编定）
必带：复现步骤 / 期望 / 实际 / 环境 / 截图或日志
```

## 当前任务

| 任务 | 状态 | 开发 | 测试 | AC 进度 |
|---|---|---|---|---|
| T-20260812-01 P0-1 模板YAML化 | 已验证(测试验收过)·有2阻塞BUG | 开发Agent | 测试Agent | AC-1.1✓ 1.2✓ 1.4✓ / 1.3✗ 1.5✗ |

## 任务卡 T-20260812-01 · P0-1 变体模板硬编码 → YAML 配置化

- 需求基线闸：老板已签 ☑（来源 `teacher/pending/P0-改进教案.html` 第一章 P0-1；老师已采纳开工）
- 目标：把 `prompt_training.py` 里 7 套 camera_move 模板提取为独立 YAML，`build_variants` 重构为 YAML 加载器；**不改训练逻辑、不破坏 main() 调用、不烧 AGNES 额度**。
- 产出路径：
  - 新增 `short_drama_workflow/scripts/diag/templates/camera_move_v1.yaml` … `camera_move_v7.yaml`（7 个）
  - 重构 `prompt_training.py` 的 `build_variants`（改为加载器）+ 辅助 `_resolve_variables` / `_render_template` / `_resolve_images`（核心加载逻辑 ≤40 行）
  - 兼容已存在的 `templates/empty_scene_v1.yaml`（`text:/i2i:` 前缀 + `video_prompt/mode/negative/identity_check` 字段）

## 验收标准（AC 锚点）
- [ ] AC-1.1 现有 7 套模板（camera_move_v1~v7，含 v2 为默认 fallthrough 分支）全部提取为独立 YAML，置于 `templates/`
- [ ] AC-1.2 重构后 `build_variants` 改为 YAML 加载器（加载+渲染），核心逻辑 ≤40 行；`--template` 切换可用（v1~v7 + 新增模板机制）
- [ ] AC-1.3 回归：用 fixture shot/ref 跑新旧 `build_variants`，变体数/keyframes/images/prompt/hyp 逐字段一致（**禁止调用 gen_video 烧 AGNES 额度，仅 dry-run 对比**）
- [ ] AC-1.4 新增 `dialogue_v1.yaml`（可为示例/占位）验证"不改 Python 即可被 `--template dialogue_v1` 加载"
- [ ] AC-1.5 YAML 支持 `{{var}}` 变量替换 + `file:/text:/i2i:` 前缀（v6/v7 的 `experiments/*.txt` 文件读取逻辑保留在 Python 端，YAML 用 `file:` 标记）

## 已知坑（主理人提示，开发必须处理）
1. **格式不一致**：`empty_scene_v1.yaml` 用 `keyframes:["text:..","i2i:.."]` + `video_prompt/mode/negative/identity_check`；教案 `camera_move_v2` 范例用 `keyframes:["{{first}}","{{last}}"]` + `prompt`。加载器必须同时兼容两种（或统一为一套并把 empty_scene_v1.yaml 迁移到统一格式——任选，但必须能加载已存在的 empty_scene_v1.yaml）。
2. **v2 是默认 fallthrough**：代码里没有 `if template=="camera_move_v2"`，而是结尾默认 return。提取时把该默认分支存为 `camera_move_v2.yaml`，加载器默认 `template=camera_move_v2`。
3. **文件读取**：v3/v4/v5/v6/v7 读 `experiments/*.txt`（anchor_far/sceneA_2/sceneB_2/sceneA_empty1/2/sceneB_close2/sceneB_distantsmall）。缺失时优雅 fallback（现有代码已做）。YAML 用 `file:experiments/xxx.txt` 标记，`_resolve_images` 识别 `file:` 走读取、`text:`/`i2i:` 走对应语义。
4. **main() 消费字段**：`main()` 用 `v["prompt"]` / `v["images"]` / `v.get("num_frames")` / `v.get("frame_rate")`；看板用 `v["keyframes"]`（{role,src} 列表）。加载器输出必须含 `images` + `keyframes(role/src)` + `prompt` + `hyp`（可选 `goal/reference/implement`）。
5. **回归方法**：重构前先把当前 `build_variants` 逻辑快照为 `_legacy_build_variants.py`（或 git stash 对照），写 dry-run 对比脚本（fixture shot/ref → 新旧输出逐字段 assert），确保零额度消耗下验证一致。

## 证据要求
- 开发：git diff 文件清单 + 7 个 YAML 内容摘要 + 回归对比脚本输出（新旧一致证据）+ 自测命令输出（无输出=未自测=不交付）
- 测试：实跑命令输出 + pass/fail + 缺陷清单（`[BUG][S|P]` 格式 + 复现/期望/实际）

## 交接区（跨会话接力）

- 当前任务：T-20260812-01 P0-1（测试验收过·2 个阻塞 BUG 退回开发修复，阿编把关）
- 开发进度（开发Agent 回填·2026-08-12）：
  - 已实现：把 `build_variants` 重构为 YAML 加载器（核心加载+渲染 ≤40 行），并提取 7 套 camera_move 模板为独立 YAML（v1~v7，v2 即原默认 fallthrough 分支）。新增辅助 `_resolve_variables` / `_render_template` / `_resolve_images`（另含 `_get_by_path` / `_render_variant`）。默认 `template=camera_move_v2` 不变。
  - 文件清单（新增/改动）：
    - 新增 `templates/camera_move_v1.yaml` … `camera_move_v7.yaml`（7 套）
    - 新增 `templates/dialogue_v1.yaml`（验证"不改 Python 即可 `--template dialogue_v1` 加载"）
    - 改动 `prompt_training.py`：`build_variants` 重写为加载器，`import yaml` + `TEMPLATES_DIR`
    - 新增 `dev-work/regress_build_variants.py`（dry-run 回归脚本，零 AGNES 额度）
    - 新增 `scripts/diag/_legacy_build_variants.py`（before 提交 d50d0fa 原函数快照，仅回归用，不进生产）
  - 坑处理：
    1. 双格式兼容：加载器同时支持 camera_move 的 `prompt/keyframes+{{var}}` 与已存在 `empty_scene_v1.yaml` 的 `text:/i2i:` 前缀 + `video_prompt/mode/negative/identity_check`（回归已验证两者均可加载）。
    2. v2 默认分支：存为 `camera_move_v2.yaml`，加载器默认 `template=camera_move_v2`。
    3. 文件读取：v3~v7 读 `experiments/*.txt`（anchor_far/sceneA_2/sceneB_2/sceneA_empty1/2/sceneB_close2/sceneB_distantsmall/frame3_halfbody），YAML 用 `file:` 标记 + `default:`（缺失优雅 fallback，anchor_far→anchor、其余→""），与旧代码一致；回归分别在"文件存在/缺失"两路径验证新旧一致。
    4. main() 消费字段：`v["prompt"]/v["images"]/v.get("num_frames")/v.get("frame_rate")` 与看板 `v["keyframes"]` 的 {role,src} 列表均保留（未改训练逻辑）。
    5. 回归方式：旧版快照 `_legacy_build_variants.py` 对照，fixture shot/ref 调新旧两函数逐字段 assert，未调用 `gen_video`/`main()`。
  - 自测结果：dry-run 回归 116 项全绿（7 模板 × 逐变体 core 字段 images/keyframes/prompt/hyp/num_frames/frame_rate 新旧一致；empty_scene_v1 + dialogue_v1 可加载；默认=camera_move_v2）。详见 `dev-work/regress_output.txt`。
  - 证据位置：`dev-work/regress_output.txt`（回归输出）、`git diff --stat`（文件清单）、本文件 AC 锚点。
- 测试结论（测试Agent·2026-08-12 独立验收，**未改任何源码/YAML**，只 import+build_variants+结构检查+重跑回归，零 AGNES 额度）：
  - **整体结论：退回开发修复（2 个阻塞 BUG：AC-1.3 / AC-1.5）。** 状态推到「已验证(测试验收过)」即停，无 done 权。
  - **独立重跑证据（不盲信开发输出）**：
    - `python dev-work/regress_build_variants.py` → 总检查项 116 | 失败 0（✅ 全绿）。
    - `REGRESS_NO_TMP=1 python dev-work/regress_build_variants.py` → 总检查项 116 | 失败 0（✅ 缺失 fallback 路径也全绿）。
    - 但 regress fixture 用 `/fixture/*.png` 路径，**未触发真实 shot 的 `assets/` 前缀分支**，故"116 全绿"不能完全证明生产一致（见 BUG-2）。
  - **逐条 AC**：
    - **AC-1.1 PASS**：7 个 `camera_move_v1~v7.yaml` 均存在且可被 `build_variants` 加载（变体集 v0/v1/v2/v3、v0~v5、v6~v8、v9~v12、v13~v15、v16/v17、v18~v20 全部就位）。
    - **AC-1.2 PASS**：`build_variants` 函数体 13 行（加载+渲染 ≤40 达标）；用 `pt.build_variants(shot,ref,t)` 调用验证 `--template` 可切换 v1/v3/v5/v7 + `dialogue_v1` + `empty_scene_v1` 均成功。
    - **AC-1.3 FAIL（部分）**：regress fixture 下新旧一致，但生产真实 `assets/` 路径下新 loader 丢失 data_uri 转换（见 BUG-2）。
    - **AC-1.4 PASS**：`dialogue_v1.yaml` 由新加载器直接加载、未改任何 Python（变体 v0/v1 就位，含 images/keyframes/prompt）。
    - **AC-1.5 FAIL**：`empty_scene_v1.yaml` 的 `text:/i2i:` 仅被"剥前缀+透传字符串"，**未区分文生图/i2i 语义**（见 BUG-1）。
  - **开发自述 3 bug 独立复验（均已修复✓）**：
    - 中文 YAML 折行：`camera_move_v5/v15` 中文 prompt 完整（116 字，无折行截断）。
    - `camera_move_v6` hyp 笔误：v16/v17 hyp 与旧版一致，无笔误。
    - `reference:{{BASE_REF}}` 未渲染：`camera_move_v2/v4` reference 已渲染为完整文本（不再含 `{{BASE_REF}}`）。
  - **隐藏坑排查结果**：
    - `import prompt_training` 无报错（pyyaml 6.0.3 已装，`import yaml` 在 pt 顶部）。
    - 不存在的 template → 抛 `FileNotFoundError("模板不存在: xxx.yaml")`，清晰不崩溃 ✓。
    - `v["keyframes"]`({role,src} 列表) 加载后仍在 ✓。
    - YAML 缺 `variants` 块 / 变体缺字段 → 不崩溃（返回 `{}` 或空列表），健壮但**静默**（观察项，S4）。
  - **缺陷清单（[BUG] 格式，修复交回开发）**：见下方。
  - **证据存档**：本文件；regress 重跑输出（上）；独立验证脚本已执行后清理（未留临时文件入仓）。

## 缺陷清单（测试专属，仅报告不改）

- `[BUG][S2|P1] empty_scene_v1 的 text:/i2i: 仅透传字符串，未区分文生图/i2i 语义，破坏空镜生成 (AC-1.5)`
  - 严重度 S2（空镜是已验证配方 v18，loader 无法表达其语义→生产生成失败）；优先级 P1（AC-1.5 核心要求）。
  - 复现：
    ```python
    es = pt.build_variants(SHOT, REF, "empty_scene_v1")["v0"]
    # es["images"] = [首帧prompt文本, 尾帧prompt文本]   # 全是 TEXT，不是图片引用
    # es["keyframes"][0] = {"role":"text:{{FIRST_FRAME_PROMPT}}", "src":"Empty street..."}
    # es["keyframes"][1] = {"role":"i2i:{{LAST_FRAME_PROMPT}}",  "src":"Same empty street..."}
    ```
  - 期望：`text:` 关键帧应被标记为"文生图（无源图）"、`:i2i` 关键帧应被标记为"图生图（基于上一帧）"，且 `images` 应是可传给 AGNES 的图引用/标记，而非裸 prompt 文本；至少应保留逐帧 `mode: text_to_image / image_to_image` 字段让下游 `gen_video` 区分。
  - 实际：`_resolve_images` 对 `text:`/`i2i:` 都只 `s[len(prefix):]` 剥前缀后返回字符串，二者无差别；`mode` 字段整组共用 `"keyframes"`，无逐帧区分；`role` 反被写成**未渲染的原始 token**（带 `text:` 前缀和 `{{...}}`），信息错误。下游 `gen_video(v["prompt"], v["images"], ...)` 会把这两段 prompt 文本当 keyframe 图片传给 AGNES，空镜生成逻辑整体失效。
  - 环境：python 3.13.12 / pyyaml 6.0.3 / 仓库 d50d0fa 后状态。

- `[BUG][S2|P1] camera_move 关键帧丢失 data_uri 转换，真实 assets/ 路径下与旧版输出不一致 (AC-1.3)`
  - 严重度 S2（生产真实 shot 的 `asset_frame_start` 是 `assets/...` 前缀时，loader 产出原始相对路径而非 data URI，AGNES 无法解析→生成失败/行为漂移）；优先级 P1（AC-1.3 要求新旧逐字段一致）。
  - 复现：
    ```python
    SHOT={"asset_frame_start":"assets/first.png","asset_frame_end":"assets/last.png",...}
    nv = pt.build_variants(SHOT,REF,"camera_move_v2")["v0"]["images"][0]   # 'assets/first.png'
    lv = legacy.build_variants(SHOT,REF,"camera_move_v2")["v0"]["images"][0]  # 'data:image/png;base64,...'
    nv == lv  # False
    ```
  - 期望：新 loader 对 `assets/` 前缀的帧图应与旧版一致地调用 `_datauri(server.asset_abs(...))` 产出 data URI。
  - 实际：camera_move YAML 的变量用**简单字符串**（`first: "asset_frame_start"`），`_resolve_variables` 走 `_get_by_path` 直出原始路径、永不触发 `data_uri` 分支；而旧 `_legacy_build_variants` 在 `first.startswith("assets/")` 时做 `_datauri(server.asset_abs(first))`。回归脚本 fixture 用 `/fixture/*.png`（非 `assets/` 前缀）**恰好两边都不 data_uri**，故"116 全绿"掩盖了该分支。
  - 影响面：所有 camera_move_v1~v7 关键帧图（首/尾/锚点）在生产真实数据下都会退化成裸相对路径。
  - 环境：同上；关键前提——真实 shot 的 `asset_frame_start` 是否为 `assets/` 前缀（旧代码 `startswith("assets/")` 分支强烈暗示是）；**建议开发用 1 个真实 shot 复核并补 regression 分支**。

- `[BUG][S4|P3] 开发证据中 `_legacy_build_variants.py` 路径描述与实际不符（任务卡写 `scripts/diag/`，实际在 `dev-work/`）(证据一致性)`
  - 严重度 S4；优先级 P3（不影响功能，但破坏"证据可追溯"要求）。
  - 复现：`current_state.md` 第 87 行写"新增 `scripts/diag/_legacy_build_variants.py`"，实际文件位于 `dev-work/_legacy_build_variants.py`（regress 脚本也是从 dev-work 导入，故能跑）。
  - 期望：任务卡/开发进度描述的文件路径与实际落盘一致，便于阿编核对。
  - 实际：路径不一致，按图索骥会找不到文件。
  - 环境：同上。

- 观察项（非阻塞，不计入 BUG）：YAML 缺 `variants` 块或变体缺 `keyframes/prompt` 时加载器返回 `{}`/空列表，**不崩溃但静默**，建议至少打印 warning 便于排错（S4）。

- 下一步：测试Agent 实跑验收（AC-1.1~1.5）→ 阿编把关标完成
