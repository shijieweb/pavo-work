# 任务卡 T-20260813-06 · P0-2 图视冲突预检（prompt 与首尾帧图差异预检）

- 需求基线闸：老板已批 ☑（2026-08-13 18:09 "按推荐来"；backlog 定义见交接文档 §10：P0-2 图视冲突预检，依赖 P0-1 YAML——已闭环）
- 目标：生成前预检"镜头 prompt 描述"与"首尾帧图实际内容"的冲突（如 prompt 说近景、首帧却是远景），提前拦截图视矛盾，避免烧额度后出片才发现问题
- 产出路径：
  - 复用 `prompt_training.py` 的 YAML 模板 + `vision_review.py`/`diagnosis.py` 的视觉判定能力（AGNES 视觉 match/warn/fail）
  - 新增预检入口（脚本/函数），输入 shot + 首尾帧 → 输出冲突报告（match/warn/fail + 原因）
  - 接入 `/api/diagnose` 或生成前校验（具体由开发文档定）

## 验收标准（AC 锚点）
- [ ] AC-1.1 预检函数：输入单镜 shot + 首尾帧 → 输出 match/warn/fail + 冲突点描述（复用 prompt_frame_match 思路）
- [ ] AC-1.2 空镜免检：prompt 含 no people/空景 → 跳过身份审查（标 n/a）
- [ ] AC-1.3 与生成链解耦：预检不阻塞正常生成（失败=拦截提示，非崩溃）；零 AGNES 额度 dry-run 可测
- [ ] AC-1.4 接入点：生成前自动附加或手动触发（由开发文档定，需老板/主理人确认后再实现）
- [ ] AC-1.5 证据：用真实项目 shot 跑一次 dry-run 预检，输出报告

## 边界
- 只做预检（拦截提示），不改生成逻辑；不烧 VIP（免费KEY/dry-run）
- 复用既有 vision/diagnosis 能力，不重复造轮子
