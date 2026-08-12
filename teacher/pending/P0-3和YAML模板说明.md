# P0-3 和 YAML 模板说明

> 老师已直接完成的两项修改，你 pull 下来即可看到代码变更。

## 1. P0-3：param_snapshot bug 已修复

### 改了什么

**文件 1：`short_drama_workflow/scripts/diag/auto_learn.py`**

`_param_snapshot()` 函数（第 202 行起）：

| 字段 | 修复前 | 修复后 |
|------|--------|--------|
| negative | `p.get("negative") is not None` → 对字符串和布尔值判断有误 | 类型感知判断：str→bool(strip)，bool→直接用，other→bool() |
| negative_prompt | 不存在 | 新增，记录实际负面词文本（前200字符） |
| seed_fixed | `p.get("seed") is not None` → 同样有误 | `isinstance(seed, (int, float))` |
| seed_value | 不存在 | 新增，记录实际 seed 值 |
| mode | 有时为 null | 保持原值，但由于 negative/seed 修复后整体快照更准确 |

**文件 2：`short_drama_workflow/scripts/diag/prompt_training.py`**

第 381 行 evidence 块：
- `negative` 保持布尔值（标记是否使用负面词）
- 新增 `negative_prompt`：存 `NEG_PROMPT` 字符串前 200 字符

### 验证结果

```
重跑 auto_learn.py on exp_0812_1502:
  negative: True          (修复前 False)
  negative_prompt: "text, watermark, logo, subtitles, morphing, ..."
  seed_fixed: True        (修复前 False)
  seed_value: 1224        (修复前不存在)
  mode: "keyframes"       (修复前 null)
全部断言通过 ✅
```

### 你不需要做什么

P0-3 已完成，不用再改。

---

## 2. YAML-1：empty_scene_v1.yaml 模板已创建

### 新文件

`short_drama_workflow/scripts/diag/templates/empty_scene_v1.yaml`

### 内容

从 08 经验避坑库 C 段第 7 条"真空景生成配方"提取（v18 已验证 pass）。

4 个变体：

| 变体 | 假设 | 目标 |
|------|------|------|
| v0 | 基准：英文 prompt + 2 帧 + 81 帧 | 验证 v18 配方可重复 |
| v1 | 中文 prompt：运动描述更细腻 | 验证中文在空景中是否也优于英文 |
| v2 | 短时长测试 | 空景变化少，更短时长是否更稳定 |
| v3 | 增强人物抑制 | 负面词叠加 + prompt 重复 no people |

特殊配置：
- `identity_check: skip`（空镜免检）
- 空景专用负面词（在通用负面词基础上增加 people/person/figure/human/silhouette 等抑制词）
- 首帧用 `text:` 前缀标记文生图（P0-1 YAML 加载器完成后识别此前缀）

### 你需要做什么

**等 P0-1 完成后**，验证此模板可被 `--template empty_scene_v1` 加载。如果 P0-1 的 YAML 格式和这个模板有差异，告诉我，我调整模板格式适配。
