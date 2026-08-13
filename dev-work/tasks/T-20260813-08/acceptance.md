# T-20260813-08 验收报告（acceptance.md）

## 结论

**✅ 放行（完成）**。AC-1.1~1.4 全部 PASS，无 [BUG]，QA 独立验收（fresh eyes）建议放行，主理人核产+线上验证通过。

## 交付内容

看板 UI P0×3（分析师留言 #5 三处硬伤），全部收敛在 `shared_board/index.html` 一处（22 insertions / 3 deletions）：

| AC | 内容 | 落地 |
|---|---|---|
| AC-1.1 | 详情入口显式化 | 卡片级「详情」按钮（L204-205，stopPropagation→openDrawer），单击展开/双击/长按原样保留 |
| AC-1.2 | 顶部进度概览 | `#prog` 概览条 + renderProg()（L226-233），`X 进行中 · Y 待验证 · Z 已完成 / 总数` + 待办/已验证/阻塞 muted 明细 |
| AC-1.3 | 删除弱化 | `.delbtn` 次级样式（透明底/12px/下划线）+ 移底部独立分隔行，confirm 保留 |
| AC-1.4 | 回归红线 | 后端零改动；展开/保存/新建/5 态/阻塞/日志/轮询零回归 |

## 证据链

### 主理人核产（读盘 + 线上实测）
- 双 commit 属实：`f3e63b1`（before）+ `bee5808`（实现，diff 仅 index.html 22+/3-）
- 关键实现点 grep 就位：dbtn/progbar/delbtn/renderProg（L235 在早退分支前）/confirm（L172）
- 线上生效（**零重启**）：8787/board 与 8788 直连 HTML 均含新标记×10；PID 29144/13040 与基线一致
- 接口零回归：/ext 6 端点 + /studio /board / 全 200；server.py git diff 净（K4）
- 项目 19 分布：完成×10 + 待办×2 = 12 → 进度期望 `0 进行中 · 0 待验证 · 10 已完成 / 12`

### QA 独立验收（software-qa-engineer-5，Playwright 实测）
- **AC-1.1** ✅ 8 用例：点详情开抽屉字段对、K1 点详情不触发展开（drawer=True expanded=False）、单击展开/收起、双击、移动端长按全过
- **AC-1.2** ✅ 6 用例：项目 19 进度 (0,0,10,12) 与 API 逐条一致；项目 4/18/19 全一致；写路径新建/切状态/阻塞 ≤5s 轮询实时更新
- **AC-1.3** ✅ 5 用例：computed style 保存 rgb(37,99,235)/16px vs 删除 rgba(0,0,0,0)/12px；弹窗出现→取消零删除（12→12）；临时实例确认后删子树正常
- **AC-1.4** ✅ 10 用例：6 态下拉+徽标 CSS 齐；日志 20 行；轮询 6s 无 JS 异常；接口/页面全 200；线上 HTML 新标记生效

### K1~K4 专项结论（全部 PASS）
- K1 详情按钮 stopPropagation（静态+实测）
- K2 进度口径（X/Y/Z 只计对应状态、总数=任务数组 length）
- K3 confirm 保留（弹窗实测出现+取消零删除）
- K4 server.py git diff 净 + PID 零重启铁证 + 线上数据零污染

## 缺陷清单

无 [BUG]。

## WARN（非阻断，已记录）

| # | 内容 | 建议 |
|---|---|---|
| WARN-A | 控制台 favicon.ico 404 噪音（基线既有，非本卡回归） | 补 `<link rel="icon" href="data:,">` 一行（跟进项） |
| WARN-B | `.danger` CSS 规则保留但无引用（死代码） | 最小 diff 原则下可接受，后续清理 |

## 判定

- 判定台账：judge_and_log.sh → **PASS**
- 提交：`f3e63b1`（before）+ `bee5808`（实现）+ 本验收文档提交
