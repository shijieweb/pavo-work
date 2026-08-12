# Teacher · 老师工作台

> 老师（Agnes Skills 认知层）和学生（代码维护 AI）的协作接口。
> 老板（人类）是最终决策者。

## 目录结构

```
teacher/
├── README.md            ← 你正在看的文件
├── TRACKING.md          ← 教案状态总表（老师维护）
├── CHANGELOG.md         ← 改动日志（双方共用）
└── documents/           ← 教案文档
    ├── P0-fix-spec.md   ← P0 改进教案（4 条修复规范）
    └── entry-gap-patches.md ← 入口缺口补丁（4 个补丁）
```

## 协作流程

### 老师出教案
1. 在 `documents/` 写教案文档（含验收标准）
2. 在 `TRACKING.md` 添加条目，状态 📋
3. commit + push

### 学生改代码
1. `git pull` 拉取最新教案
2. 读 `TRACKING.md` 找状态为 📋 的条目
3. 读 `documents/` 中对应教案
4. 改代码
5. commit message 标注教案 ID，如 `[P0-1] extract templates to YAML`
6. 在 `CHANGELOG.md` 记录改了什么
7. 在 `TRACKING.md` 把状态改为 🧪
8. push

### 老师验证
1. `git pull`
2. `git diff` 分析变更
3. 读 `CHANGELOG.md` 看学生自述
4. 逐条对照教案验收标准
5. 在 `CHANGELOG.md` 填写验收结果
6. 全部通过 → `TRACKING.md` 状态改 ✅
7. 有问题 → 状态改 ❌ + 写明哪条没过
8. 如果代码变化导致教案需修订 → 状态改 🔄 + 更新教案
9. 出下一轮教案（如有）
10. commit + push

### 闭环判定
- `TRACKING.md` 中某教案状态为 ✅ = 闭环完成
- 状态为 ❌ = 需返工，学生重新改
- 状态为 🔄 = 教案需更新，老师重新写

## Commit Message 规范

```
[教案ID] 简述

详细说明（可选）
```

示例：
- `[P0-1] extract 7 templates to YAML, refactor build_variants()`
- `[P0-3] fix _param_snapshot negative/seed detection`
- `[GAP-1] add exp JSON schema to 03_数据契约.md`

## 老板触发检查

老板随时可以对老师说"检查一下他改了什么"，老师会：
1. `git pull`
2. `git log --oneline -10` 看最近提交
3. `git diff` 分析变更
4. 读 `CHANGELOG.md`
5. 对照 `TRACKING.md` 验收标准
6. 输出状态报告：哪些 ✅ / 哪些 ❌ / 哪些 🔄
