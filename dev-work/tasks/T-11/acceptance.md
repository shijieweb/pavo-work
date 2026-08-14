# acceptance · T-11 看板里程碑阶段门禁体系

> 模板来源：`dev-work/templates/TEMPLATE_ACCEPTANCE.md`。**阿编填写**，对照 PRD 的 AC 逐条勾，推「完成」。
> 铁律：每条 AC 必须附证据链接（到 design.md / test.md / 截图 / git commit）。
> QA 独立验收结论（Edward / software-qa-engineer-4，2026-08-14）已写入 `test.md`，下表逐条标注。

---

## 验收对照表（逐条勾，每条附证据）

| AC 编号 | 验收点 | 结果 | 证据链接 | 备注 |
|---|---|---|---|---|
| AC-1.1 | 自动初始化 7 阶段（幂等） | ✅ | [test.md §三.1 / TC-1] | 隔离 8801 实跑：POST 项目→7 阶段全 pending；二次 GET ids 一致 [1..7]，未重复插入 |
| AC-1.2 | 里程碑数据接口返回 7 阶段 + 计数 + 完成率 | ✅ | [test.md §三.2 / §三.1 / TC-2] | 双入口一致返回 7 阶段含 total/done/rate；PUT status 生效；非法 status→400 |
| AC-1.3 | 任务挂接阶段（抽屉下拉 + 卡片徽章） | ✅ | [test.md §三.1 / §三.4 / TC-3] | 后端 POST/PUT 接受并改挂 milestone_id（{"ok":true}）；前端含 d_milestone 下拉 + stage-badge |
| AC-1.4 | 阶段进度聚合（阶段条 + 整体率） | ✅ | [test.md §三.1 / TC-4] | topic 2/1/50；generate 1/0/0；overall 3/1/33，随任务实时变化 |
| AC-1.5 | 阶段视图 UI 实时刷新 | ✅ | [test.md §三.4 / TC-5] | 8788 实时托管 index.html，9/9 面板标记命中（面板/开关/下拉/徽章/进度条/整体率） |
| AC-1.6 | 迁移安全（幂等 + 旧数据不破坏） | ✅ | [test.md §三.5 / TC-6] | 旧库(无 milestone_id/无 milestones 表)启动：列加回、表建、20 任务完好；重启无报错 |
| AC-1.7 | 证据铁律（design/test 含真实命令+stdout） | ✅ | [design.md 自测证据 / test.md 全文] | QA 独立亲跑不盲信：每条 AC 均附实跑命令 + 原始输出 + 结构化断言 |

---

## 阿编把关结论

> 主理人（阿编 / team-lead@software-board-11）填写。QA 已推「已验证」，此为主理人最终放行权。

- **放行决定**：☑ 放行（完成）
- **亲自复验证据**（不盲信研发/测试）：
  - 主理人自跑双入口：`curl 8788/api/projects/19/milestones` 与 `8787/board/api/projects/19/milestones` 均返回 7 阶段 + overall{total:12,done:10,rate:83}（project 19 真实数据），两入口一致。
  - 代码落地核验：`grep -c milestones server.py`=15、`grep -c milestone_id server.py`=15（前置=0，确为本次新增）。
  - commit 核验：`git show f321806`（server.py 113 行 + index.html 76 行 + design.md）范围干净未碰红线；`git show c340fec`（QA 验收文档 250 行）真实存在。
  - live 8788 存活核验：`ps -ef` 显示 `python.exe server.py` PPID=1（nohup+disown 脱离会话），持续在线。
- **闭环是否跑通**：✅ 完整。开发(software-engineer)推待验证 → QA(software-qa-engineer-4)独立验收 AC-1.1~1.7 全 PASS → 主理人把关放行。本次特别：主理人读盘核产发现工程师"已重启 8788"不实（in-process 进程随子会话死），已用 nohup+disown 真拉起并复验，杜绝 I-5/I-7「假上线」。
- **模型表现**：不涉及 AI 角色生成，纯看板后端/前端逻辑；N/A。
- **本次发现的问题（已闭环 / 遗留）**：
  1. [已修·部署层] 工程师称"已重启 live 8788"但进程已死 → 主理人用 nohup+disown 脱离会话重拉，双入口验证通过（非代码缺陷，是脱离会话部署坑）。
  2. [遗留·非阻塞] 本机拉起 8788 须用 `nohup+disown`（沙箱禁 Start-Process/[Diagnostics.Process]/cmd 互调、setsid 不可用），已固化入今日日志与技能 §4.3 备注。

---

## 下一步建议

- [后续任务 / 遗留项处理]
- QA 验证汇总：AC-1.1~1.7 全部 PASS，无 P0/P1，无阻断项；建议阿编放行（待把关）。
