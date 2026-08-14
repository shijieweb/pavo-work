# test · T-14（独立测试填写，推「已验证」即停，不修 bug）

> 测试独立验收（不盲信开发自报）+ 实跑。覆盖矩阵闭环，每条结论附证据（真实命令 + stdout）。
> 环境：Python 3.13.14 / Node v22.22.2；全程用 board.db 临时副本，未触碰生产库。
> 结论：**全部 11 条 AC 通过，无 P0/P1 缺陷。**

## 覆盖矩阵

| AC | 验证命令 | 证据（stdout 摘录） | 结果 |
|---|---|---|---|
| AC-A.1 | `python -c` 读 board.db `PRAGMA table_info(tasks)` + `SELECT id,title,COALESCE(is_hotfix,0)`；并对「已 DROP 列」的旧库起服务 GET 验证 | `A1_HAS_IS_HOTFIX: True`；旧卡 `A1_OLD_ROW: (1, '测试任务', 0)`…均 0/false；旧库(无列)`A1_OLD_DB_GET_OK count=1`、`A1_OLD_DB_ROW is_hotfix= False`（无报错） | 通过 |
| AC-A.2 | `grep -nE "card\.hotfix\|hotfixHtml\|🚨" shared_board/index.html` | L103 `.card.hotfix{border-left:3px solid #dc2626}`；L104 红字 `.card-id,.card-title{color:#dc2626}`；L465 `const hotfixHtml=(t.is_hotfix)?'<span …>🚨</span>':''`；L467 头部插入 `hotfixHtml` | 通过 |
| AC-A.3 | 起 `BOARD_DB=临时副本 BOARD_PORT=8799 python shared_board/server.py`，`X-Board-Token` 头 POST is_hotfix=true → GET 读回；再 POST 缺 is_hotfix 字段 → GET 默认 false；校验现有字段齐全 | `A3_CREATED_HOTFIX {'id':50}` → `A3_HOTFIX_READ …is_hotfix=True`；`A3_DEFAULT_READ …is_hotfix=False`；`A3_EXISTING_FIELDS_MISSING: NONE`（title/status/priority/author/updated/parent_id/detail/id 全在）；测试后删除临时库 | 通过 |
| AC-A.4 | `python -c` 抽取 `<script>`（全文仅 1 个 script 块，24513 字节）+ `node --check` | `extracted bytes: 24513` + `NODE_CHECK_OK` | 通过 |
| AC-B.1 | 读 `design.md`「P0-4 跨 seed 一致性·定义」段 + 代码 docstring | design.md L31-38 含完整定义（跨 seed 含义 / 3 项关键属性：人物描述·seed 锁定·关键帧 / 判据）；`prompt_training.py:cross_seed_consistency_report` docstring 同样先写定义再实现 | 通过 |
| AC-B.2 | `cd short_drama_workflow/scripts/diag && python prompt_training.py --cross-seed --template camera_move_v2` | `[v0/v1/v4/v5] 一致=True \| prompt一致=True keyframes一致=True seed锁定=True \| 漂移=无`；`结论: all_consistent=True` | 通过 |
| AC-B.3 | 代码独立复验 `--cross-seed` 分支（`prompt_training.py:443-458`）`return` 在 `gen_video`(:487)/`urllib.request.urlopen`(:402) 之前；离线运行 <1s 无网络 | 运行无任何 AGNES/网络调用，仅 `build_variants` 纯 YAML 模板渲染；符合 L0 静态校验、未烧 VIP | 通过（L0 静态） |
| AC-B.4 | 同上命令 + 读 `experiments/cross_seed_consistency_0814_225216.json` | 报告 JSON 落盘 `experiments/`；`writings:['v0','v1','v4','v5']`；`all_consistent: True`；全部 `consistent=True` | 通过 |
| AC-C.1 | 构造只含 `variables` 的 YAML（`name/constants/variants` 缺失）喂 `build_variants` | `WARNING prompt_training: YAML 模板 _t14_missing 缺少关键字段 'name'/'constants'/'variants'` ×3 + `WARNING … 未渲染出任何变体（variants 缺失或为空）`；`RETURNED_VARIANTS: []`（不再静默空） | 通过 |
| AC-C.2 | 正常 `camera_move_v2` 跑 `build_variants` | `OK variants: ['v0', 'v1', 'v4', 'v5']` 且**无 WARNING**（回归不受损） | 通过 |
| AC-C.3 | 上述两条命令均可重跑 | 两次运行均产出稳定 stdout（见 AC-C.1 / AC-C.2） | 通过 |

## 缺陷清单

**无 P0/P1 缺陷。** 全部 11 条 AC 独立实跑通过，无阻塞项。

## 备注（非阻塞 · S4，不阻塞放行，建议后续排期）

1. **迁移 DDL 未显式 commit（server.py:143-144）**：对「无 is_hotfix 列」的全新库，迁移在单次请求连接内生效（SELECT 成功、旧卡读 `false` 不报错），但进程终止后该 DDL 未落盘（独立连接复检列不存在）。因迁移为请求级幂等（`db()` 每次 `PRAGMA` 复检 + `try/except` 包 `ALTER TABLE`），运行时正确性不受影响；且生产 `board.db` 实测 `has_is_hotfix=True` 已含该列。建议 `db()` 在 `ALTER` 后加 `c.commit()` 以固化 schema。
2. **AC-B 报告打印两遍（cosmetic）**：因 `import server` 带入的日志 handler，跨 seed 报告既经 `[INFO]` 前缀输出一遍、又纯 `print` 一遍。不影响结果，建议去重。

## 测试结论

- 覆盖矩阵闭环：11/11 AC 通过。
- 证据可追溯：每条 AC 均亲自跑命令拿真实 stdout（见上表），未采纳研发自报。
- 推「**已验证**」即停，不修 bug；缺陷（若有）以 `[BUG]` 交回开发。本任务无 P0/P1，非阻塞 S4 已记备注。
