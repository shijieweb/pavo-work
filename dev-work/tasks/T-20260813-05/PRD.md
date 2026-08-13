# 任务卡 T-20260813-05 · 看板外部指导 API（/ext/*）+ 状态对齐

- 需求基线闸：老板已批 ☑（2026-08-13 18:09 "按推荐来"；方案 v2 见 `dev-work/看板改造方案_20260813.md`）
- 目标：远程指导角色经 8787 网关 `/ext/*` 读看板进度 + 留指导意见；顺带修状态对齐（board 任务状态与 current_state 失真）
- 产出路径：
  - `agnes_proxy.py`：加 `/ext/` 前缀白名单 → 转发 8788，改写 `/ext/`→`/api/ext/`
  - `shared_board/server.py`：新增 `/api/ext/*` 端点（status/projects/tasks/audit/presence/notes）
  - `dev-work/current_state.md`：状态对齐修复（T-20260813-01 等已闭环任务补标 done）

## 验收标准（AC 锚点）
- [ ] AC-1.1 `GET /ext/status` → 200：全部项目 + 在途任务 + 最近审计 8 条
- [ ] AC-1.2 `GET /ext/projects`、`/ext/tasks?project_id=N`、`/ext/audit?project_id=N`、`/ext/presence` → 200 正确数据
- [ ] AC-1.3 `POST /ext/notes`（`{"project_id":N,"text":"..."}`）→ 写看板留言 + 审计记 `agent=远程指导`，前端「指导留言」栏可见
- [ ] AC-1.4 无 token 直达（本任务按老板决策不做鉴权）；`/ext/*` 不污染现有 `/api/*` 路由
- [ ] AC-1.5 状态对齐：board 已闭环任务补标 done（现状 8done+4todo+0doing 失真）

## 边界
- 只动 `agnes_proxy.py` 白名单/转发 + `shared_board/server.py` 端点；不碰生成链/云API
- 不做鉴权（老板拍板统一后置）；不加新端口
