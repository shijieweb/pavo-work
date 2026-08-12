# Change Log · 改动日志

> 记录每次代码变更，老师和学生共用。
> 学生改代码后在这里记录改了什么；老师验证后在这里记录验收结果。

## 格式规范

```
## YYYY-MM-DD HH:MM | 角色 | [教案ID] 简述

### 改动内容
- 文件：xxx.py 第 XX 行
- 改了什么：...

### 验收结果（老师填写）
- [x] / [ ] 验收项 1
- [x] / [ ] 验收项 2
- 结论：✅ 通过 / ❌ 未通过 / 🔄 需更新教案
```

---

## 2026-08-12 16:30 | 老师 | [P0-3] 修复 param_snapshot bug

### 改动内容
- 文件：`scripts/diag/auto_learn.py` 第 202-244 行
- 改了什么：`_param_snapshot()` 函数，将 `is not None` 改为类型感知判断
  - negative：默认 False，按 str/bool/other 类型判断
  - 新增 negative_prompt 字段记录实际负面词文本
  - seed_fixed：默认 False，检测 int/float 类型
  - 新增 seed_value 字段记录实际 seed 值

- 文件：`scripts/diag/prompt_training.py` 第 381 行
- 改了什么：evidence 块新增 `negative_prompt` 字段（存 NEG_PROMPT 字符串前 200 字符）
  - evidence.negative 保持布尔值（标记是否使用负面词）
  - evidence.negative_prompt 新增（记录实际文本）

### 验收结果
- [x] negative 字段输出 true（修复前 false）
- [x] negative_prompt 包含实际负面词文本
- [x] seed_fixed 输出 true（修复前 false）
- [x] seed_value 记录实际 seed 值（1224）
- [x] mode 输出 "keyframes"（修复前 null）
- 结论：✅ 通过（重跑 auto_learn.py 全部断言通过）

---

## 2026-08-12 16:30 | 老师 | [YAML-1] 创建 empty_scene_v1 模板

### 改动内容
- 文件：`scripts/diag/templates/empty_scene_v1.yaml`（新建）
- 内容：4 个变体（v0 基准/v1 中文 prompt/v2 短时长/v3 增强人物抑制）
- 来源：08 经验避坑库 C 段第 7 条"真空景生成配方"（v18 验证）
- 特殊：identity_check: skip（空镜免检）、空景专用负面词

### 验收结果
- [x] YAML 文件格式正确
- [x] 4 个变体定义完整
- [x] 空景专用负面词含人物抑制词
- [ ] 可被 --template empty_scene_v1 加载（待 P0-1 完成后验证）
- 结论：✅ 模板创建完成，待 P0-1 YAML 加载器完成后联调

---

<!-- 学生改代码后在这里追加记录 -->
<!-- 模板：

## YYYY-MM-DD HH:MM | 学生 | [教案ID] 简述

### 改动内容
- 文件：xxx.py 第 XX 行
- 改了什么：...

### 验收请求
请老师验证以下验收标准：
- [ ] 验收项 1
- [ ] 验收项 2

-->
