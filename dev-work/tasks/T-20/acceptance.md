# acceptance · T-20 看板重构综合方案

> 模板来源：`dev-work/templates/TEMPLATE_ACCEPTANCE.md`。主理人（阿编）把关填写，对照每条 AC 附证据。

## 验收对照表（实施完成后填）

| AC | 内容 | 证据 | 结论 |
|---|---|---|---|
| AC-1.1 | current_state.md 当前任务表由 board 自动生成 | sync 脚本输出 + diff | ☐ PASS / ☐ FAIL |
| AC-1.2 | 8788 默认首页 = 执行中台 | 8787/board 截图 | ☐ |
| AC-2.1 | 进站视图：待办未认领按 created_at | curl /api/intake | ☐ |
| AC-2.2 | 指标条：进站/新进/吞吐/WIP | 计算值核对 | ☐ |
| AC-3.1 | 堵塞视图：阻塞或 blockedBy 未解 + aging | curl /api/blocked | ☐ |
| AC-3.2 | blockedBy + blocked_reason 持久化 | db 查询 | ☐ |
| AC-3.3 | 堵塞 >N 天标红 | 前端截图 | ☐ |
| AC-4.1~4.5 | 筛选/快切/留言/自动刷新/完成时间戳/flash | 交互验证 | ☐ |
| AC-5.1 | 删测试项目 + 建 3 真实工作线 | board 项目列表 | ☐ |
| AC-6.1 | 老板一屏见进站/WIP/堵塞 + 进行中实时非 0 | 老板肉眼 | ☐ |

## 主理人把关结论（实施完成后填）
- 放行 / 退回：☐
- 备注：
