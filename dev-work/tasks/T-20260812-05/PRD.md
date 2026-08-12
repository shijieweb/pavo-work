# 任务卡 T-20260812-05 · O4 check_wip.ps1 WIP 机械检查脚本

- 需求基线闸：老板已签 ☑（2026-08-12 口头授权"开始吧"→ O4 board 机械闸门迁移）
- 自签依据（R1 留痕）：属「协作框架自动化(O4)」内部脚本，**不改短剧业务需求基线**，白名单核验：不触对外接口/生产数据/鉴权/生成逻辑 → 主理人闸1 自签
- 目标：把 WIP 限制从「阿编自觉」变「机械检查」——GATE0 派活前跑 `check_wip.ps1`，doing 任务数超阈值即红卡拦截（exit 非 0），未超放行（exit 0）
- 产出路径：新增 `short_drama_workflow/ops/check_wip.ps1`；`ops/README.md` 补一行用法

## 验收标准（AC 锚点）

- [ ] **AC-1.1** 调 board API `GET http://127.0.0.1:8788/api/tasks?project_id=<id>`（带 `X-Agent: 阿编` + `X-Board-Token`，令牌从 `shared_board/.env` 的 `BOARD_TOKEN` 读取），统计 `status=="doing"` 的任务数
- [ ] **AC-1.2** 参数：`-ProjectId`（默认 19）、`-Limit`（默认 3）、`-Owner`（可选，只统计某 author 的 doing 任务，近似 v4 按角色 WIP）
- [ ] **AC-1.3** 判定：doing 数 ≤ Limit → 绿字 `[OK] WIP PASS` + `exit 0`；doing 数 > Limit → 红字 `[FAIL] WIP 超限`（列出超限任务标题/PID 级别信息）+ `exit 1`（**红卡拦截，可被 GATE0 脚本检测**）
- [ ] **AC-1.4** 零 AGNES 额度（纯 board API 调用）；幂等可重复；board 服务未起时优雅报错并 exit 1（不静默）
- [ ] **AC-1.5** 实跑验证：当前项目 doing=1（O4 主任务），`-Limit 3` 应 PASS exit 0；`-Limit 0` 应 FAIL exit 1（红卡生效）；`-Owner 阿编` 与全量统计一致
- [ ] **AC-1.6** `ops/README.md` 补 `check_wip.ps1` 用法行

## 证据要求

- 开发：git diff 文件清单 + 实跑输出（PASS/FAIL 两态）+ exit code
- 测试：独立实跑（PASS/FAIL/幂等/board 未起 4 态）+ `[BUG][S|P]` 缺陷清单（如有）
- 全程零 AGNES 额度

## 禁止项

- 不改 `server.py` / `agnes_proxy.py` / `shared_board/*`（board 服务本身不动）
- 不改 test.md / current_state.md（主理人管控）
- 不创建多余文件（单脚本 + README 一行）
