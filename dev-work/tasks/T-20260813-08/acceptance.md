# T-20260813-08a 验收报告（acceptance.md）

## 结论

**✅ 放行（完成）**。T-08a 视图重做（泳道 5 态 + 统计条 + 暗色 + toast + 在线👤 + K1 迁移 + 6 态配色）验收通过：Round 1 抓出 1 个 P0 泳道布局 bug（已修复），Round 2 全量回归全绿，判定 PASS。

## 交付内容（commit 链）

| commit | 内容 |
|---|---|
| `5ec5944` | before 基线 |
| `8206348` | 泳道 UI 重做（298+/74-，仅 index.html）：6 列泳道/统计条(K1)/暗色/toast/在线👤/视图切换/子任务方案 A/6 态配色 |
| `4c9ddfa` | P0 泳道布局修复（display:block→flex）+ WARN-1 暗色徽章对比度 |

**能力**：泳道 5 态（待办/进行中/待验证/已验证/完成 + 阻塞旁路）横向滚动、统计条（总计/进行中/待验证/阻塞/完成 + muted）、🌙 暗色切换（localStorage 持久化）、toast 反馈、在线 👤 头像条、泳道⇄树视图切换、子任务方案 A（全量平铺+父引用 chip+计数徽章）、新态配色（待验证 amber/已验证 purple）、K1 迁移（详情按钮/进度概览）。

**保留能力零回归**：抽屉编辑（5 态下拉/优先级/保存/子任务/删除弱化 confirm）、多项目切换、owner 写锁 403、审计流、复制派单、token 注入。

## 证据链

### 主理人核产（读盘 + Playwright 亲测）
- 双 commit 属实 + diff 仅 index.html；11 个渲染/保留函数就位；JS 语法 node 抽检通过
- **P0 修复亲测**：`board.display=flex`、6 列横向（left 22→1382 等差、top 全 155）、scrollW 1648>1544 可滚动
- 线上生效（零重启）：8787/board 与 8788 新标记×35；PID 29144/13040 与基线一致
- 接口零回归：/ext 6 端点 + /studio /board / 全 200；server.py git diff 净（K5）

### QA 独立验收（software-qa-engineer-6）
- **Round 1**：L0 全 PASS、L1 线上 35/35、写路径 26/27——**抓出 P0 泳道布局 bug**（display:block 覆盖 flex→6 列垂直堆叠）+ WARN-1 暗色徽章对比度 2.06:1
- **Round 2**（修复后）：**全绿放行**——
  - P0 复验 ✅：桌面 6 列横向（distinctLefts=6/distinctTops=1）、移动端 390px 80vw 列横向滚动生效（scrollW 1960>374）
  - WARN-1 复验 ✅：暗色紧急徽章 #fca5a5 对比度 7.71:1（≥4.5 AA）
  - WARN-3 破案 ✅：子任务计数徽章**非源码 bug**——测试脚本 force-click 落在遮挡 drawer 上导致视图未切换，改 JS 原生 click 后 27/27 全 PASS
  - 全量回归 ✅：L0 K1~K5、L1 线上、写路径全套全绿
- 附带处置：清理 2 个残留 QA 调试进程（PID 32820/32324）+ 残留临时 DB；线上 board.db 零污染

### K1~K5 专项（全 PASS）
- K1 详情按钮 stopPropagation（点详情前后展开状态不变）
- K2 统计口径（各计各态、总计=任务数组 length，三向一致）
- K3 暗色持久化（localStorage('kanban-dark') + reload 保持）
- K4 confirm 保留 + toast 替代 alert
- K5 server.py git diff 净 + PID 零重启 + 线上数据零污染

## 缺陷清单

- [BUG][P0] 泳道布局 display:block 覆盖 flex → **已修复**（4c9ddfa，Round 2 复验 PASS）
- [WARN-1] 暗色优先级徽章对比度 2.06:1 → **已修复**（7.71:1，随 4c9ddfa）
- [WARN-3] 子任务计数徽章 → **非源码 bug**（测试脚本 force-click 问题，QA 自修）

## 判定

- 判定台账：judge_and_log.sh → **PASS**
- 提交：`8206348`（功能）+ `4c9ddfa`（修复）+ 本验收文档
