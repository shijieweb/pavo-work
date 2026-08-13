# T-20260813-03 · acceptance · 令牌闸验收

| AC | 描述 | 状态 | 证据 | 备注 |
|---|---|---|---|---|
| AC-1 | 无 token `GET /studio` → 401 | ⬜ | [test.md] | 主理人实跑 |
| AC-2 | 带 token `GET /studio` → 200 | ⬜ | [test.md] | 老板可达 |
| AC-3 | 无 token `PUT /api/spec` → 401 | ⬜ | [test.md] | 阻断改文件 |
| AC-4 | 内部健康检查不受影响 | ⬜ | [test.md] | 自愈拉起正常 |
| AC-5 | 重启后老板带 token 全功能 | ⬜ | [boss 验证] | 待老板确认 |
| AC-6 | 未设 token 维持开放 | ⬜ | [design.md#2] | 向后兼容 |

## 主理人把关结论
- 放行决定：⬜ 放行 / ⬜ 退回
- 亲自复验：主会话 curl 401/200 实测
- 闭环：开发(主理人自写)→主理人实跑→把关
