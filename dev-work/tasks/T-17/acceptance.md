# acceptance · T-17 训练面板顶部实验目的说明块 + 扩展（每写法号目的+合并建议+全部测试参数置顶）

> 模板来源：`dev-work/templates/TEMPLATE_ACCEPTANCE.md`。**阿编（主理人）填写**，对照 PRD 的 AC 逐条勾，推「完成」。

## 把关结论（主理人 · 2026-08-15）

- **放行决定：✅ 放行（完成）**。T-17 主体（AC-1.1~1.7）+ 扩展（AC-2.1~2.6）全部 PASS；研发/测试分离铁律已守（开发推待验证→QA 独立验收→主理人读盘核产）。
- **主理人亲自读盘核产（§4.3，不盲信研发/测试自报）**：用 `C:/Users/67972/.workbuddy/binaries/python/versions/3.13.12/python.exe` 直接 `re.findall` 读取 `training_panel.html` 真数，见下「实测数字」表。
- **核心铁律零破坏**：56 img = 54 候选缩略图 + 2 参考图；tag 级 `data-role="thumb"`=54；54 唯一 `wXX_Y.png` 0 缺失；base64 内嵌=0；中文锚点「同一个齐肩黑发」=54（未变 55，新增块中文意译已规避该 6 字）；`data-writing` 去重=27；27 分组齐全。
- **扩展真落地**：`params-note`=1（顶部全部测试参数）、`writing-purpose`=27（每写法号目的+合并建议，内容经 QA 与 `writing_purpose.csv` 逐字比对一致）；`exp-note`=1（这批图在测什么，T-17 主体保留）。
- **下一步**：老板可据此面板直接做采纳决策——每块写法号见测试目的+合并建议，顶部见全部参数，不再跳外部文件。

## 实测数字（主理人 §4.3 读盘核产，真实 stdout）

| 指标 | 期望 | 实测 | 结论 |
|---|---|---|---|
| `<img` 标签总数 | 56 | 56 | ✅ |
| tag 级 `data-role="thumb"` | 54 | 54 | ✅ |
| 唯一 `wXX_Y.png` | 54 | 54 | ✅ |
| `data:image/...;base64` 内嵌 | 0 | 0 | ✅ |
| 中文锚点「同一个齐肩黑发」 | 54 | 54 | ✅ |
| `data-writing` 去重 | 27 | 27 | ✅ |
| 分组容器 `.group` | 27 | 27 | ✅ |
| 顶部参数块 `params-note` | 1 | 1 | ✅ |
| 每写法号目的块 `writing-purpose` | 27 | 27 | ✅ |
| 主体说明块 `exp-note` | 1 | 1 | ✅ |
| HTML 字节 | < 5MB | 178,396（174.2 KB） | ✅ |

## AC 逐条勾（主体 AC-1.1~1.7，前轮已验，本轮复核无回归）

- [x] AC-1.1 顶部唯一 `exp-note` 说明块，标题含「这批图在测什么」→ 实测 `exp-note`=1 ✔
- [x] AC-1.2 含「为何每写法 2 张图」解释（唯一变量=写法号；同写法内 2 张 prompt 同仅变种子；故意测跨种子一致性）→ 块内 `<div class="exp-why">` 就位 ✔
- [x] AC-1.3 列出 4 测试目的（黄金配方/跨种子稳定性/反例 2·3·12/首尾帧模板 v1）→ 块内 `<div class="exp-goals">` 4 项 ✔
- [x] AC-1.4 全中文可懂 → 复核通过 ✔
- [x] AC-1.5 T-16 铁律不变（56/54/54/0/54/27）→ 实测全过 ✔
- [x] AC-1.6 改生成器单源（build_training_panel.py），重运行可复现 → 本轮由生成器重生成，未手改 HTML ✔
- [x] AC-1.7 导出/采纳/统计/持久化未回归 → 控件 `btn-export-json`/`btn-export-csv`/`lightbox`/`data-group-set=adopt`(27)/`data-set=primary`(54) 均在 ✔

## AC 逐条勾（扩展 AC-2.1~2.6，本轮新增）

- [x] AC-2.1 顶部唯一 `params-note` 块含「全部测试参数」标题，覆盖 9 项（固定角色/固定场景/唯一变量/生成方式/鉴权/尺寸比例/数量/跨种子设计/负向词）→ 实测 `params-note`=1，QA 确认 9 项全命中（含 S 英文原文、免费 TEST key、2K/9:16、54 张、NEG）✔
- [x] AC-2.2 27 组均有 `writing-purpose` 块（计数=27），含「测试目的」+「合并建议」，内容来自 `writing_purpose.csv` 经 `html.escape` → 实测 27，QA 抽 w01/w12/w24 与 CSV 逐字一致 ✔
- [x] AC-2.3 参数块全中文可懂（专有词保留 i2i/TEST key/9:16/NEG）→ 复核通过 ✔
- [x] AC-2.4 T-16+T-17 主体铁律不变，新增块未引入 `<img`/`data-role=thumb`/`base64`/新`data-writing`/`wXX_Y.png`，且中文锚点仍=54 → 实测全过；QA 对 28 个新增块做 DOM 子树禁词扫描，违规=0 ✔
- [x] AC-2.5 改动落生成器单源，`self_check` 新增 4 断言（writing-purpose==27 / params-note==1 / 中文锚点复验==54 / data-writing 去重==27）→ 研发自测 + 主理人读盘双确认 ✔
- [x] AC-2.6 导出/采纳/统计/持久化无回归 → 同 AC-1.7 控件仍在 ✔

## 独立验收（QA · software-qa-engineer · agent-a2dcab0b）

- 方法：直接 `re.findall`/`str.count` 读 `training_panel.html` 与 `writing_purpose.csv`，未采信研发自报；临时脚本在 `/tmp`，未入项目。
- 结论：**建议放行（PASS）**。A 组铁律 7 项 + B 组新结构 3 项 + C 参数块 9 项 + D 每写法号目的 27 块与 CSV 全对应 + E 无越界污染，全部 PASS；0 BUG。
- 良性说明（非缺陷）：全局 `data-role="thumb"`=55 多出 1 处是 JS 选择器字符串 `ev.target.closest('[data-role="thumb"]')`；全局 `base64`=4 全在 CSS 注释（如「不引入 img/base64 内嵌」），`data:image/...;base64` 内嵌图仍=0。

## 证据位置

- 生成器：`C:\Users\67972\projects\short-drama-training\build_training_panel.py`（单源真理，已含 params-note / writing-purpose 渲染 + self_check 增量断言）
- 产物：`C:\Users\67972\projects\short-drama-training\training_panel.html`（178,396 B，自包含）
- 数据源：`01_配方训练/实验批次/batch-001/out/writing_purpose.csv`（27 行）、`scripts/run_batch001.py` 第 1–95 行
- 任务文档：`dev-work/tasks/T-17/{PRD,design,test,acceptance}.md`
