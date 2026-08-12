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
| T-20260812-01 P0-1 模板YAML化 | 进行中(开发接手) | 开发Agent | 测试Agent | AC-1.1~1.5 待实现 |

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

- 当前任务：T-20260812-01 P0-1（开发接手）
- 开发进度：（开发Agent填写）
- 测试结论：（测试Agent填写）
- 下一步：开发实现 → 测试验收 → 阿编把关
