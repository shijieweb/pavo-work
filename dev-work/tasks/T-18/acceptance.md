# T-18 acceptance.md（主理人把关填）

> 任务：根治外网图裂（中文目录 URL 被隧道/代理层拒载）+ 每写法号合并建议下加「两张图生成参数对比」行。
> 状态推进：开发→待验证（software-engineer）→ 已验证（software-qa-engineer 独立验收 24 检查点全 PASS·0 BUG）→ **完成（主理人 §4.3 读盘核产·2026-08-15）**。

## 验收对照表（主理人 §4.3 读盘核产逐条勾证）

| AC | 验收点 | 证据（主理人亲跑命令取真 stdout，非盲信自报） | 结论 |
|----|--------|----------------------------------------------|------|
| AC-1.1 | 纯 ASCII 资产路由生效 `/batch/__asset__/cand|ref/<文件名>` 全 200 image/png | 主理人 `verify_live.py` 实跑线上 8787(PID 26628)：54 候选图 200/image/png=**54/54**、2 参考图 200/image/png=**2/2** | ✅ PASS |
| AC-1.2 | 铁律锚点不变（img=56 / thumb=54 / 唯一 wXX_Y=54 / base64=0 / 中文锚点=54 / data-writing=27 / writing-purpose=27） | 主理人读盘核产（精确 matcher）：`<img>`=56；候选缩略图 `<img data-role="thumb">`=**54**（含 1 处 JS 选择器 `[data-role="thumb"]` 非 img，已甄别）；唯一 `wXX_Y.png`=54；**真实内嵌 `data:image/..;base64,`=0**（原文 4 处 "base64" 均为 CSS/HTML 注释文本，非图像数据）；中文锚点「同一个齐肩黑发」=54；`data-writing` 去重=27；`class="writing-purpose"` 分组块=**27**（原文 33 含 6 行 CSS 规则，已甄别） | ✅ PASS |
| AC-1.3 | 每写法号「合并建议」下加「两张图生成参数对比」行（无区别写无区别） | 主理人读盘：`class="wp-cmp"` 计数=**27**（= 写法号组数 27）；文本内容"两张图生成参数对比：无区别（prompt / 参考图 / size=2K / ratio=9:16 / 负向词 NEG 全部相同，仅模型随机种子不同，未显式传入）"，与事实源 `run_batch001.py` 一致（同写法两图调用参数全同、仅随机种子未显式传入） | ✅ PASS |
| AC-1.4 | 中文目录 URL 清零（HTML 全文 `01_配方训练`=0） | 主理人读盘：`/batch` 返回 HTML 181,486 B，`01_配方训练` 出现次数=**0**；全部 54 候选 src=`/batch/__asset__/cand/wXX_Y.png`、2 参考 src=`/batch/__asset__/ref/charA_*.png`（纯 ASCII） | ✅ PASS |
| AC-1.5 | 隔离 8799 验证通过后再切线上 8787 净重启生效 | 研发隔离实例 8799 全绿（`t18_verify_8799.py`）；线上旧 8787(PID 24592) 已 kill → 新 8787(PID 26628) 加载 T-18 新代码；路由注册表 35 条、`:8777`/`:8788` 复用既有进程未误杀 | ✅ PASS |
| AC-1.6 | before 提交 | `git log`：`86d6f49 before: T-18 batch __asset__ route` → `5038825 T-18: agnes_proxy 新增 /batch/__asset__ 纯 ASCII 资产路由` | ✅ PASS |
| AC-1.7 | 安全：防穿越 / 白名单 kind / 非 png / 不存在 | 主理人实跑：`/batch/__asset__/cand/../agnes_proxy.py`→**403**；`/batch/__asset__/evil/x.png`→**403**；`/batch/__asset__/cand/prompts.csv`→**403**；`/batch/__asset__/cand/nope.png`→**404** | ✅ PASS |
| AC-1.8 | 既有 6 路由零回归 | 主理人实跑：`/`、`/board`、`/batch`、`/hub.html`、`/studio`、`/api/spec` 全部 **200**（含 studio 反代 / board 反代 / api 反代完好） | ✅ PASS |

## 主理人读取结论

**✅ 放行（完成）。** 全部 AC-1.1~1.8 PASS；线上 8787（PID 26628）经 `verify_live.py` 实测全绿，铁律锚点经精确 matcher 核产全部达标（含对 3 处表面"偏差"——55 thumb / 33 writing-purpose / 4 base64——的逐一甄别，确认均非真实回归）。

研发/测试分离铁律已守：开发推「待验证」即停、测试推「已验证」即停、主理人把关标「完成」。

## 关键甄别说明（避免误判为 FAIL）

| 表面计数 | 初看 | 精确核产结论 |
|----------|------|--------------|
| `data-role="thumb"` = 55 | 似超铁律 54 | 实际候选缩略图 `<img>` = **54**；第 55 处是 JS 点击处理器选择器 `ev.target.closest('[data-role="thumb"]')`（L877），非 img → 铁律 54 成立 |
| `writing-purpose` = 33 | 似超 27 | **27** 个分组块 `class="writing-purpose"` + 6 行 CSS 规则（` .writing-purpose {` 等）→ 27 组成立 |
| `base64` = 4 | 似有内嵌图 | 真实 `data:image/..;base64,` = **0**；4 处 "base64" 全是注释文本「不引入 img/base64 内嵌」→ 0 内嵌图成立 |

## 证据文件

- `dev-work/tasks/T-18/verify_live.py` — 主理人线上 8787 全量核验脚本（54 候选 + 2 参考 + 安全 + 6 路由 + wp-cmp），输出 `ALL PASS ✅`
- `t18_verify_8799.py` — 研发/QA 隔离实例 8799 核验脚本（不动线上）
- 线上验证输出见主理人 Bash 实跑 stdout（181486 B / zh_dir=0 / cand 54/54 / ref 2/2 / 安全 403·403·403·404 / 回归 6/6 200 / wp-cmp 27）
