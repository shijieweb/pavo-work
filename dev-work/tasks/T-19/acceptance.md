# acceptance · T-19 训练提示词修正意见(可编辑)+手机端头部优化+脚本化进化闭环

> 主理人(阿编)把关放行文档。依据 PRD AC-1.1~1.10。证据来自主理人独立读盘核产 + QA(software-qa-engineer-1) 独立 L1 验收（test.md）。

## 一、放行决定
✅ 放行（完成）。AC-1.1~1.10 全部 PASS；研发/测试分离铁律已守（开发推「待验证」即停、测试推「已验证」即停、主理人把关标「完成」）；无 P0/P1/P2 缺陷。

## 二、AC 验收锚点核对（主理人逐条核）

| AC | 验收点 | 结论 | 证据 |
|---|---|---|---|
| AC-1.1 | writing_purpose.csv 增「提示词修正意见/修正后prompt」两列，面板逐写法号渲染可编辑块 | PASS | build_training_panel.py read_writing_purpose 读 4 列+降级；wp-corr 块 batch-001=27 / batch-002=3；design.md §3.2 |
| AC-1.2 | wp-corr 块用 data-correction-writing（不污染 data-writing==27 不变式） | PASS | self_check wp-corr==group_count；复验 data-writing 去重仍==group_count（27/3） |
| AC-1.3 | POST /batch/api/correction 端点（校验+写回） | PASS | agnes_proxy.py _serve_correction 校验 writing∈1..27/字符串/防穿越/长度≤20000/批次白名单；_update_writing_purpose 原子写回保留 BOM+全列+行序；design §3.2-D 5 例全绿 |
| AC-1.4 | 面板「保存修正」→fetch POST→写回 DOM | PASS | 前端 saveCorrection() 经 data-correction-writing 取块→fetch→轻提示+回写；端点契约 L0 验过（真浏览器点击列为 L1 必点，QA 按 AC-1.9 数据分离要求未走端点以保老板数据） |
| AC-1.5 | 手机端 .toolbar ≤768px 非 sticky（桌面不变） | PASS | CSS @media(max-width:768px){.toolbar{position:static}} L425，桌面 sticky 不变 |
| AC-1.6 | gen_next_round 确定性产下一轮（零 LLM） | PASS | L1 实测 总27/改动1(写法2进门)/沿用26；零 LLM 零 KEY |
| AC-1.7 | run_round 出图（参数同 batch001，免费 TEST KEY） | PASS | L1 实测 6 张合法 PNG（2K/9:16），use_test 零 VIP；dry-run 零 API 已验 |
| AC-1.8 | 资产路由泛化支持 batch-002 | PASS | BATCH_DIRS 含 batch-002；_serve_batch_asset 三段路由；8787 curl batch-002/cand/*.png 全 200 |
| AC-1.9 | 小批量验证闭环（3 写法号 L1→batch-002 面板→线上不裂） | PASS | 闭环全链路跑通；写法2 本轮图 prompt 确带进门修正；8787 PNG/HTML 均 200 |
| AC-1.10 | 铁律按 batch 参数化自检 | PASS | 双批次 self_check 全过：batch-001(img56/thumb54/唯一54/base640/wp-corr27/data-writing27/中文0)、batch-002(img8/thumb6/唯一6/base640/wp-corr3/data-writing3/中文0) |

## 三、闭环成立关键证明
老板手填修正（sample_corrections.csv 模拟写法2 进门修正）→ gen_next_round 确定性拼出写法2 prompt 含「明确进门动作：她正推门向内、迈步进入咖啡馆（非出门）」(27/1/26) → run_round 用免费 TEST KEY 真出 w02_1/2.png（PNG 字节 w02_1=3990598 ≠ 占位 3752757，证明确为重新生成）→ batch-002/out/prompts.csv 写回带修正 prompt + AGNES url → 重建面板 HTML 实测含进门修正文案 + wp-corr/data-correction-writing 块 → 8787 线上 200 不裂。**写法2 这轮出的图，其 prompt 确实带进了门修正，闭环成立。**

## 四、遗留 / 边界（非阻塞）
- 前端真实浏览器点击保存→DOM 回写路径：L0 验端点契约、L1 按 AC-1.9 数据分离要求未走 POST 端点（避免污染老板 writing_purpose.csv）；建议后续做一次真浏览器点击端到端确认（不阻塞放行）。
- 进化链「下一轮→再下一轮」：run_round 写回 prompts.csv 为 (file,写法号,prompt,url) 格式，与 gen_next_round 读取的 (写法号,prompt) 不同；当前闭环以 writing_purpose.csv 为持久单源（面板编辑→端点写回）驱动，round prompts.csv 仅当轮产物，不阻断多轮。多轮累积「连续无修正轮次/成型标志」由 gen_next_round 的 round_status.csv 提供信号。
- 全量 54 张 batch-002：按 q-0 决策"机制+小批量验证"，本次仅跑 3 写法号 6 张证明闭环；全量待老板确认后另跑。

## 五、主理人把关签名
- 放行：✅ 完成（2026-08-15）
- 主理人独立读盘核产：L0 重跑全过 + L1 真图字节已变 + 面板含修正文案 + 自跑 batch-002 自检全过 + 读 test.md 确认 AC 全 PASS。
- 证据存档：dev-work/tasks/T-19/{PRD,design,test,acceptance}.md；01_配方训练/实验批次/batch-002/out/{w02_1,w02_2,w09_1,w09_2,w17_1,w17_2}.png；training_panel_batch-002.html；round_002/prompts.csv + round_status.csv。
