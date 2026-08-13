# T-20260813-03 · acceptance · 令牌闸验收

| AC | 描述 | 状态 | 证据 | 备注 |
|---|---|---|---|---|
| AC-1 | 无 token `GET /studio` → 401 | ✅ | [test.md#二] | 主理人 localhost+公网双验 |
| AC-2 | 带 token `GET /studio` → 200 | ✅ | [test.md#二] | 老板可达 |
| AC-3 | 无 token `PUT /api/spec` → 401 | ✅ | [test.md#二] | 阻断改文件 |
| AC-4 | 内部健康检查不受影响 | ✅ | [test.md#二] | 自愈拉起正常 |
| AC-5 | 重启后老板带 token 全功能 | ✅ | [test.md#二] | 主理人实跑通过 |
| AC-6 | 未设 token 维持开放 | ✅ | [design.md#2] | 逻辑可证（PORTAL_TOKEN 空→恒 True） |

## 主理人把关结论
- 放行决定：✅ 放行（完成）
- 亲自复验：主会话 curl 401/200 实测（localhost + 公网隧道双路径全过）
- 闭环：开发(主理人自写)→主理人实跑(抓 1 真 bug 已修)→把关放行
- 交付物：8387 令牌闸上线；token 存 `~/.workbuddy/.env` 不进代码；老板书签 `agnes.owen1.de5.net/studio?token=<PORTAL_TOKEN>`
