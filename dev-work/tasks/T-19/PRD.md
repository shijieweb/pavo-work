# PRD · T-19 训练提示词修正意见(可编辑)+手机端头部优化+脚本化进化闭环

> 模板来源：`dev-work/templates/TEMPLATE_PRD.md`。阿编(主理人)填写。

- **需求基线闸：老板已签 ☑**（来源：本会话 2026-08-15 老板指令「加提示词修正意见→进下一轮；手机端头部不固定；进化全模板化不依赖你考虑，要闭环」+ 两问答复 q-0=机制+小批量验证(含写法2) / q-1=老板手填。视同闸1/闸2 老板显式批准需求基线与范围）
- **白名单核验（R1 留痕）**：本任务触碰【接口】新增 POST `/batch/api/correction`、【数据】`writing_purpose.csv` 改动、【生成逻辑】`run_round.py` 出图、【新增功能】可编辑修正字段+进化脚本——按运行手册 §12 本应无裁量权必叫老板；但老板已在本会话显式批准，故留痕视同签核，不走闸2 二次确认。
- **目标**：①训练面板每写法号加「提示词修正意见」可编辑字段(老板手填、保存落盘 CSV) ②手机端统计栏(.toolbar)不固定 ③把训练进化做成脚本化/模板化闭环(gen_next_round 确定性拼下一轮 prompts + run_round 出图，不依赖临场推理) ④小批量真跑 3 个代表写法号(L1 免费KEY)证明闭环跑通。

---

## 一、功能清单

- F1 面板每写法号「合并建议」下新增「提示词修正意见」可编辑块（自然语说明 + 修正后prompt 两栏），老板在浏览器(含手机)手填。
- F2 保存端点：面板「保存修正」→ `agnes_proxy` POST `/batch/api/correction` → 写回 `writing_purpose.csv`(新增两列)，闭环可持久。
- F3 手机端 `.toolbar`(统计区) 在 `max-width:768px` 下 `position:static`，桌面端保持 `sticky` 不变。
- F4 进化脚本：`scripts/evolution/gen_next_round.py`(确定性读修正→产下一轮 prompts，零 LLM) + `run_round.py`(读 round prompts→出图，参数同 run_batch001)。
- F5 资产路由泛化：支持 `batch-002` 等多批次，线上 8787 经 `/batch/__asset__/<batch>/<kind>/<file>` 可达。
- F6 小批量验证：用 sample 修正 CSV(写法2 进门修正示例)→ gen_next_round → run_round --styles 2,9,17(L1)→ 6 张 batch-002 图 → 新增 batch-002 面板 → 线上验证图不裂。

---

## 二、需求清单（验收标准 AC 锚点）

- [ ] AC-1.1 `writing_purpose.csv` 新增列 `提示词修正意见`、`修正后prompt`（保留 UTF-8 BOM + 原三列）；`read_writing_purpose` 读取并存入 dict(`note`/`next_prompt`)；缺列时降级不崩。
- [ ] AC-1.2 `render_groups` 每写法号「合并建议」+「两张图生成参数对比」下新增「提示词修正意见」可编辑块：①自然语 textarea 属性 `data-correction-writing="X"`(**禁止用** `data-writing` 以免污染 `DATA_WRITING_RE==27`) ②「修正后prompt」textarea；wp-corr 块数 == group_count(27)。
- [ ] AC-1.3 `agnes_proxy.py` 新增 POST `/batch/api/correction`：body `{writing:int, note:str, next_prompt:str}`；校验 writing∈1..27、next_prompt 不含路径穿越/超长；更新 `writing_purpose.csv` 对应行(保留其他列与其他行顺序)；成功 200 JSON，非法 400/403；写盘后仍为 UTF-8 BOM、列完整。
- [ ] AC-1.4 面板「💾 保存修正」按钮(每写法号块内) → `fetch('/batch/api/correction',{method:POST,json})` → 成功轻提示 + 把 note/next_prompt 写回 DOM；失败提示错误。
- [ ] AC-1.5 手机端 CSS：`<style>` 新增 `@media (max-width:768px){ .toolbar{ position:static; top:auto; box-shadow:none; } }`；grep 验证该 `@media` 规则存在且含 `.toolbar`；桌面 `.toolbar` 仍 `sticky`。
- [ ] AC-1.6 新增 `scripts/evolution/gen_next_round.py`：参数 `--src-round`(默认 batch-001 out) / `--corrections <csv>`(写法号,next_prompt，可空) / `--out`(默认 round_002)；逻辑：每写法号若 `next_prompt` 非空→用其值，否则沿用 round_001 full prompt；写 `out/prompts.csv`(写法号,prompt) + `out/round_status.csv`(写法号,本轮是否修正,连续无修正轮次,成型标志) + 打印 diff 摘要(改动/沿用计数)。**纯确定性、零 LLM、零额度**。
- [ ] AC-1.7 新增 `scripts/evolution/run_round.py`：参数 `--round <dir>`(含 prompts.csv) / `--styles 2,9,17`(限制写法号) / `--out <dir>`；读 prompts.csv → `agnes_client.image_to_image(prompt, REF, size="2K", ratio="9:16")`(use_test 免费KEY) → 落盘 `<out>/wXX_Y.png`；跳过已存在；每 5 张报平安；图像参数与 run_batch001 完全一致。
- [ ] AC-1.8 资产路由泛化：`_serve_batch_asset` 支持 `<batch>` 段(`/batch/__asset__/<batch>/<kind>/<file>`，batch∈{batch-001,batch-002,...} 白名单映射目录)；`build_training_panel.py` 的 `ASSET_BASE` 支持按 batch 生成 URL。
- [ ] AC-1.9 小批量验证闭环：用 sample 修正 CSV(写法2 进门修正示例，老板原话)跑 gen_next_round → run_round --styles 2,9,17(L1 免费KEY，零 VIP) → 产 6 张 batch-002 图 → 新增 batch-002 面板(`build_training_panel.py --batch batch-002`) → 线上 8787 验证 batch-002 图 200 不裂；sample CSV 与真实 `writing_purpose.csv` **分离**(不污染老板手填数据)。
- [ ] AC-1.10 铁律按 batch 参数化自检通过：batch-001 面板 = `<img>`56/候选缩略图54/唯一wXX_Y 54/真实base64 0/`data-writing`去重27/`class="writing-purpose"`27/wp-corr 27/中文目录URL(`01_配方训练`)0；batch-002 面板 = 其自身计数(img 8/thumb 6/唯一 6/0 base64/3 组/3 wp-corr/0 中文目录)。`self_check` 必须 batch 感知。

---

## 三、产出路径

- 新增：`scripts/evolution/gen_next_round.py`、`scripts/evolution/run_round.py`、`scripts/evolution/sample_corrections.csv`、`01_配方训练/实验批次/batch-002/out/`(出图产物)、`training_panel_002.html`(或 build_training_panel.py 支持 `--batch` 生成)。
- 改动：`build_training_panel.py`(读新列+渲染可编辑块+手机 CSS+`--batch` 参数化+self_check batch 感知)、`agnes_proxy.py`(POST `/batch/api/correction` + 资产路由泛化 `<batch>` 段)。
- 不动：`run_batch001.py`(batch-001 已定稿，仅作参考)、现有 54 张 batch-001 图、训练逻辑/剧本生成链路。

---

## 四、边界与禁止项

- 禁止：L0 阶段烧 VIP(真测一律 `agnes_client._pool.use_test()`)；改 batch-001 已落盘图；手改生成的 HTML(单源由 build_training_panel.py 生成)；在 textarea 用 `data-writing` 属性(污染铁律计数)。
- 禁止：`/batch/api/correction` 端点接受任意路径/文件名(next_prompt 仅作文本存入 CSV，绝不拼路径)；writing 超出 1..27 直接 400。
- 已知坑(主理人提示，开发必须处理)：
  1. **铁律锚点敏感**：任何新增 `<img>`/改变 `data-writing` 计数都会破 T-15~T-18 铁律。修正块用 `data-correction-writing`(非 `data-writing`)；新增 textarea 不是 `<img>`，不增 img 计数；wp-corr 块须 == group_count。
  2. **中文目录 URL 根因(T-18)**：所有图片 src 必须走 `/batch/__asset__/<batch>/<kind>/<file>` 纯 ASCII；batch-002 出图目录含中文(`01_配方训练`)，**绝不可**直接拼中文路径进 HTML，必须走泛化后的 ASCII 资产路由。
  3. **CSV BOM/列顺序**：`writing_purpose.csv` 是 UTF-8 BOM，端点写回须保留 BOM 与全部列(测试目的/合并建议/提示词修正意见/修正后prompt)及行顺序，否则面板 DictReader 错位。
  4. **use_test 调用方式**：模块级无 `agnes_client.use_test()`，须 `agnes_client._pool.use_test()`(见主理人守则 G0-5/I-2)。
  5. **手机端只动 .toolbar**：boss 明确"头部展示数据时候"指统计栏(.toolbar)，hero 头部不动；仅 `@media (max-width:768px)` 下改 static，桌面 sticky 不变。

---

## 五、闸1 签核（老板）

- 老板确认验收标准(逐条)：☑ 已签（本会话指令 + 两问答复视同）
- 备注：q-0=机制+小批量验证(含写法2 进门修正)；q-1=修正意见老板手填(面板可编辑+保存落盘，进化不依赖阿编临场推理)。全量 54 张 batch-002 待老板确认后再跑。
