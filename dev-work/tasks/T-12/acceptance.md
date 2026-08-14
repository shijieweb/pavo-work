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

（以下由主理人填写，QA 不越权）

- **放行决定**：
- **亲自复验证据**：
- **闭环是否跑通**：
- **模型表现**（若涉及 AI 角色）：
- **本次发现的问题**（已闭环 / 遗留）：
  1.
  2.

---

## 下一步建议

（由主理人把关后填写）
