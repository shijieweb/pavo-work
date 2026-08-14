# acceptance · T-12 8787 门户补齐两个缺失入口（音效台 + 看板 API 说明）

> 模板来源：`dev-work/templates/TEMPLATE_ACCEPTANCE.md`。
> QA 部分由 software-qa-engineer 填写（2026-08-14）；「阿编把关结论」留空，由主理人亲自复验后填写。
> 铁律：每条 AC 必须附证据链接（到 design.md / test.md / 截图 / git commit）。

---

## 验收对照表（逐条勾，每条附证据）

| AC 编号 | 验收点 | 结果 | 证据链接 | 备注 |
|---|---|---|---|---|
| AC-1.1 | `/soundsfree`、`/soundsfree.html` 均 200 且 body 含 SoundsFree（真页面非兜底） | ✅ PASS | test.md §3.1（TC-1） | 字节数 34986=磁盘；`<title>` 含 SoundsFree |
| AC-1.2 | hub 含 `href="/soundsfree"` 卡片、文案含「音效」、卡片总数=7 | ✅ PASS | test.md §3.2（TC-2） | cards=7 = 基线5+新增2 |
| AC-1.3 | hub 含 `href="/board/docs"` 卡片；`/board/docs` 200 且含「看板 API 说明页」 | ✅ PASS | test.md §3.3（TC-3） | |
| AC-1.4 | 6 入口零回归；`/board` 反代完好（7 阶段里程碑）；`/studio` 反代完好（`/api/spec` 200）；docs 未被篡改（与直连 diff=0） | ✅ PASS | test.md §3.4（TC-4） | PRD §3 风险点实测未触发（OBS） |
| AC-1.5 | 仅改 `agnes_proxy.py`+`hub.html`；禁改区零改动；无生成链路改动 | ✅ PASS | test.md §3.5（TC-5） | commit `d1a4b99` |
| AC-1.6 | 8787 单监听(24436)，8788(32924)/8777(29296) 存活 | ✅ PASS | test.md §3.6（TC-6） | 现网合规终态（仅只读核验，未重启） |
| AC-1.7 | 每条 AC 附可重跑命令 + 原始 stdout | ✅ PASS | test.md 全文 | 无输出=未测=不通过 不成立 |

---

## 阿编把关结论

- **放行决定：✅ 放行（完成）**。AC-1.1~1.7 全部 PASS（QA 独立实跑 + 主理人亲自读盘核产双重验证），零 BUG、无阻断项、无越界、无回归。
- **亲自复验证据（主理人 读盘核产 §4.3④，与 QA 互补不替代）**：
  1. 主理人亲自 curl 8787 全 8 入口 → **全部 200**（`/` `/soundsfree` `/board/docs` `/console` `/logs` `/training` `/api/spec` `/board/api/projects/19/milestones`）。
  2. 内容真实：`/soundsfree` 标题 `SoundsFree - 免费程序化音效生成器`；`/board/docs` 标题 `看板 API 说明页 · /docs`（非 404、非兜底）。
  3. 端口卫生：8787 仅 PID 24436（唯一监听）、8788=32924、8777=29296 均在、未被误杀；agnes_proxy 仅 1 个原生进程（遗留旧进程已清）。
  4. git 核验：源变更仅 `agnes_proxy.py`(+5) + `hub.html`(+20)，commit `d1a4b99`；`route_registry.json` / `shared_board/**` / `short_drama_workflow/**` 零改动。
- **闭环是否跑通（本次核心测试目标）**：✅ 跑通。完整走完 派活 GATE0 → 工程师实现 → 主理人 §4.3 派活后验证(读盘核产) → QA 独立验收(全 PASS) → 主理人把关放行 五步；研发/测试分离铁律已守，QA 闸未漏。
- **模型表现（老板关切）**：software-engineer / software-qa-engineer 双角色在团队模式下工作正常——工程师按 PRD/守则/模板落地、自检、commit；QA 独立实跑 curl/netstat/diff、按 `[BUG][S|P]` 纪律零提单（无缺陷）、严守"只验证不改码"。未观察到角色权限越界或上下文丢失。
- **本次发现的问题（已闭环 / 遗留）**：
  1. `[已闭环·非本任务] 8787 遗留双原生进程（PID 31328/29144）占端口致自测假 404` → 工程师 `taskkill` 精确清理（仅 8787，未碰 8788/8777），现为唯一监听终态。
  2. `[观察·非阻塞] PRD §3 警示的「/board/docs 文本被 /api/→/board/api/ 重写篡改」风险经实测未出现`：门户版与直连版 docs 逐字节一致(diff=0)，老板阅读无碍。属实记录，不阻塞放行。
  3. `[遗留·低优·非本任务] shared_board/server.py 有 4 个进程（仅 32924 真监听 8788，另 3 为端口被占后启动失败未退出的僵尸）` → 资源泄漏隐患，登记待后续清理，不阻塞 T-12。

---

## 下一步建议

- 现网已达合规终态，老板可直接经 `http://localhost:8787` 门户点「音效台」「看板 API 说明」两张新卡片进入。
- 建议后续排期清理 8788 僵尸进程（非 T-12 范畴）。
