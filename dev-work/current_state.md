# dev-work · 开发/测试协作状态台

> 主理人(阿编)与「开发」「测试」的共享状态目录。跨会话接力：开工先读、收工写回。  
> **控制框架（2026-08-12 制度化）**：
> - 宪法：`dev-work/运行手册.md`（阿编调度唯一操作宪法，含三道人闸/四文档/5态/证据铁律/分层测试 L0-L1-L2/DoD）
> - 标准表单：`dev-work/templates/TEMPLATE_{PRD,DESIGN,TEST,ACCEPTANCE,BUG}.md`（派活强制按模板填）
> - 每任务四文档：`dev-work/tasks/<T-ID>/{PRD,design,test,acceptance}.md`（拒绝全塞一文件→失控）
> 参考《战队作战手册》(老师) 采纳：AC 验收锚点 / 状态机 / 双闸 / BUG 格式。

## 📮 旧窗口留言板（2026-08-13 02:11 · 主理人前任留言，接手必读）

1. **我只写文档、提意见、分析，不碰任何代码**——代码改动一律由团队自己落地（老板指令 02:11）。
2. **T-20260813-02「8787 统一网关路由注册表收敛」规格卡已备好**：`dev-work/tasks/T-20260813-02/PRD.md`（≤30 行，AC 锚点 + 边界齐全）。**l1_smoke 收尾后自取开卡**，走 GATE0 + 闸1；动 `agnes_proxy.py` 前 `git commit before:`。
3. **验收提醒（针对 l1_smoke 返工）**：`l1_smoke.run.log` 目前仍停在 **01:54 失败版**（`FileNotFoundError: html_prototype\server.py`），真跑通过后**务必覆盖/追加成功日志**，否则验收者第一眼会误判最新状态（旧窗口就差点看错）。AC 重点验：入口 assert `mode=="test"` 守卫生效、data_uri 真覆盖、零 VIP、真出片证据（last_url + curl 200）。
4. 留言回复方式：在本节追加一行即可，旧窗口/老板可读。

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

| 任务                         | 状态                    | 开发      | 测试      | AC 进度                       |
| -------------------------- | --------------------- | ------- | ------- | --------------------------- |
| T-20260812-01 P0-1 模板YAML化 | ✅ 完成(阿编把关·2026-08-12) | 开发Agent | 测试Agent | AC-1.1✓ 1.2✓ 1.3✓ 1.4✓ 1.5✓ |
| T-20260812-02 L1 真·管线冒烟(免费KEY验证P0-1) | ✅ 完成(阿编把关·2026-08-12) | — | 测试Agent | AC-1.1✓ 1.2✓ 1.3✓ 1.4✓ 1.5✓ |
| T-20260812-03 运维脚本工作流(不建角色·固化脚本) | ✅ 完成(主理人把关·2026-08-12) | 开发Agent | 测试Agent | AC-1.1✓ 1.2✓ 1.3✓ 1.4✓ 1.5✓ 1.6✓ |
| T-20260812-04 框架加固 R1/R2/R3 + v4锚 + 改进文档 | ✅ 完成(主理人把关·2026-08-12) | — | — | 白名单硬卡/强制审计/WIP/v4锚/改进手册 |
| T-20260812-05 O4 check_wip.ps1 WIP机械检查 | ✅ 完成(主理人把关·2026-08-13) | 主理人接手(Agent异常) | 主理人实证 | AC-1.1✓ 1.2✓ 1.3✓ 1.4✓ 1.5✓ 1.6✓ |

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
    - 新增 `dev-work/_legacy_build_variants.py`（before 提交 d50d0fa 原函数快照，仅回归用，不进生产；注意：此前开发进度误写为 `scripts/diag/_legacy_build_variants.py`，实际落盘在 `dev-work/`，此处更正，对应 BUG-3 路径一致性）
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
    - **AC-1.1 PASS**：7 个 `camera_move_v1~v7.yaml` 均存在且可被 `build_variants` 加载（变体集 v0/v1/v2/v3、v0~~v5、v6~~v8、v9~~v12、v13~~v15、v16/v17、v18~v20 全部就位）。
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
- `[BUG][S4|P3] 开发证据中 `\_legacy_build_variants.py`路径描述与实际不符（任务卡写`scripts/diag/`，实际在 `dev-work/`）(证据一致性)`
  - 严重度 S4；优先级 P3（不影响功能，但破坏"证据可追溯"要求）。
  - 复现：`current_state.md` 第 87 行写"新增 `scripts/diag/_legacy_build_variants.py`"，实际文件位于 `dev-work/_legacy_build_variants.py`（regress 脚本也是从 dev-work 导入，故能跑）。
  - 期望：任务卡/开发进度描述的文件路径与实际落盘一致，便于阿编核对。
  - 实际：路径不一致，按图索骥会找不到文件。
  - 环境：同上。
- 观察项（非阻塞，不计入 BUG）：YAML 缺 `variants` 块或变体缺 `keyframes/prompt` 时加载器返回 `{}`/空列表，**不崩溃但静默**，建议至少打印 warning 便于排错（S4）。
- 下一步：测试Agent 实跑验收（AC-1.1~1.5）→ 阿编把关标完成

---

## 开发进度·BUG 修复回填（开发Agent·2026-08-12 二轮，接「退回开发修复」）

状态机：`已验证(测试验收过)·有2阻塞BUG` → `待验证(开发自检完)`（无 done 权，待测试复核）。

### 修了什么

1. **[BUG-1 S2|P1] empty_scene_v1 text:/i2i: 未区分文生图/i2i 语义（AC-1.5）**
   - 根因：`_resolve_images` 对 `text:`/`i2i:` 一律只剥前缀返回裸 prompt 文本；`_render_variant` 又把未渲染的 token 直接当 `keyframes.role`（带 `text:` 前缀+`{{...}}` 未渲染）。
   - 修复（`prompt_training.py`）：
     - `_resolve_images` 重写为结构化返回 `{"mode", "raw"}`：`text:`→`text_to_image`（首帧文生图无源图）、`i2i:`→`image_to_image`（尾帧图生图）、`file:`→`file`、`{{var}}`/字面量→`image`（兼容 camera_move 的 `{{first}}/{{last}}/{{anchor}}`）。
     - `_render_variant`：`text_to_image`/`image_to_image` 帧的 `images` 元素为 `{"mode":..., "content":...}` dict（逐帧明确生成方式标记）；`keyframes` 的 `role` 渲染为干净中文标签「文生图(无源图)」/「图生图(基于上一帧)」、`src` 为渲染后的干净 prompt 文本（去掉 `text:`/`i2i:` 前缀、无未渲染 token）。
     - `gen_video` 增加结构化关键帧兼容：遇 dict 取 `content` 提交，字符串帧不变（向后兼容，下游可据 `mode` 区分首帧文生图/尾帧 i2i）。
2. **[BUG-2 S2|P1] camera_move 关键帧丢失 data_uri 转换（AC-1.3）**
   - 根因：camera_move YAML 用字符串变量（`first:"asset_frame_start"`），`_resolve_variables` 走 `_get_by_path` 直出原始路径，从不触发 `data_uri`；旧版在 `startswith("assets/")` 时做 `_datauri(server.asset_abs(first))`。回归 fixture 用 `/fixture` 路径恰好两边都无 datauri，掩盖分支。
   - 修复（`prompt_training.py` `_render_variant`）：`images` 收集时对 `image` 模式且内容以 `assets/` 开头的帧图，复刻旧版 `_datauri(server.asset_abs(...))` 转 data URI；`keyframes.src` 保持原始路径（与旧版看板展示一致）。camera_move 系列真实 `assets/` 帧图现与旧版逐字段一致。
3. **[BUG-3 S4|P3] 证据路径描述不符** — 开发进度中 `_legacy_build_variants.py` 路径由误写的 `scripts/diag/` 更正为实际落盘位置 `dev-work/`（见上方文件清单行）。

### 新回归分支（dev-work/regress_build_variants.py）

- **BUG-2 分支（第 5 节）**：用真实 `asset_frame_start:"assets/first.png"`（非 `assets/` 的 `asset_frame_end` 保持与旧版「仅 first 帧 datauri」语义对齐）的 shot，对 camera_move_v1~v7 逐变体比对新/旧 `images`/`keyframes`/`prompt`，并断言新 loader 不产生裸 `assets/` 路径。覆盖此前被 fixture 掩盖的 data_uri 分支。
- **empty_scene 语义校验（第 3 节）**：断言 v0 `images` 首帧 `mode==text_to_image`、尾帧 `mode==image_to_image` 且每帧含 `content`；`keyframes` 的 role/src 无 `text:`/`i2i:`/`{{` 残留，role 标明文生图/图生图，src 渲染为干净 prompt 文本。
- `_datauri` 桩：`pt._datauri`/`legacy._datauri` 均替换为确定性伪 data URI（不读真实文件），保证新旧可比、零额度。

### 自测结果（零额度，仅 import + build_variants + 回归）

- `python dev-work/regress_build_variants.py` → 总检查项 **200** | 失败 **0** ✅（含 7 模板×变体核心字段、empty_scene 语义、dialogue_v1、默认=camera_move_v2、新增 assets/ data_uri 分支）。
- `REGRESS_NO_TMP=1 python dev-work/regress_build_variants.py` → 总检查项 **200** | 失败 **0** ✅（缺失 fallback 路径也全绿）。
- 独立复现测试原始断言：BUG-1 `es["images"][0].mode=="text_to_image"` 且 `keyframes[0].role` 无前缀/`{{`；BUG-2 新 loader `images[0]==legacy images[0]==data:image/png;base64,...`（用伪 datauri 等价比对）→ 两 BUG 复现断言均不再触发。
- 未调用 `gen_video`/`main()`，未烧 AGNES 额度。

### 遗留

- 无功能遗留。说明一处语义取舍：BUG-2 修复按「旧版仅对 `asset_frame_start`（首帧）做 datauri」复刻，故回归 shot 的 `asset_frame_end` 用非 `assets/` 路径以与旧版逐字段相等；若生产真实 `asset_frame_end` 也带 `assets/` 前缀，新 loader 会一并转 data URI（比旧版更完整，但与该边缘情形下的旧版输出会有差异——属旧版自身不一致，不在本次 AC 范围内）。
- 观察项（非阻塞，沿用测试建议）：YAML 缺 `variants` 块或变体缺字段时加载器返回 `{}`/空列表不崩溃但静默，建议后续加 warning 便于排错。

## 测试结论·独立复验（测试Agent·2026-08-12 二轮，接「开发修复后重测」）

> 角色：测试（独立验收者），**只验收、绝不改代码**。方法：仅 `import` + `build_variants` + 回归脚本 + 结构检查，**未调用 `gen_video`/`main()`**，零 AGNES 额度。临时验证脚本均置于 `/tmp`（不入仓），复验后工作树干净（`git status` 无未提交改动）。

- **整体结论：建议 阿编 放行（状态推到「已验证(测试验收过)」即停，无 done 权）。** 2 个阻塞 BUG（BUG-1 / BUG-2）经独立复验**确认已真修好**；回归分支经"修复前必失败"证明**有效**；AC-1.1~1.5 全部 PASS。唯一遗留为非阻塞 S4（静默返回，见下）。
- **环境**：python 3.13.12 / pyyaml 6.0.3；before 快照 `3946e95`，fix 提交 `9d0fb01`。

### 1) 重跑回归（不盲信开发输出）

- `python dev-work/regress_build_variants.py` → **总检查项 200 | 失败 0** ✅。
- `REGRESS_NO_TMP=1 python dev-work/regress_build_variants.py`（文件缺失 fallback 路径）→ **总检查项 200 | 失败 0** ✅。
- 说明：本次 regression 第 5 节已用真实 `asset_frame_start="assets/first.png"` 触发 data_uri 分支（不再像首轮那样被 `/fixture` 路径掩盖），故"200 全绿"对生产真实 assets/ 路径有效。

### 2) BUG-1 复验（empty_scene text:/i2i: 语义）—— PASS（修复前 FAIL / 修复后 PASS）

- 独立构造 `es = pt.build_variants(SHOT, REF, "empty_scene_v1")["v0"]`：
  - ✅ `images[0]` 为 dict 且 `mode=="text_to_image"`（首帧文生图）、`images[1]` 为 dict 且 `mode=="image_to_image"`（尾帧图生图），每帧含 `content`；
  - ✅ `keyframes[0].role=="文生图(无源图)"`、`keyframes[1].role=="图生图(基于上一帧)"`；
  - ✅ `keyframes[0/1].src` 为干净中文 prompt（`Empty street...` / `Same empty street...`），无 `text:`/`i2i:`/`{{` 残留；
  - ✅ 不再是"裸 prompt 字符串透传"（`images` 元素为带 mode 的结构化 dict，非裸 str）。
- **分支真实性（修复前必失败）**：临时 `git checkout 3946e95 -- prompt_training.py` 后重跑回归，脚本在 empty_scene 语义校验处直接 `AttributeError: 'str' object has no attribute 'get'`（修复前 `images[0]` 是裸字符串）→ 证明第 3 节断言**真能抓到 bug**；恢复 `9d0fb01` 后复跑仍 200/0。

### 3) BUG-2 复验（camera_move assets/ data_uri）—— PASS（修复前 FAIL / 修复后 PASS）

- 独立构造真实 `ASSET_SHOT={"asset_frame_start":"assets/first.png","asset_frame_end":"/fixture/last.png"}`，对 `camera_move_v1~v7` 调 `build_variants`，与 `_legacy_build_variants` 旧版逐字段比对：
  - ✅ 全部变体 `images`/`keyframes`/`prompt` 新旧**完全相等**；
  - ✅ `images` 中 `assets/` 开头的帧图均被转为 `data:image/...;base64,...`，**无裸 `assets/` 路径残留**；
  - ✅ 首帧 `assets/first.png` 已转 data URI（复刻旧版 `_datauri(server.asset_abs(...))`）。
- **分支真实性（修复前必失败）**：在 `3946e95` 版本上单独跑 assets/ 比对，新 loader 产出裸 `'assets/first.png'`、旧版产出 `'data:image/png;base64,STUB_assets/first.png'`，`nv != lv` 且"裸路径"断言同时触发（camera_move_v1~v7 全中）→ 证明第 5 节断言**真能抓到 bug**。
- 边缘观察（非 bug，沿用开发说明）：若生产 `asset_frame_end` 也带 `assets/` 前缀，新 loader 会一并转 data URI（比旧版"仅首帧转"更完整），与该边缘下的旧版输出会**不等**——属旧版自身不一致，不在 AC-1.3 逐字段相等范围内。

### 4) 新增回归分支真实性核查——通过

- 第 3 节（empty_scene 语义）确有断言：`images[0].get("mode")=="text_to_image"`（L140）、`images[1].get("mode")=="image_to_image"`（L142）、`keyframes` 无 `text:/i2i:/{{` 残留、`role` 标明文生图/图生图。
- 第 5 节（assets/ 分支）确有断言：逐变体 `nv==lv` 比对 + 循环断言"无裸 `assets/` 路径"（L199）。
- 两者均在 `3946e95`（修复前）实际失败、在 `9d0fb01`（修复后）通过 → **分支有效，非空跑**。

### 5) AC 复扫（独立脚本逐条确认）

- **AC-1.1 PASS**：`camera_move_v1~v7.yaml` 全部存在且可加载（变体集 v0/v1/v2/v3、v0~~v5、v6~~v8、v9~~v12、v13~~v15、v16/v17、v18~v20 就位）。
- **AC-1.2 PASS**：`build_variants` 函数体约 12 行（≤40 达标）；`--template` 切换 `camera_move_v1/v3/v5/v7` + `dialogue_v1` + `empty_scene_v1` 均成功。
- **AC-1.3 PASS**：真实 `assets/` 路径下新 loader 与旧版逐字段一致（200 项回归 + 独立逐变体比对双重确认）。
- **AC-1.4 PASS**：`dialogue_v1.yaml` 由加载器直接加载、未改任何 Python（变体 v0/v1 含 images/keyframes/prompt）。
- **AC-1.5 PASS**：`{{var}}` 渲染无 `{{` 残留；`text:/i2i:` 区分文生图/图生图语义；`file:` 标记正确读取 `experiments/*.txt` 且缺失优雅 fallback（独立抽查 `_resolve_images("file:experiments/xxx.txt")` 通过）。

### 6) 回归残留观察（S4 结论）

- 独立确认：`build_variants` 对缺 `variants` 块返回 `{}`、变体缺 `keyframes/prompt` 时 `_render_variant` 返回空结构（`images:[]/keyframes:[]/prompt:""`），**不崩溃但静默**。
- **判断**：功能不受影响（非阻塞），但该静默行为在 YAML 拼错字段名时会让 `main()` 静默产出 0 视频、难以排错。沿用此前建议，正式提 **S4 BUG**（见下方缺陷清单）。

### 7) 缺陷清单（测试专属，仅报告不改）

- ~~`[BUG][S2|P1] empty_scene_v1 text:/i2i: 未区分文生图/i2i 语义`~~ **已修复（二轮复验 PASS）**——关闭。
- ~~`[BUG][S2|P1] camera_move 关键帧丢失 data_uri 转换`~~ **已修复（二轮复验 PASS）**——关闭。
- ~~`[BUG][S4|P3] 证据路径描述不符`~~ **已修复**——开发进度已更正为实际落盘位置 `dev-work/_legacy_build_variants.py`，复验确认文件确实在该路径且回归可正常导入——关闭。
- `[BUG][S4|P3] YAML 缺 variants/字段时加载器静默返回 {} / 空列表，无 warning（回归残留观察项）`
  - 严重度 S4（不崩溃、不影响现有功能）；优先级 P3（非阻塞，建议后续加 warning 便于排错）。
  - 复现：`build_variants` 在 `tpl.get("variants")` 为空或变体缺 `keyframes/prompt` 时返回 `{}`/空结构，`main()` 将静默跑出 0 视频。
  - 期望：至少打印 warning（如 `print("⚠ 模板 %s 无 variants/字段缺失，产出空变体集" % template)`）便于配置错误时快速定位。
  - 实际：当前静默返回，无提示。
  - 环境：python 3.13.12 / 仓库 9d0fb01。

### 8) 下一步

- 阿编把关：对照本验收表逐条勾证据，确认无误后由阿编将状态机从「已验证(测试验收过)」推进到「完成」。
- 可选：将上述 S4 warning 项交开发在后续迭代补上（非本次放行阻塞项）。

---

## 阿编把关结论（主理人·2026-08-12，切换 Hunyuan Hy3 后首测）

- **放行决定：✅ 放行（完成）**。AC-1.1~1.5 全部 PASS，2 个阻塞 BUG 经测试复验确认真修好。
- **主理人亲自复验证据**：用 `C:/Users/67972/.workbuddy/binaries/python/versions/3.13.12/python.exe` 重跑 `dev-work/regress_build_variants.py`，正常路径与 `REGRESS_NO_TMP=1` 缺失 fallback 路径均 **200 项 / 失败 0**，含 `assets/` data_uri 分支与 empty_scene 语义分支（修复前在 `3946e95` 上会失败，证明分支有效）。零 AGNES 额度。
- **闭环是否跑通（本次核心测试目标）**：✅ 跑通。完整走完 开发实现 → 测试独立抓 BUG → 开发修复 → 测试复验 PASS → 主理人把关 五步，且测试确实独立抓出了开发自己 116 项回归没暴露的 2 个生产级 BUG（回归 fixture 掩盖），正是双角色闭环存在的价值。
- **Hy3 模型表现（老板关切）**：开发/测试两个角色在 Hunyuan Hy3 下工作正常——能读懂任务卡、写代码、跑 dry-run 测试、按 `[BUG][S|P]` 格式报缺陷、遵守状态机权限（开发不标完成、测试不修码）。未观察到模型相关异常或上下文丢失。
- **本次发现的问题（已闭环）**：
  1. `[已修] empty_scene_v1` 的 `text:/i2i:` 仅透传字符串、未区分文生图/i2i 语义 → 空镜生成失效。
  2. `[已修] camera_move` 真实 `assets/` 路径下丢失 data_uri 转换 → 生产数据下 AGNES 收不到图。
  3. `[已修] 开发证据路径描述不符`（S4）。
  4. `[遗留·S4·非阻塞] YAML 缺 variants/字段时加载器静默返回，建议加 warning`——建议后续迭代补，不阻塞本次。
- **下一步建议**：S4 warning 项可开新任务卡交开发补；P0-1 完成后可推进 P0-2（图视冲突预检）/ P0-4（跨 seed 一致性），二者依赖 P0-1 的 YAML 模板机制。

---

## 待办 Backlog（跨任务，不丢）

- **[S4·P3·非阻塞]** P0-1 遗留：YAML 缺 `variants`/字段时加载器静默返回 `{}`/空列表，建议加 warning 便于排错。→ 可开小任务卡交开发补（不阻塞主线）。

## 挂起状态清单（老板 2026-08-13 19:57 拍板·不做不排期）

> 分析师 UI 建议中明确**不做**的项，登记在此备查；何时启动作废此清单决定。

- **[挂起·主题]** 看板暗色主题统一（#6 视觉 P0：看板亮/门户暗主题割裂）——范围大，不做。
- **[挂起·搜索]** 看板按状态筛选（#5 P1-5：进行中/待办/完成筛选）——不做。
- **[挂起·保存]** 保存成功反馈 toast / 启动超时静默提示（#6 P1）——不做。
- **[挂起·其他 UI]** #5 P2（操作日志 20 条→加载更多、任务卡片显示子任务数）、#6 其余 P1/P2——累积待排期。
- **[框架·2026-08-12 已建]** 控制框架制度化：运行手册 + 5 模板 + 四文档分离 + 分层测试 L0/L1/L2（L1 用免费KEY 真测）。首个示范任务 = `tasks/T-20260812-02`（待闸1）。
- **[提醒·老板]** 免费KEY（`AGNES_TEST_API_KEY`）无限额度仅排队，真测必用、不占 VIP——已写入运行手册 §8，勿再忘。

---

## 阿编把关结论（主理人·2026-08-12，L1 免费KEY 真测收尾）

- **放行决定：✅ 放行（完成）**。AC-1.1~1.5 全部 PASS，经主理人独立复验。
- **主理人亲自复验证据**：
  1. 成片 URL `curl -sI` → `HTTP/1.1 200 OK / Content-Type: video/mp4`（真实视频可达，非编造）。
  2. `git status` → `prompt_training.py` / `templates/*.yaml` 零改动，测试严守"只验证不改码"。
  3. 测试发现的 `agnes_client.use_test()` 文档坑（实为 `_pool.use_test()`）已在 `主理人守则.md` G0-5 / I-2 两处更正。
- **本任务核心价值（回应老板"别再忘免费KEY"）**：P0-1 重构后首次在**真实 AGNES 免费KEY** 端到端跑通——关键帧 `data_uri` 修复（BUG-2）在真实 `assets/` 数据路径下确认生效，`images_to_video` 真实提交→轮询→取回成片，**全程零 VIP 额度**，排队约 97s（免费KEY 仅排队，符合预期）。
- **优化落地建议（已记 MEMORY）**：将 `l1_smoke.py` 固化进回归套件，今后 P0 改动自动跑 L1；脚本内加 `assert key_pool_status()["mode"]=="test"` 守卫防误烧 VIP。
- **下一步**：可推进 P0-2（图视冲突预检）/ P0-4（跨 seed 一致性）；S4 静默返回 warning 项可开小任务卡。

---

## 阿编把关结论（主理人·2026-08-12，T-20260812-03 运维脚本工作流闭环）

- **放行决定：✅ 完成（主理人把关）**。AC-1.1~1.6 全部 PASS；4 BUG（S1P0/S2P1/S3P2/S2P2）经主理人独立实跑复验确认真修。
- **核心教训（实测 > 推断）**：本任务再次印证双角色闭环价值——开发自测"全绿、0 缺漏"时，主理人/测试独立实跑竟抓出 **S1 P0 脏双进程**（`clean_restart_studio.ps1` 在单残留稳态下不杀进程、反派生重复进程，正是脚本要杜绝的）。根因是 PowerShell 函数 `return $array` 会被**管道枚举拆包**，单命中调用方拿到裸 `CimInstance`、`.Count` 为 `$null` → 跳过杀分支。修复 `return ,$out` + 调用方 `@(...)`。
- **主理人亲自复验证据**（零 AGNES 额度）：
  1. 重跑 `clean_restart_studio.ps1`：BASELINE 29716 → 精确杀除 → 重拉 3188 → 单一健康；`OLD killed=True`、`EXACTLY ONE=True`；board/proxy/jianying/node 全部存活（0 误杀）。
  2. `deploy.ps1 --check` 进 `[CHECK mode]`、`exit 0`、未执行 rsync；远端 `nohup python3`（非 Windows 路径）。
  3. 指纹 `AND Name='python.exe'` 生效（实跑只命中真 studio）。
- **测试 Agent 工具异常**：本轮测试 Agent 写 test.md/current_state.md 时工具反复报错（content 丢失 4 次），仅给出口头结论；主理人接手按"证据不信任"原则**亲自实跑**完成复验与文件落地。后续若再遇 Agent 写文件报错，主理人应直接接手实证 + 落文件，不依赖其文件产出。
- **git**：锚点 `ed3b562`、修复 `a500bbc`（仅改 `short_drama_workflow/ops/`）。最终 8777 单一健康 PID 3188。
- **下一步**：运维脚本工作流已固化，日常一键 `clean_restart_studio.ps1` 即可；O5(VPS) provisioned 后用 `deploy.ps1 -DeployHost user@vps` 真部署（远端 python3 已就绪）。可推进 P0-2/P0-4。

---

## 操作审计（强制·R2，每次状态推进必追加一行）

> 规则（守则 §5 / 运行手册 §12）：每次状态推进（待办→进行中→…→完成 / 退回）**必须在此追加一行**，缺 = 非法状态变更。O4 board 技能启用后审计由系统自动写（X-Agent 日志），本段仅作兜底。历史任务（T-20260812-01/02/03）审计发生在本规则建立前，其「阿编把关结论」段即当时事实源；自 T-20260812-04 起严格执行本段。

| 时间 | 操作者 | 任务 | 状态变更 | 依据 |
|---|---|---|---|---|
| 2026-08-12 | 主理人 | T-20260812-04 框架加固(R1/R2/R3+v4锚)+改进文档 | 待办→进行中 | 闸1自签（框架维护·不改需求基线·白名单核验通过） |
| 2026-08-12 | 主理人 | T-20260812-04 | 进行中→完成 | 主理人把关（本段+改进文档落地） |
| 2026-08-13 | 主理人 | T-20260812-05 check_wip.ps1 | 待办→进行中→完成 | 闸1自签（O4内部脚本·不改需求基线·白名单核验通过）；Agent工具异常→主理人接手实现+实证；board 审计同步（id22/27/28/29） |
| 2026-08-13 | 开发 | T-20260813-01 l1_smoke 固化 | 待办→待验证 | 闸1自签（纯验证类·不改需求基线·白名单核验通过）；5 提交 ceb0d00/d590b06/7183432/acfdc6f（仅新增 scripts/l1_smoke.py 303 行，零生产改动） |
| 2026-08-13 | 主理人 | T-20260813-01 l1_smoke 固化 | 待验证→派测试(已验证进行中) | 主理人本机可控后台实跑 L1 免费KEY PASS（task V3gwmQ·成片URL HTTP200+video/mp4·零VIP）；证据落 design.md§3 + l1_smoke.run.log 覆盖旧失败版；派测试独立验收 AC-1.1~1.4 |
| 2026-08-13 | 主理人 | T-20260813-01 l1_smoke 固化 | 派测试(进行中)→已验证→完成 | 测试 subagent 静默返回空(test.md未写·无挂死进程)；主理人依 SOP(current_state行324)接手主会话实证：AC-1.1 curl 200+video/mp4、AC-1.2 exit3不提交、AC-1.3 mode=test零VIP、AC-1.4 --help exit0任意目录；逐条真跑复核全 PASS，放行完成 |
| 2026-08-13 | 主理人(合伙人) | T-20260813-03 对外入口令牌闸 | 待办→进行中→完成 | 老板授权"你干吧"；自探暴露面(0.0.0.0:8787 + 公网隧道 401 前 200 + PUT 可改文件)；加 PORTAL_TOKEN 闸覆盖 /studio+/api/*+/v1+/agnesapi+/console+/merge；自验抓 1 真 bug(PORTAL_TOKEN 在 _load_env 前读取→恒开)已修；localhost+公网双路径 401/200 全过；token 存 ~/.workbuddy/.env 不进代码；D4"本地网络"前提正式破产归档 |
| 2026-08-13 | 开发 | T-20260813-04a 取消鉴权·回退令牌闸 | 派活→(静默空返回) | 开发子 agent 第 2 次静默空返回（无 commit/无改动，同测试病）；主理人依 SOP §3.6 主会话接管执行 |
| 2026-08-13 | 主理人(合伙人) | T-20260813-04 取消鉴权+8787系统自启 | 进行中→完成 | 老板决策"仅本地单人·默认取消鉴权·3一样不做"；回退令牌闸(dec5ce9·34行纯删除·py_compile过·残留清空)；注册 schtasks AgnesPortal(onlogon) + start_portal.bat(托管python+崩溃重启)；杀旧PID6336→新PID26296接管8787；无token全通(200/200/400业务层/200)；8777自愈200；AC-1~5 全 PASS；rev2 修 schtasks 交互任务被父会话 ^C 回收致 8787 失联(5b5e1aa·Start-Process 独立进程·T+19s 存活验证) |
| 2026-08-13 | 开发(dev-t02) | T-20260813-02 8787 路由注册表收敛 | 派活→待验证 | **团队模式首次真实任务**（通道铁律§3.6第8层验证）；before 890f8ff + 完成 a9f47f4（route_registry.json 33路由+agnes_proxy 注册表驱动+回归脚本+自测脚本+design.md·仅入口层）；自测5 PASS |
| 2026-08-13 | 主理人(合伙人) | T-20260813-02 | 待验证→完成 | 主理人复验：读盘核验双commit+diff范围；干净重启8787(杀21120→schtasks rev2→新PID30996)；主会话重跑回归抓真bug→回归脚本501断言误判(后端透传501当未转发)→续派dev-t02修54043c5→33路由全PASS exit0；AC-1.5 起真8779假服务铁证 GET/PUT/DELETE 全200(加一行即通)；AC-1.1~1.5 全 PASS 放行 |
| 2026-08-13 | 开发(software-engineer-2) | T-20260813-06 P0-2 图视冲突预检 | 派活→待验证 | **新流程首次完整跑通**（老板18:09定：开发先写design+测试先写test+主理人双审过再实现）；design.md 审过(方案A独立端点主理人拍板)→实现 98807f5+c0cc2c4(precheck.py 287行+server路由+白名单双登记·生成链零改动)→自测4用例+真视觉match |
| 2026-08-13 | QA(software-qa-engineer-3) | T-20260813-06 | 待验证→已验证 | 独立验收(fresh eyes)AC-1.1~1.5全PASS；**抓真缺陷BUG-1(P2·真视觉路径无test守卫可烧VIP·AGNES_TEST_MODE no-op证实)+OBS-1(P3裸路径)**；不修回报 |
| 2026-08-13 | 开发(software-engineer-2) | T-20260813-06 BUG修复 | 已验证→待验证 | a04c8f1：ensure_test_mode硬守卫(仿l1_smoke)+端点默认dry_run=true+文档纠正+OBS-1裸路径判缺失；守卫自测4项+无key拦截证据 |
| 2026-08-13 | 主理人(合伙人) | T-20260813-06 | 待验证→Round2 | 主理人核产(a04c8f1真实+最小集)+线上验证(端点默认零额度+守卫拦截blocked实测)+回归34PASS；派QA Round2 |
| 2026-08-13 | QA(software-qa-engineer-3) | T-20260813-06 Round2 | 已验证→完成 | Round2 全PASS：BUG-1守卫拦截exit3+有key真视觉match零VIP、OBS-1裸路径warn、AC-1.1~1.5无回归；放行收尾 |
| 2026-08-13 | 开发(software-engineer) | T-20260813-05 看板外部API | 派活→待验证 | design.md 审过(agnes_proxy零改动结论核实)；before b265759 + 完成 cc00088(注册表+/ext·server.py 6端点+notes表·board.db状态对齐·21项自测PASS·temp DB/8799测试未碰线上) |
| 2026-08-13 | 主理人(合伙人) | T-20260813-05 | 待验证→派验收 | 主理人核产(cc00088最小集+agnesis_proxy零改动+py_compile)；干净重启8787(19632)/8788(25660)；线上实测6端点无token全200+POST写库+不污染+AC-1.5查库(10done+2todo)+回归35全过；派QA独立验收 |
| 2026-08-13 | QA(software-qa-engineer-2) | T-20260813-05 | 已验证→完成 | 独立验收AC-1.1~1.5全PASS+回归35/35 exit0+无BUG；L0静态(注册表/notes表/前端审计流/零改动)+L1真跑(含4错误路径+UTF-8无损+直连8788 401预期)；建议放行 |
| 2026-08-13 | 开发(software-engineer-3) | T-20260813-07 看板5态+docs+校验+热加载 | 派活→待验证 | design审过(K1关键坑+K2~K4全覆盖·/ext/docs修正)；before ff33776 + 完成 bb8f7c2(6文件+274/-22：server.py枚举+校验+/docs路由+K1三态过滤·docs.html·index.html 5处中文化·migrate_status_zh.py·check_wip三态·agnes_proxy热加载mtime惰性) |
| 2026-08-13 | 主理人(合伙人) | T-20260813-07 | 待验证→派验收 | 主理人核产(bb8f7c2最小集+py_compile)+**执行线上迁移**(K3顺序：停8788→备份board.db.bak-190840→迁移todo→待办×10/done→完成×10→0英文残留→起新代码)+干净重启8787(29144)/8788(13040)+线上实测(AC-1.1中文+K1在途0、AC-1.2校验400/200、AC-1.3/docs 200、AC-1.6热加载加删路由秒级+字节还原、AC-1.7回归9项200+route_diff 35全过) |
| 2026-08-13 | QA(software-qa-engineer-4) | T-20260813-07 | 已验证→完成 | 独立验收AC-1.1~1.7全PASS+无BUG；K1~K4专项全过(在途三态未爆表/热加载字节还原/备份含英文/前端0英文残留)；隔离实例8799+线上只读；TEST-FIX-1 QA自修(test期望对齐三态口径) |
| 2026-08-13 | 主理人(合伙人) | T-20260813-08 | 待办→进行中→完成 | 老板19:57拍板"主题/搜索/保存挂起·其他开干"→只做看板P0×3(分析师#5)；design方案A审过(详情按钮stopPropagation+进度概览renderProg+删除.delbtn弱化·confirm保留)；实现bee5808仅index.html 22+/3-；主理人核产+线上验证(新标记10处生效·PID29144/13040零重启铁证·接口全200·server.py净)；QA独立验收AC-1.1~1.4全PASS无BUG·K1~K4全过·零写路径零污染 |

#### 子角色判定台账（judge，自动追加）

> 纪律：每次派活收尾，主理人跑 `bash ops/judge_and_log.sh --task <T-id> --artifact <路径> [--expect ...] [--forbid ...] [--commit-dir ...]`，脚本自动在此追加一行。**结论来自主会话读盘（judge_subagent.sh），非子角色文本**——与上方状态推进表互为印证：状态表记"完成"前，此处须有对应 judge=PASS/WARN 结论。
> 用法见 `short_drama_workflow/ops/judge_and_log.sh`（包装 judge_subagent.sh，零破坏）。

<!-- JUDGE_LEDGER -->
- 2026-08-13 20:14 | T-20260813-08 | judge=✅ PASS（子角色产出经主会话读盘核验，可勾验收→完成） | QA独立验收全PASS·P0×3纯前端22行·K1~K4全过·零重启零污染·无BUG
- 2026-08-13 19:16 | T-20260813-07 | judge=✅ PASS（子角色产出经主会话读盘核验，可勾验收→完成） | QA独立验收全PASS·5态中文+docs+校验+热加载·K1~K4全覆盖
- 2026-08-13 18:42 | T-20260813-05 | judge=✅ PASS（子角色产出经主会话读盘核验，可勾验收→完成） | QA独立验收全PASS·6端点200+状态对齐+回归35全过·无BUG
- 2026-08-13 18:32 | T-20260813-06 | judge=✅ PASS（子角色产出经主会话读盘核验，可勾验收→完成） | QA独立验收抓BUG-1烧VIP风险·a04c8f1修复·Round2全PASS
- 2026-08-13 17:37 | T-20260813-02 | judge=✅ PASS（子角色产出经主会话读盘核验，可勾验收→完成） | 主理人复验·33路由PASS·AC-1.5真服务铁证200
- 2026-08-13 17:14 | T-20260813-04 | judge=✅ PASS（子角色产出经主会话读盘核验，可勾验收→完成） | 主理人主会话实测·鉴权取消+服务自启全过
- 2026-08-13 16:58 | T-20260813-03 | judge=✅ PASS（子角色产出经主会话读盘核验，可勾验收→完成） | 主理人主会话实跑·公网+localhost 双路径 401/200 全过
- 2026-08-13 16:30 | T-20260813-01 | judge=❌ 打回（原因:） | 验证打回留痕
- 2026-08-13 16:30 | T-20260813-01 | judge=✅ PASS（子角色产出经主会话读盘核验，可勾验收→完成） | 主理人主会话实证·AC-1.1成片URL
