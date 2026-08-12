# Teacher Tracking · 教案状态总表

> 老师（Agnes Skills 认知层）维护，学生（代码维护 AI）阅读。
> 每条教案有唯一 ID、状态、验收标准。改完代码后 commit message 标注对应 ID。

## 当前状态总览

| 教案 ID | 标题 | 优先级 | 状态 | 最后更新 |
|---------|------|--------|------|----------|
| P0-1 | 变体模板硬编码 → YAML 配置化 | P0 | 📋 待开始 | 2026-08-12 |
| P0-2 | 缺少图视冲突预检 | P0 | 📋 待开始 | 2026-08-12 |
| P0-3 | param_snapshot 布尔值 bug | P0 | ✅ 老师已修复 | 2026-08-12 |
| P0-4 | seed 不完全可复现 → 跨 seed 一致性 | P0 | 📋 待开始 | 2026-08-12 |
| GAP-1 | exp JSON Schema 补充 | P0 | 📋 待粘贴 | 2026-08-12 |
| GAP-2 | 训练操作指南补充 | P0 | 📋 待粘贴 | 2026-08-12 |
| GAP-3 | README 训练入口补充 | P1 | 📋 待粘贴 | 2026-08-12 |
| GAP-4 | 09 SOP 第九章修正 | P1 | 📋 待粘贴 | 2026-08-12 |
| YAML-1 | empty_scene_v1.yaml 模板 | P1 | ✅ 老师已创建 | 2026-08-12 |

## 状态说明

| 图标 | 含义 |
|------|------|
| 📋 | 待开始——老师已出教案，学生尚未动手 |
| 🔧 | 进行中——学生正在改 |
| 🧪 | 待验证——学生说改完了，老师尚未验证 |
| ✅ | 已完成——老师验证通过 |
| ❌ | 有问题——老师验证未通过，需返工 |
| 🔄 | 需更新——代码变化导致教案需修订 |

## 验收协议

**学生改完代码后**：
1. commit message 必须标注教案 ID，如 `[P0-1] extract templates to YAML`
2. 在本文件 CHANGELOG.md 记录改了什么
3. 状态从 📋 改为 🧪

**老师验证时**：
1. `git pull` 拉取最新代码
2. `git diff` 分析变更
3. 逐条对照教案的验收标准
4. 全部通过 → 状态改为 ✅
5. 有未通过项 → 状态改为 ❌ + 写明哪条没过

## 各教案验收标准

### P0-1：变体模板 YAML 化
- [ ] 现有 7 套模板全部提取为独立 YAML 文件
- [ ] 重构后 build_variants() 不超过 40 行
- [ ] 用 exp_0812_1502 重跑结果与重构前一致
- [ ] 新建 dialogue_v1.yaml 不改 Python 代码即可加载
- [ ] YAML 支持 {{var}} 替换和 file: 读取

### P0-2：图视冲突预检
- [ ] 新建 visual_conflict_check.py 可独立运行
- [ ] exp_0812_1502 v18/v19 测试通过（无冲突误报）
- [ ] 故意冲突的变体被标记并跳过生成
- [ ] 看板展示冲突标签
- [ ] skipped_conflict 独立统计

### P0-3：param_snapshot bug ✅ 老师已修复
- [x] negative 字段输出 true（修复前 false）
- [x] negative_prompt 包含实际负面词文本
- [x] seed_fixed 输出 true（修复前 false）
- [x] seed_value 记录实际 seed 值
- [x] mode 输出 "keyframes"（修复前 null）
- [x] prompt_training.py evidence 增加 negative_prompt 字段
- **验证结果**：重跑 auto_learn.py，全部断言通过

### P0-4：跨 seed 一致性
- [ ] _compute_confidence() 区分跨 seed 和同 seed pass
- [ ] exp_0812_1502 重跑置信度为 medium（单次 pass）
- [ ] prompt_training.py 支持 --runs 2
- [ ] 看板显示 seed 验证标签
- [ ] 跨 seed 不一致标记"不稳定"

### GAP-1~4：文档补丁
- [ ] 补丁 1 粘贴到 03_数据契约.md
- [ ] 补丁 2 粘贴到 09_SOP.md 第十二章
- [ ] 补丁 3 粘贴到 README.md
- [ ] 补丁 4 替换 09_SOP.md 第九章

### YAML-1：empty_scene 模板 ✅ 老师已创建
- [x] templates/empty_scene_v1.yaml 已创建
- [x] 4 个变体（v0 基准/v1 中文/v2 短时长/v3 增强抑制）
- [x] 含空景专用负面词（抑制人物生成）
- [x] identity_check: skip（空镜免检）
- **待学生做**：P0-1 YAML 加载器完成后，验证此模板可被 --template empty_scene_v1 加载
