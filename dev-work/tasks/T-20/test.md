# test · T-20 看板重构综合方案

> 模板来源：`dev-work/templates/TEMPLATE_TEST.md`。测试独立验收填写，推「已验证」即停（无 done 权）。
> 本文件在**实施阶段**填写：覆盖矩阵（AC-1.1~6.1）+ 独立验证命令与 stdout + 缺陷清单。

## 一、覆盖矩阵（待实施填）
- [ ] TC-1 AC-1.1 sync_board_to_md 生成 current_state.md 当前任务表 == board
- [ ] TC-2 AC-1.2 8788 默认首页 = 执行中台（含进站/堵塞/WIP 信号）
- [ ] TC-3 AC-2.1 进站视图：待办未认领按 created_at 列出
- [ ] TC-4 AC-2.2 指标条：进站积压/新进/吞吐/WIP 计算正确
- [ ] TC-5 AC-3.1 堵塞视图：阻塞或 blockedBy 未解列出 + aging
- [ ] TC-6 AC-3.2 blockedBy + blocked_reason 持久化
- [ ] TC-7 AC-3.3 堵塞 >N 天标红
- [ ] TC-8 AC-4.1~4.5 筛选/快切/留言/自动刷新/完成时间戳/flash
- [ ] TC-9 AC-5.1 删测试项目 + 建 3 真实工作线
- [ ] TC-10 AC-6.1 老板一屏见进站/WIP/堵塞 + 进行中实时非 0

## 二、独立验证命令与输出（待实施填）
```
<curl /api/intake /api/blocked /api/metrics 输出>
<sync 脚本输出 + current_state.md diff>
<8787/board 打开截图>
```

## 三、缺陷清单（测试专属，仅报告不改）
```
[BUG][S|P] ...
```
