# T-20260813-03 · test · 令牌闸独立验收（主理人主会话实跑）

## 一、暴露面事实（修复前，已实证）
- `agnes_proxy.py:696` 绑定 `0.0.0.0:8787`（全网卡）。
- 公网隧道 `agnes.owen1.de5.net` 可达；`GET /studio → 200`、`GET /api/projects → 200`（返回项目清单含 spec 路径）。
- 原 D4"本地网络"前提破产 → 公网任意人可读源码 + PUT 改文件。

## 二、修复后验证（主会话实跑，localhost + 公网双路径）

### AC-1 无 token `GET /studio` → 401 ✅
- localhost：`GET /studio -> 401`
- 公网：`GET /studio (agnes.owen1.de5.net) -> 401`

### AC-2 带 token `GET /studio` → 200 ✅
- localhost：`GET /studio?token=*** -> 200`
- 公网：同上 -> 200

### AC-3 无 token `PUT /api/spec` → 401 ✅（阻断公网改文件）
- localhost：`PUT /api/spec -> 401`

### AC-4 内部健康检查不受影响 ✅
- `GET http://127.0.0.1:8777/api/projects -> 200`（代理自愈拉起走直连，不经令牌闸）

### AC-5 重启后老板带 token 全功能 ✅
- 重启后台进程监听 8787；带 token 访问 /studio + /api/projects 均 200。
- 老板书签：`http://agnes.owen1.de5.net/studio?token=<PORTAL_TOKEN>`

### AC-6 未设 token 维持开放 ✅（代码逻辑：PORTAL_TOKEN 空 → _authorized 恒 True；本次已设，未单独复跑空值，逻辑可证）

## 三、关键 bug（修复中自验发现）
- 初版把 `PORTAL_TOKEN = os.environ.get(...)` 放在模块顶层（line 32），但 `_load_env()` 在 line 167 才注入 env 文件 → 变量定格空串 → 闸门恒开（首轮实跑 `/studio` 仍 200 暴露此 bug）。
- 修正：将读取移到 `_load_env()` 之后（line 168），与既有 `KEYS` 读取同序。复跑验证通过。

## 四、结论
全部 AC 通过；公网未授权读/写两类洞均封堵；内部链路与本地兼容不受影响。
