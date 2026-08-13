# T-20260813-03 · design · 令牌闸实现

## 1. 改动文件
- `agnes_proxy.py`（唯一改动，+~25 行，不触生产生成逻辑）。

## 2. 实现要点
1. 顶部 `import urllib.parse`；读 `PORTAL_TOKEN = os.environ.get("PORTAL_TOKEN","").strip()`（经 `_load_env` 从 `~/.workbuddy/.env` 注入）。
2. 新增受保护路由判定 `_is_protected(path)`：
   - `_is_studio(path)`（/studio + /api/* 工作台面）
   - `path.startswith(("/v1","/agnesapi","/console","/merge"))`（AGNES 转发 + 调试台 + 文件拼接，均带服务端 KEY/写本地）
3. 新增 `_authorized()`：未设 `PORTAL_TOKEN` → 永远 True（本地向后兼容）；设了则校验 `?token=` 或 `X-Portal-Token` 头 == `PORTAL_TOKEN`，否则 False。
4. 在 `do_GET/do_POST/do_PUT/do_DELETE` 中，凡 `_is_protected(path)` 且 `not self._authorized()` → `self._send(401, {"error":"未授权：带 ?token= 或 X-Portal-Token"})` 并 return。
5. 公共导航（hub/ /logs /training /files）**不闸**，保持本地工具可用。

## 3. 内部调用不受影响证明
- 代理自愈拉起 / 健康检查走 `urllib.request.urlopen(STUDIO_BASE+...)` 直连 `127.0.0.1:8777`，**不经过本代理的 do_* 处理器**，故不受令牌闸影响。

## 4. 验证证据（主理人主会话实跑）
- 重启前：`GET /studio → 200`、`GET /api/projects → 200`（已实证，见探针）。
- 重启后：无 token `GET /studio → 401`；带 token `→ 200`；无 token `PUT /api/spec → 401`（用 `curl -X PUT` 实测，不真写业务项目，用临时 project 或仅查 401 状态）。

## 5. 回滚
- 删 `~/.workbuddy/.env` 的 `PORTAL_TOKEN` 行 → 重启 8787 → 恢复全开放（本地）。
