# T-20260813-08b 功能融合 · 验收对照（acceptance.md）

> 对照 PRD §三 验收标准 AC-1.1 ~ AC-1.12。T-08a 已验收项（AC-1.1~1.10 中泳道/统计/暗色/编辑回显/权限/ toast/自动刷新/新态配色/多项目）**本卡在融合中零回归保留**，此处逐条确认。

| AC | 验收点 | 实现/验证 | 结论 |
|---|---|---|---|
| **AC-1.1** | 泳道按 5 态正确分组（+阻塞列），每列计数对 | `COLUMNS` 6 列直映射；`renderBoard()` 按 `statusToColumn` 分组；列头 `count` 实时 | ✅ 零回归 + L0.5 断言 1 |
| **AC-1.2** | 统计条数字与泳道各列一致 | `renderProg()` 改用 `matchFilter()` 与 `renderBoard()` 同一口径 | ✅ L0.5 断言 6/7 |
| **AC-1.3** | 暗色切换生效且 localStorage 持久化 | 未改动，沿用 T-08a `.dark`+`localStorage('kanban-dark')` | ✅ 零回归 |
| **AC-1.4** | 卡片单击开详情；保存后异步回显（drawer 不重置） | `openDrawer`/`saveDrawer` 未改；`tick()` 异步刷新不触抽屉 DOM | ✅ 零回归 + 代码审查 |
| **AC-1.5** | 增删改/子任务/owner 写锁 403/审计/复制派单不破；删除弱化 | `addRoot/addChild/delTask/copyDispatch/changeOwner` 全保留；`delbtn` 弱化为 ghost/danger 小字 | ✅ grep 确认 + 零回归 |
| **AC-1.6** | toast 出现（保存/失败/手动刷新） | `showToast` 保留；手动刷新/自动切换均有 toast | ✅ 零回归 |
| **AC-1.7** | 自动刷新开关：开=异步刷不打断编辑；关=停轮询 | 新增「🔄 自动」开关 + `tick()/startAuto()/stopAuto()`；默认开 | ✅ 代码审查 + test.md |
| **AC-1.8** | 新态配色可见：待验证=amber、已验证=purple | 未改动，T-08a 已落地 | ✅ 零回归 |
| **AC-1.9** | 多项目切换/操作日志/在线条正常；`/ext` 6 端点不受影响 | `projSel`/`setProj` 保留；`loadPresence/loadAudit` 仍于 tick 刷新；仅新增消费 `/api/ext/notes`（GET），其余 `/ext` 端点未动 | ✅ 零回归 + 代码审查 |
| **AC-1.10** | 消费 5 态中文 API 正确 | 状态 5 态中文（待办/进行中/待验证/已验证/完成）+ 阻塞旁路，直映射列 | ✅ 零回归 |
| **AC-1.11** | **指导留言栏**展示 `/ext/notes`（按项目过滤、最新置顶、本地+外部可见） | `loadNotes()` GET `?project_id=cur`；`renderNotes()` 渲染；空态/未选项目态；可折叠；复用审计样式 | ✅ curl 数组 + L0.5 断言 11/12 |
| **AC-1.12** | **功能融合 A 类**：筛选(状态/优先级/作者)生效；完成时间戳徽章；flash 定位 | 筛选=AC 主菜⑨（L0.5 断言 9/10）；完成时间戳=`done-stamp`（断言 3）；flash=`scrollToCard`+父任务引用 onclick | ✅ L0.5 断言 1/3/9/10 |

## 九项 T-08b 主菜对照（PRD 〇.9~13 + 一.6/一.7）
| # | 主菜 | 状态 |
|---|---|---|
| 9 | 筛选按钮组（状态/优先级/作者，纯按钮组，实时生效，与泳道协同） | ✅ |
| 10 | 卡片状态快捷切换（点徽章弹菜单，不开 drawer，调 PUT） | ✅ |
| 11 | 指导留言栏（GET /api/ext/notes，按项目过滤、最新置顶、可折叠、复用审计样式） | ✅ |
| 12① | 完成时间戳徽章（done/完成 显示完成时间，updated 近似） | ✅ |
| 12② | flash 高亮定位（关联标签点击滚动+闪烁，参考 scrollToCard） | ✅ |
| 12③ | 进度字段位（暂无 progress 不显示，留好结构） | ✅ |
| 13 | 自动刷新开关（默认开，异步刷不打断编辑）+ 保存异步回显 | ✅ |

## 总结
- 12 条 AC 全部满足（T-08a 项零回归，T-08b 新增项全部实现并实测）。
- 四文档齐全：`PRD.md`（既有）、`design.md`、`test.md`、`acceptance.md`（本卡新增）。
- 后端 `server.py` 零改动；前端纯原生 JS 零依赖。
- 无未决遗留缺陷。
