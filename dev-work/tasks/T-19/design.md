# design · T-19 训练提示词修正意见(可编辑)+手机端头部优化+脚本化进化闭环

> 模板来源：`dev-work/templates/TEMPLATE_DESIGN.md`。**开发填写**，推「待验证」时一并交付。
> 铁律：无输出 = 未测 = 不通过。以下每节都填真实内容，禁止空话。
> 角色纪律（主理人守则 G0-5 / I-2）：开发只做开发 + L0 自测，推「待验证」，无 done 权限；L1 真出图走测试角色免费 TEST KEY，开发不烧额度、不调用 `gen_video`。

---

## 一、实现方案

### 1.1 总思路
T-19 是把「训练面板 → 老板手填修正意见 → 落盘 CSV → 脚本确定性拼下一轮 prompt → 出图 → 再进面板」这条**进化闭环**从半手工变成脚本化、可复跑；同时把资产路由从单批次硬编码泛化成多批次白名单，并把面板在手机端的统计栏 `.toolbar` 改为非 sticky（仅 ≤768px，桌面 sticky 不变）。

### 1.2 关键改动点 & 为什么

**① 每写法号「提示词修正意见」可编辑块（AC-1.1 / AC-1.2 / AC-1.4）**
- 在 `render_groups()` 每个写法号的「合并建议」下，追加 `.wp-corr` 块：一个自然语 `textarea`（data-role=correction-note）+ 一个修正后 prompt `textarea`（data-role=correction-prompt，预填 `next_prompt`）+ 一个「💾 保存修正」按钮。
- **铁律不变式保护**：修正块所有 data 属性一律用 `data-correction-writing`（绝不蹭 `data-writing`）。否则会污染 `DATA_WRITING_RE` 去重计数 `== 27` 的不变式，被 self_check 抓出来。textarea 是文本非 `<img>`，不增 img 计数。
- `self_check()` 新增：`wp-corr` 块数 `== group_count`（batch-001=27 / batch-002=3）；且追加修正块后复验 `data-writing` 去重仍 `== group_count`。
- `read_writing_purpose()` 新增读取「提示词修正意见」「修正后prompt」两列；列缺失时降级为空串，不中断构建（AC-1.1 兼容旧 3 列 CSV）。

**② POST /batch/api/correction 端点（AC-1.3）—— 落盘闭环**
- 在 `agnes_proxy.py` 的 `do_POST` 中、`/api/hub/start-studio` **之前**插入 `if path == "/batch/api/correction": self._serve_correction(data)`。
- **关键 bug 修复**（L0 真测发现）：`do_POST` 已把请求体读进 `data`，**禁止**在 `_serve_correction` 里再 `self.rfile.read()`，否则 `ConnectionResetError` / 10054 挂起。改为 `_serve_correction(self, data)` 直接吃 `data` 里的字节。
- `_update_writing_purpose()`：utf-8-sig 读 → 确保两列存在 → 按 `int(写法号)` 精确匹配行更新 → 缺失则追加 → 原子写（`.tmp` + `os.replace`），**保留 UTF-8 BOM、全部列、行序、其它行内容**。
- 前端 `saveCorrection(block, btn)`：fetch POST `{writing, note, next_prompt}`，成功写回 DOM 文案（轻提示「✅ 已保存」），失败提示错误。按钮 wired 进 `#groups` 监听器（在 `.switch button[data-set]` 之前）。

**③ 资产路由泛化（AC-1.8）—— 多批次**
- `cand_url/ref_url(file, batch=None)`：URL 从 `/batch/__asset__/cand/<file>` 升级为 `/batch/__asset__/<batch>/cand/<file>`（多带一个批次段）。
- 代理 `_serve_batch_asset` 改为匹配 `/batch/__asset__/<batch>/<kind>/<name>`（3 段），白名单 `BATCH_DIRS={"batch-001":..., "batch-002":...}` 校验 `batch_id` 与 `kind∈{cand,ref}`，含路径穿越防护；cand→`BATCH_DIRS[batch]`，ref→共用 `BATCH_REF_DIR`。

**④ 脚本化进化机制（AC-1.6 / AC-1.7）—— 零 LLM**
- `scripts/evolution/gen_next_round.py`：读 `src-round/prompts.csv`（写法号→本轮全 prompt）+ `writing_purpose.csv` 的「修正后prompt」，叠加 `--corrections`（写法号,next_prompt）覆盖。每写法号：`next_prompt` 非空 → 用修正值；否则沿用 round_001 prompt。**纯字符串确定性拼装，零 LLM、零网络、零 KEY**。输出 `prompts.csv`（写法号,prompt）+ `round_status.csv`（写法号,本轮是否修正,连续无修正轮次,成型标志）。
- `scripts/evolution/run_round.py`：读 round `prompts.csv`，按 `--styles` 过滤，每写法 `REPS_PER_WRITING=2` 张，调 `agnes_client.image_to_image(prompt, REF_data_uri, size="2K", ratio="9:16")` 出图，参数与 `run_batch001` 一致。`--dry-run` 只列计划（含已存在跳过逻辑）、**不 import agnes_client / 不读 KEY / 不调 API**；真出图才 `sys.path.insert` 注入 `agnes_client` 并 `agnes_client._pool.use_test()`（免费 TEST KEY，零 VIP）。

**⑤ 手机端 `.toolbar` 非 sticky（AC-1.5）**
- `build_training_panel.py` 的 `<style>` 中在 1000px 媒体查询**之前**新增：
  ```css
  @media (max-width: 768px) {
    .toolbar { position: static; top: auto; box-shadow: none; }
  }
  ```
- 桌面（>768px）sticky 行为完全不变。

### 1.3 与现有逻辑兼容
- `build_training_panel.py` 新增 `--batch`（默认 `batch-001`）参数；不设参时行为与改动前 100% 一致（输出 `training_panel.html`）。
- 旧 3 列 `writing_purpose.csv` 仍能构建（新列缺省降级为空串）。
- 面板 img 计数不变式（img 数 = PNG 数 + 2 ref / base64=0 / data-writing=27）在所有批次下仍成立（self_check 双重复验）。

---

## 二、接口契约

### 2.1 面板生成器（build_training_panel.py）
| 项 | 说明 |
|---|---|
| 函数签名 | `def set_batch(batch_id: str) -> None`；`def cand_url(file, batch=None)`；`def ref_url(file, batch=None)` |
| 输入字段 | `--batch`：批次目录名（`batch-001`/`batch-002`，默认 `batch-001`） |
| 输出字段 | 生成 `training_panel.html`（默认批次）或 `training_panel_<batch>.html`；HTML 内 `data-correction-writing` 锚定每块修正 |
| 下游消费方 | 浏览器面板（老板手填）→ JS `saveCorrection` → POST 代理 |

### 2.2 代理端点（agnes_proxy.py）
| 项 | 说明 |
|---|---|
| 路由 | `POST /batch/api/correction` |
| 请求体 | `{"writing": int, "note": str, "next_prompt": str, "batch"?: str}`（`batch` 缺省 `batch-001`） |
| 校验 | writing∈1..27 整数；note/next_prompt 为 str；next_prompt 禁 `../` `..\` 开头 `\x00` 超长 20000；batch 须白名单 |
| 输出字段 | 成功 `200 {"ok":true,"writing":int,"batch":str}`；非法 `400 {"ok":false,"error":str}`；写盘失败 `403 {"ok":false,"error":str}` |
| 副作用 | 原子写回 `<BATCH_DIRS[batch]>/writing_purpose.csv` 对应写法号行的「提示词修正意见」「修正后prompt」（保留 BOM/列/行序） |
| 下游消费方 | 面板 JS（写回后轻提示 + 更新 DOM textarea 值） |

### 2.3 进化脚本（scripts/evolution/）
| 脚本 | 函数签名 / CLI | 输入 | 输出 | 下游 |
|---|---|---|---|---|
| `gen_next_round.py` | `--src-round`(默认 `01_配方训练/实验批次/batch-001/out`) `--corrections <csv>` `--out`(默认 `round_002`) | src prompts.csv + writing_purpose.csv + corrections.csv | `<out>/prompts.csv`(写法号,prompt) + `<out>/round_status.csv` | `run_round.py --round` |
| `run_round.py` | `--round <dir>`(必填) `--styles 2,9,17` `--out <dir>` `--dry-run` | round prompts.csv + 角色参考图 | 出图 PNG + `<out>/prompts.csv` | 下一轮面板（batch-002） |

---

## 三、自测证据（铁律：无输出 = 未测 = 不通过）

### 3.1 改动文件清单（git diff）
> WorkBuddy 仓库是 git 仓库；training 项目无 git，用 `.bak` 时间戳快照作 before-snapshot（见 `dev-work/tasks/T-19/build_training_panel.diff.txt`）。

```
# agnes_proxy.py (git 仓库，可 diff)
 agnes_proxy.py | 146 ++++++++++++++++++++++++++++++++++++++++++++++++++++-----
 1 file changed, 133 insertions(+), 13 deletions(-)

# build_training_panel.py (training 项目无 git)
#   before-snapshot: 01_配方训练/实验批次/.../build_training_panel.py.bak.20260815_165626
#   diff 已落盘:     dev-work/tasks/T-19/build_training_panel.diff.txt  (246 行, +188 / -26)
# 新增: scripts/evolution/gen_next_round.py / run_round.py / sample_corrections.csv
```

### 3.2 本机跑测试的真实命令 + stdout

**A. gen_next_round 确定性（AC-1.6）**
```
> python scripts/evolution/gen_next_round.py --src-round "01_配方训练/实验批次/batch-001/out" --corrections scripts/evolution/sample_corrections.csv --out round_002
[gen_next_round] src        = 01_配方训练/实验批次/batch-001/out
[gen_next_round] corrections= scripts/evolution/sample_corrections.csv
[gen_next_round] out        = round_002
[gen_next_round] 总写法号    = 27
[gen_next_round] 改动(用修正值) = 1
[gen_next_round] 沿用(本轮prompt) = 26
[gen_next_round] -> 已写 prompts.csv / round_status.csv
# 结论: writing 2 走 sample_corrections 的修正值, 其余 26 沿用 round_001 prompt (确定性, 零 LLM)
```

**B. run_round --dry-run（AC-1.7，不烧 KEY）**
```
> python scripts/evolution/run_round.py --round round_002 --styles 2,9,17 --out "01_配方训练/实验批次/batch-002/out" --dry-run
[run_round][dry-run] 将生成 6 张 -> 01_配方训练/实验批次/batch-002/out
  [plan] w02_1.png  (写法 2, 已存在·跳过)
  [plan] w02_2.png  (写法 2, 已存在·跳过)
  [plan] w09_1.png  (写法 9, 已存在·跳过)
  [plan] w09_2.png  (写法 9, 已存在·跳过)
  [plan] w17_1.png  (写法 17, 已存在·跳过)
  [plan] w17_2.png  (写法 17, 已存在·跳过)
[run_round][dry-run] 未调用任何 API / 未烧 KEY / 未 import agnes_client
# 结论: 6 张计划正确, 跳过逻辑生效, 真跑时只会对缺失图调用 image_to_image(use_test)
```

**C. 双批次面板 self_check（AC-1.10，铁律按 batch 参数化）**
```
> python build_training_panel.py --batch batch-001   →  [自检] 全部通过 ✔ (56 img / 54 unique / base64=0 / data-writing=27 / wp-corr=27 / 中文目录字眼=0)
> python build_training_panel.py --batch batch-002   →  [自检] 全部通过 ✔ ( 8 img /  6 unique / base64=0 / data-writing= 3 / wp-corr= 3 / 中文目录字眼=0)
# 完整日志见 dev-work/tasks/T-19/selfcheck_batch001.txt / selfcheck_batch002.txt
# 关键计数对照 (AC-1.10 EXACT):
#   batch-001: img=56 thumb=54 unique=54 base64=0 wp-corr=27 data-writing=27 writing-purpose=27 中文=0
#   batch-002: img= 8 thumb= 6 unique= 6 base64=0 wp-corr= 3 data-writing= 3 writing-purpose= 3 中文=0
```

**D. 代理 live POST 测试（AC-1.3 / AC-1.4，代理 PID 5692 跑在 8787）**
```
# 备份真 CSV 后发 5 个用例, 再还原:
CASE 1 valid (writing=2):
  (200, '{"ok": true, "writing": 2, "batch": "batch-001"}')
CASE 2 writing=99:
  (400, '{"ok": false, "error": "writing 超出范围 1..27"}')
CASE 3 next_prompt="../etc/passwd":
  (400, '{"ok": false, "error": "next_prompt 含非法字符或超长"}')
CASE 4 batch="batch-999":
  (400, '{"ok": false, "error": "未知批次: batch-999"}')
CASE 5 writing="abc":
  (400, '{"ok": false, "error": "writing 必须为 1..27 整数"}')
# 写回验证: CASE1 后 写法号=2 行 提示词修正意见='L0自测:明确进门动作' / 修正后prompt='S-... 进门 ...'
# 还原后: 行数=27, 两新列空, BOM 保留=True, 无 .t19bak 残留 ✔
```

**E. 手机端非 sticky 证据（AC-1.5）**
```
> grep -n "max-width: 768px" build_training_panel.py
425:  @media (max-width: 768px) {
# 该媒体查询内 .toolbar{position:static;...}, 仅 ≤768px 生效, 桌面 sticky 不变
```

### 3.3 关键运行日志 / 截图
- 双批次 self_check 全文：`dev-work/tasks/T-19/selfcheck_batch001.txt`、`selfcheck_batch002.txt`
- 面板 diff：`dev-work/tasks/T-19/build_training_panel.diff.txt`
- 代理 live 测试实测见 §3.2-D（5 例全绿，含写回验证与还原）
- 真 CSV 还原校验：`行数=27, 修正意见非空=0, 修正后prompt非空=0, BOM 保留=True`

### 3.4 可真跑的启动 / 调用命令
```bash
# 0) 起代理 (统一门户, 测试角色 L1 也走它)
cd C:/Users/67972/WorkBuddy/workbuddy && python agnes_proxy.py   # 默认 8787

# 1) 生成两个批次面板 (开发自测已跑通)
cd C:/Users/67972/projects/short-drama-training
python build_training_panel.py --batch batch-001      # -> training_panel.html
python build_training_panel.py --batch batch-002      # -> training_panel_batch-002.html

# 2) 进化闭环 (确定性, 零 LLM)
python scripts/evolution/gen_next_round.py --src-round "01_配方训练/实验批次/batch-001/out" \
       --corrections scripts/evolution/sample_corrections.csv --out round_002
python scripts/evolution/run_round.py --round round_002 --styles 2,9,17 \
       --out "01_配方训练/实验批次/batch-002/out" --dry-run   # 先 dry-run 看计划

# 3) 真出图 (L1, 测试角色执行, 走免费 TEST KEY; 开发不跑)
python scripts/evolution/run_round.py --round round_002 --styles 2,9,17 \
       --out "01_配方训练/实验批次/batch-002/out"

# 4) 浏览器开面板手填修正 -> 自动 POST /batch/api/correction -> 落盘 CSV
#    http://localhost:8787/batch/training_panel.html
#    http://localhost:8787/batch/training_panel_batch-002.html
```

---

## 四、提测说明（测试怎么接）

- **测试入口**：
  - L0（已自测）：见 §3.2 A/B/C/D/E，全绿。
  - L1 真出图：`python scripts/evolution/run_round.py --round round_002 --styles 2,9,17 --out "01_配方训练/实验批次/batch-002/out"`（走 `agnes_client._pool.use_test()` 免费 KEY，零 VIP）。
  - 代理已起在 `8787`（PID 5692，后台 nohup），测试角色可直接用 `http://localhost:8787/batch/...` 访问两面板并做手填→落盘回环。
- **待测范围（AC 映射）**：
  - AC-1.1：writing_purpose.csv 5 列 + 读取降级 — L0 已验。
  - AC-1.2：wp-corr 块数（27/3）+ data-correction-writing 不污染 data-writing — L0 已验。
  - AC-1.3 / AC-1.4：POST 端点 5 例 + 写回 + 前端 fetch — L0 已验端点与写回；**前端 fetch→按钮点击→DOM 回写** 建议测试角色在浏览器真点一次（开发 L0 只验了端点契约，未做真实浏览器点击）。
  - AC-1.5：手机 ≤768px `.toolbar` 非 sticky — L0 已 grep 证明；建议测试角色用 DevTools 设备模拟真看一眼。
  - AC-1.6 / AC-1.7：gen_next_round 确定性 + run_round 出图 — L0 验 dry-run；**L1 真出 6 张图** 由测试角色执行（AC-1.9）。
  - AC-1.8：batch-002 资产路由 — L0 已验 batch-002 面板 img src 全 ASCII、中文目录字眼=0、6 图全加载。
  - AC-1.9：小批量验证闭环 — 测试角色 L1 出 batch-002 的 3 写法号（2/9/17）共 6 张，确认 batch-001 线上面板不裂（AC-1.10 计数不变）。
  - AC-1.10：铁律按 batch 参数化自检 — L0 双批次全过。
- **已知限制（非阻塞）**：
  - 前端真实浏览器点击保存（AC-1.4 的 DOM 回写路径）开发仅验了端点契约，未做真浏览器端到端点击，列为测试角色 L1 必点项。
  - L1 真出图由测试角色用免费 TEST KEY 执行，开发未烧额度（主理人守则 G0-5/I-2）。
  - batch-002 当前 6 张 PNG 为 L0 结构占位（从 batch-001 w02/09/17 拷贝），非真实 round_002 出图；AC-1.9 的真图由测试角色覆盖。

---

## 五、文档回写

- [x] `design.md` 已填（本文件，含 git diff / 真实 stdout / 可复现命令）
- [ ] `current_state.md` AC 进度待更新（推「待验证」后由阿编/主理人更新）
- [ ] `acceptance.md`（`dev-work/tasks/T-19/acceptance.md`）待测试角色验收后由阿编勾
- [ ] `PRD.md` / `test.md` 未改动（需求无新增，仅扩展）
- 备注：代理 PID 5692 仍在后台运行（8787），供测试角色 L1 真出图与浏览器回环验证；如不需要可 `kill 5692`。
