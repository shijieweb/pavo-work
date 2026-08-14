# T-12 · PRD：8787 门户补齐两个缺失入口（音效台 + 看板 API 说明）

> 任务卡目录：`dev-work/tasks/T-12/`
> 闸1 签核：**老板亲签（2026-08-14，AskUserQuestion q-0 选「音效台 + 看板API说明（推荐）」）**
> 白名单核验：本任务触碰「**新增功能**」→ 按主理人守则 §3 护栏② **无裁量权、禁自签**，已由老板亲口授权（原话："把这两个入口…放到 8787 那个主要的目录里面去…给它加个链接就可以了，让我能够点过去"）。未触碰 生成逻辑 / 生产数据 / 鉴权 / 大额度。

---

## 1. 背景与问题

老板从 8787 主门户（`hub.html`）进不去两个已存在的页面——门户上**没有卡片**，直接访问 8787 也 **404**：

| 页面 | 本地文件 | 门户卡片 | 8787 现状 |
|---|---|---|---|
| SoundsFree 音效生成器 | `soundsfree_home.html` | ❌ 无 | `GET /soundsfree` → **404** |
| 看板 API 说明页 | `shared_board/docs.html` | ❌ 无 | `GET /docs` → **404** |

门户现有 5 张卡片：调试台 `/console`、工作台 `/studio`、共享看板 `/board`、运行日志 `/logs`、训练台 `/training`。

## 2. 目标（一句话）

在 8787 主门户加两个**能点过去**的入口链接，让老板不用记端口/文件名即可打开音效台与看板 API 说明页。

## 3. 前置技术勘察结论（主理人已实测，工程师须复核不得推翻而不举证）

1. **`/board/docs` 已经可用**：`curl 8787/board/docs` → **HTTP 200**，正确返回《看板 API 说明页 · /docs》（8788 `server.py:218` 已实现 `/docs`，经现有 `/board/*` 反代透传）。
   → **结论：看板 API 说明入口零后端改动**，门户卡片直接指向 `/board/docs` 即可。**不要**新造 `/docs` 顶层路由（会与 board 反代重复，且 board 反代含 body `/api/`→`/board/api/` 重写逻辑，对 API 说明页文本有篡改风险）。
2. **`/soundsfree` 需新增后端路由**：属**本地静态页**，须与 `/logs`、`/training` **同构**用 `_serve_html`（`agnes_proxy.py` do_GET 内，位于 `_route_dispatch` 之前）。
   → **不要**写进 `route_registry.json`：该注册表 `kind` 仅 `board|generic|studio`，**全是反代类**（target 指后端端口），静态文件不适用。

## 4. 功能清单

| 编号 | 功能 | 落点 |
|---|---|---|
| F1 | 新增 `/soundsfree`、`/soundsfree.html` → 服务 `soundsfree_home.html` | `agnes_proxy.py` |
| F2 | 门户新增卡片「音效台」→ `/soundsfree` | `hub.html` |
| F3 | 门户新增卡片「看板 API 说明」→ `/board/docs` | `hub.html` |
| F4 | 两张卡片与现有 5 张卡片**视觉同构**（复用 `.card` 结构：标题 + 标签 + 端口注记 + 「进入 →」） | `hub.html` |
| F5 | 8787 净重启使新路由生效并复验 | 运维动作 |

## 5. 验收标准（AC 锚点 · 每条须附可重跑命令 + stdout）

- **AC-1.1 音效台路由通**：`curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8787/soundsfree` → **200**；`/soundsfree.html` 同为 200；响应 body 含 `SoundsFree`（证明是目标页非兜底页）。
- **AC-1.2 音效台卡片可点**：`curl -s http://127.0.0.1:8787/` 返回的 HTML 中含 `href="/soundsfree"` 的 `.card` 卡片，且卡片文案含「音效」。
- **AC-1.3 看板 API 说明卡片可点**：`curl -s http://127.0.0.1:8787/` 含 `href="/board/docs"` 卡片；且 `curl -s http://127.0.0.1:8787/board/docs` → 200 且 body 含 `看板 API 说明页`。
- **AC-1.4 零回归（现有入口全活）**：`/`、`/console`、`/studio`、`/board`、`/logs`、`/training` 逐个 curl → **全 200**；若仓库存在 8787 路由回归脚本（T-20260813-02 产出），须跑通并贴 exit code。
- **AC-1.5 边界零越界**：`git show --stat <commit>` 证明**仅改** `agnes_proxy.py` + `hub.html`（+ 本任务四文档）；`grep` 证明未新增 `route_registry.json` 条目、未改 `shared_board/**`、未出现 `gen_video`/`build_variants`/关键帧/`data_uri` 相关改动。
- **AC-1.6 重启姿势合规且服务存活**：8787 重启必须用 **Bash `nohup "$PY" agnes_proxy.py > 8787.log 2>&1 & disown`**（沙箱禁 `Start-Process`/`[Diagnostics.Process]`/PowerShell↔cmd 互调，`setsid` 不可用）；重启后 `ps -ef | grep agnes_proxy` 证明存活，且 AC-1.1~1.4 复验全过。
- **AC-1.7 证据铁律**：design.md / test.md 每条 AC 附**实跑命令 + 原始 stdout**；无输出 = 未测 = 不通过。

## 6. 产出路径

- 代码：`agnes_proxy.py`、`hub.html`
- 文档：`dev-work/tasks/T-12/design.md`（开发）、`test.md`（QA）、`acceptance.md`（QA 填结论 + 主理人把关）

## 7. 边界与禁止项（越界即退回）

- ❌ 禁改 `route_registry.json`（静态入口不入注册表；若工程师认为必须改，先停手报主理人并举证）
- ❌ 禁改 `shared_board/**`（看板侧零改动，`/docs` 已可用）
- ❌ 禁碰 `short_drama_workflow/**`、`gen_video`、`build_variants`、关键帧、`data_uri` 等生成链路
- ❌ 禁调用任何 AGNES 接口（本任务零额度消耗；G0-4 判定不触及生成逻辑 → **L0 层即可，无需 L1 真测**）
- ❌ 禁改动现有 5 张卡片的行为与链接
- ❌ 禁杀 8788 / 8777（老板正在用；仅允许净重启 8787）

## 8. 角色分工（I-4 铁律）

- **开发（software-engineer）**：实现 F1~F5 + 自测 → 写 `design.md` → 推「待验证」即停，**无 done 权**。
- **测试（software-qa-engineer）**：独立实跑 AC-1.1~1.7（不盲信开发自述）→ 写 `test.md` + `acceptance.md` 结论 → 推「已验证」即停，**不修 bug**。
- **主理人（阿编）**：读盘核产（git diff + 亲自 curl 双验证）→ 填 acceptance 把关结论 → 才可推「完成」+ 写操作审计行。

## 9. 风险与对策

| 风险 | 对策 |
|---|---|
| 重启 8787 导致老板正在用的门户短时中断 | 用 nohup+disown 快速起；重启前后各跑一次 6 入口 curl，确保 30 秒内恢复 |
| 新路由位置放错（放在 `_route_dispatch` 之后被反代吞掉） | 必须与 `/training` 同位置（`_route_dispatch` 之前），并以 AC-1.1 实测为准 |
| 误把 `/docs` 挂顶层与 board 反代冲突 | PRD §3 已明确：**只用 `/board/docs`**，不新造顶层 `/docs` |
