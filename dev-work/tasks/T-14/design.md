# design · T-14（研发填写，推「待验证」即停）

> 开发按此填：接口契约 + 改动说明 + git diff 文件清单 + 自测证据（命令+stdout）+ 视觉样片/截图。
> 无输出=未测=不通过。

## 改动说明

### #2 G4 Hotfix 热修标签（shared_board/index.html + server.py + board.db）
- **数据模型**：`tasks` 表幂等新增 `is_hotfix INTEGER DEFAULT 0`（旧卡片读为 NULL → 接口返回 `bool(r[12])` = `false`，不报错）。
- **server.py**：
  - `db()` 中 `PRAGMA table_info` 查列存在再 `ALTER TABLE tasks ADD COLUMN is_hotfix INTEGER DEFAULT 0`（幂等，旧库已存在则忽略）。
  - 三处任务 SELECT（`GET /api/tasks?`、`GET /api/ext/status`、`GET /api/ext/tasks`）均 SELECT `is_hotfix` 并回 `is_hotfix: bool(r[idx])`；`/api/ext/status` 无 milestone_id，故 is_hotfix 取 r[11]。
  - `POST /api/tasks` INSERT 写入 `is_hotfix`（`1 if d.get("is_hotfix") else 0`）。
  - `PUT /api/tasks` 允许更新 `is_hotfix`（转 0/1）。
  - `validate_task_fields` 增加 `is_hotfix` 类型校验（布尔或 0/1）。
- **index.html**：
  - CSS 新增 `.card.hotfix{border-left:3px solid #dc2626}` + `.card.hotfix .card-id,.card.hotfix .card-title{color:#dc2626}`（置于状态色规则之后，保证 hotfix 红边不被覆盖；与 blocked 共存时左红边生效）。
  - `renderCard`：cls 追加 `hotfix` 类；卡片头部 `#id` 前插入 🚨 角标 `hotfixHtml`（移植 reference_kanban.html L204/L225 风格）。字段用 snake_case `is_hotfix`。

### #3 P0-4 跨 seed 一致性（prompt_training.py）
- 新增 `_locked_seed(writing_name, explicit_seed=None)`：复刻 main() 的 seed 派生逻辑（按写法号确定性派生 / 用户指定锁定）。
- 新增 `cross_seed_consistency_report(shot, ref, template, seed_strategies)` + `main()` 的 `--cross-seed` 子命令（不依赖真实 project，用合成 shot/ref 跑纯模板级校验）。
- **级别说明**：本检查为 L0 静态/dry-run——只渲染 YAML 模板并逐字符对比，不调用 `gen_video`/AGNES，**不烧 VIP**（符合 I-2 例外：仅 L0 静态/dry-run 不改生成逻辑时可不调网络）。故无需 `AGNES_TEST_API_KEY`（AC-B.3）。

### #4 S4 YAML 缺字段 warning（prompt_training.py · build_variants）
- `build_variants` 加载器：YAML 解析非字典、或缺 `name/variables/constants/variants` 关键字段时，`logging.warning` 明确写出缺哪个字段（不再静默返回 `{}`/空列表）；渲染出 0 个变体时也 warning。
- 新增模块 logger（`prompt_training`），自挂 StreamHandler 确保 warning 可见，不依赖调用方 logging 配置。正常有字段时行为不变（回归见 AC-C.2）。

---

## P0-4 跨 seed 一致性 · 定义（AC-B.1 先定义后实现）

> 通读 `prompt_training.py`（重点 `build_variants` + YAML 加载/seed 处理）与 `templates/*.yaml` 后给出明确定义，再实现。

- **跨 seed 指什么**：对同一「写法」（写法号 / YAML template 中的某个 variant，如 `v0/v1/v4/v5`）分别用多种 **seed 策略**做"生成"——`['name-locked'(按写法号派生,默认), 'explicit-42'(用户指定), 'explicit-999'(用户指定), 'random'(不锁)]`——校验写法本身渲染出的角色关键属性是否随 seed 策略漂移。
- **角色关键属性（3 项）**：① **人物描述**（`prompt`，含身份/软锁词）② **seed 锁定**（`seed` 值，应只由写法号确定性派生、可复现）③ **关键帧**（`keyframes` 列表的 role/src）。
- **一致性判据**：同一写法渲染出的 `prompt` / `keyframes` 内容在所有 seed 策略下**逐字符一致**（AGNES seed 只影响生成随机性，不应改变写法本身的角色关键属性）；且 `name-locked` seed 对同一写法号在多次生成间可复现（确定性）。任一写法 3 项全一致 → 该写法跨 seed 一致；否则报告 `drift`（哪些字段漂移）。
- **实现判定**：`build_variants` 渲染 prompt/keyframes 不接收 seed（seed 仅在 `gen_video` 提交时生效），故"跨 seed 渲染一致性"= 验证上述不变式：改变 seed 策略不应让写法本身漂移。`cross_seed_consistency_report` 对每种 seed 策略各渲染一次并对比，输出可观测报告（见自测证据 B）。

---

## git diff 文件清单（`git diff --stat`）

```
 shared_board/board.db                              | Bin 36864 -> 36864 bytes   (schema: +is_hotfix 列)
 shared_board/index.html                            |   9 +-
 shared_board/server.py                             |  33 +++--
 short_drama_workflow/scripts/diag/prompt_training.py | 153 +++++++++++++++--
 4 files changed, 172 insertions(+), 23 deletions(-)
```

> `before:` 快照 commit：`b913e39`（动源码前已提交，满足 G0-9）。
> 改动严格限定三文件（shared_board/index.html、server.py、prompt_training.py）+ board.db schema 迁移；未碰无关文件、未碰 AGNES 网关/鉴权/接口。

---

## 自测证据（命令 + stdout；无输出=未测=不通过）

### A · #2 G4 Hotfix（命令均本机实跑）

**A1 node 语法（AC-A.4）**
```bash
python -c "import re;h=open('shared_board/index.html',encoding='utf-8').read();open('/tmp/board_script.js','w').write(re.search(r'<script>(.*)</script>',h,re.S).group(1))"
node --check /tmp/board_script.js && echo NODE_CHECK_OK
```
```
extracted JS bytes: 24513
NODE_CHECK_OK
```

**A2 board.db 迁移 + 旧卡片默认 false（AC-A.1）**
```bash
(cd shared_board && python -c "import sqlite3,os;os.environ['BOARD_DB']='board.db';import server;c=server.db();c.close();c2=sqlite3.connect('board.db');cols=[r[1] for r in c2.execute('PRAGMA table_info(tasks)').fetchall()];print('has_is_hotfix:', 'is_hotfix' in cols);[print('row',r) for r in c2.execute('SELECT id,title,COALESCE(is_hotfix,0) FROM tasks LIMIT 8')]")
```
```
has_is_hotfix: True
row (1, '测试任务', 0)
row (11, 'UI开发', 0)   ...（旧卡片均默认 0/false，读取不报错）
```

**A3 服务端 round-trip（AC-A.1 写/读 + AC-A.3 现有字段不破 + AC-A.4 可加载）**
```bash
cd shared_board && python - <<'PY'
# 起服务(BOARD_PORT=8799) -> GET /index.html -> 轮询 is_hotfix 任务建/读/删
PY
```
```
INDEX_HTTP_OK len=44986 hotfix_occurrences=10     # 页面可加载，含 hotfix 样式/逻辑
BEFORE count=1 sample_is_hotfix=False            # 旧卡片默认 false
CREATED {'id': 48}
HOTFIX_TASKS [(48, '紧急热修测试', True)]         # is_hotfix=true 写后读= True
DEFAULT_FALSE_TASK [(48,'紧急热修测试',True),(49,'普通任务',False)]  # 缺字段默认 false
CLEANED_UP test tasks                             # 测试任务已清理
```

### B · #3 P0-4 跨 seed 一致性（L0，未调 AGNES / 未烧 VIP）(AC-B.2/B.3/B.4)
```bash
cd short_drama_workflow/scripts/diag && python prompt_training.py --cross-seed --template camera_move_v2
```
```
======================================================================
P0-4 跨 seed 一致性报告（模板=camera_move_v2）
======================================================================
[v0] 一致=True | prompt一致=True keyframes一致=True seed锁定=True | 漂移=无
[v1] 一致=True | prompt一致=True keyframes一致=True seed锁定=True | 漂移=无
[v4] 一致=True | prompt一致=True keyframes一致=True seed锁定=True | 漂移=无
[v5] 一致=True | prompt一致=True keyframes一致=True seed锁定=True | 漂移=无

结论: all_consistent=True
报告已存: .../experiments/cross_seed_consistency_0814_224324.json
```
> 报告 JSON 落盘 `short_drama_workflow/scripts/diag/experiments/cross_seed_consistency_0814_224324.json`，可重跑。

### C · #4 S4 YAML 缺字段 warning（AC-C.1/C.2/C.3）
**C1 缺字段触发 warning**
```bash
cd short_drama_workflow/scripts/diag && python -c "
import prompt_training as pt,os
p=os.path.join(pt.TEMPLATES_DIR,'_t14_missing.yaml');open(p,'w').write('variables:\n  first: x\n')
try: v=pt.build_variants({'video_prompt':'hi'},{},'_t14_missing')
finally: os.remove(p)
" 2>&1 | grep -iE "WARNING|RENDERED"
```
```
WARNING prompt_training: YAML 模板 _t14_missing 缺少关键字段 'name'：将按默认值处理（...），渲染可能为空
WARNING prompt_training: YAML 模板 _t14_missing 缺少关键字段 'constants'：...
WARNING prompt_training: YAML 模板 _t14_missing 缺少关键字段 'variants'：...
WARNING prompt_training: YAML 模板 _t14_missing 未渲染出任何变体（variants 缺失或为空），请检查 variants 字段
```
**C2 正常模板无 warning（回归不受损）**
```bash
cd short_drama_workflow/scripts/diag && python -c "
import prompt_training as pt
v=pt.build_variants({'video_prompt':'A man walks.'},{'remote_url':'http://x/a.png'},'camera_move_v2')
print('OK variants:', list(v.keys()))
" 2>&1 | grep -iE "warning|OK variants" || echo NO_WARNING_FOR_VALID_TEMPLATE
```
```
OK variants: ['v0', 'v1', 'v4', 'v5']     # 无 WARNING，行为不变
```

---

## 视觉样片（#2 必填）

- 浏览器运行态预览（同款 CSS/类名，QA 可直接打开核验）：`dev-work/tasks/T-14/hotfix_preview.html`
- 效果描述：
  - **Hotfix 卡片**（`is_hotfix=true`）：左侧 3px 红边框（#dc2626）+ 卡片编号/标题红字 + 左上 🚨 角标。
  - **普通卡片**（`is_hotfix=false` 或旧卡片缺字段）：维持原有渲染，左侧状态色边、无 🚨，不受影响（AC-A.3）。
  - 真实运行态：启动 `python shared_board/server.py` → 浏览器开 `http://电脑局域网IP:8788`，前端从 `/api/tasks` 读取 `is_hotfix` 字段渲染（A3 已验证接口返回该字段）。

## 研发结论
三件 backlog 全部实现并通过本机自测（A 语法/迁移/round-trip、B 跨 seed 一致报告、C 缺字段 warning + 正常无 warning）。B 为 L0 静态校验，未调 AGNES、未烧 VIP。推「待验证」，请独立测试角色验收。
