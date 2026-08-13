# T-20260813-02 测试记录（test.md）

> 分层：L0/L1 之间（零 AGNES 额度，全 127.0.0.1 内网探测）。
> 执行：开发自测 + 主理人主会话复验 + AC-1.5 真服务铁证。

## 一、注册表与代码核验（主理人读盘）

| 项 | 结果 |
|---|---|
| route_registry.json 存在，33 条路由（工作台 31 + 看板 1 + demo 1） | ✅ |
| schema：`{prefix, target, kind, flags, demo, note}` | ✅ |
| `/studio→8777`(kind=studio)、`/board→8788`(kind=board, flags.board_token_inject+rewrite_html_api) | ✅ |
| `/demo→127.0.0.1:8779`(demo=true, AC-1.5 激活) | ✅ |
| git 双 commit：before `890f8ff` + 完成 `a9f47f4` | ✅ |
| diff 范围：仅 5 个入口层文件，`agnes_proxy.py` 881+/20-（删的 20 行=4 处硬编码分发块） | ✅ |
| 工作树干净 | ✅ |

## 二、AC-1.1 注册表加载即生效

- 干净重启 8787（杀旧 PID 21120 → schtasks rev2 触发 → 新 PID 30996）
- `GET /studio → 200`、`GET /board → 200`（注册表驱动转发生效）

## 三、AC-1.2 前缀唯一校验

- 开发自测（纯函数）：手工构造冲突（`/api` vs `/api/spec`）→ RouteRegistryError 报错；合法集合通过（`/api/log` vs `/api/logs` 不误报）
- 代码审查：`_find_prefix_conflict` 路径段感知（`a==b` 或互为 `/` 前缀）✅

## 四、AC-1.3 do_PUT/do_DELETE 对注册表内所有前缀生效

- 回归脚本：33 路由 × (GET+PUT+DELETE) 全 PASS，**0 FAIL，exit 0**
- 手动实测：`DELETE /studio → 501`（**后端 8777 自身返回**，直连 8777 同响应=转发生效）；`DELETE /board → 404`（后端应答）
- 附：回归脚本初版有断言 bug（把后端透传 501 误判为未转发 501），已修 `54043c5`（区分 body 含 `unsupported method` = 门户兜底）

## 五、AC-1.4 路由清单 diff 回归脚本

```bash
python short_drama_workflow/scripts/route_diff_test.py --base http://127.0.0.1:8787
# 汇总: 33 路由, PASS=33, FAIL=0  → 退出码 0
```
- 零 AGNES 额度（只探测 127.0.0.1）✅
- 主理人复验与开发自测结果一致 ✅

## 六、AC-1.5 注册表加一行即通（真服务铁证）

- 起假服务 127.0.0.1:8779（任何请求回 200 `demo-registry-probe-OK`）
- 经 8787 转发实测：

| 请求 | 结果 |
|---|---|
| 直连 `8779/anything`（基线） | `200 demo-registry-probe-OK` |
| `8787/demo/anything` | **200**（转发到 8779） |
| `8787/demo?probe=1`（带 query） | **200** |
| `8787/demo/write`（PUT） | **200** |
| `8787/demo/del`（DELETE） | **200** |

- 结论：**注册表加一行 `/demo→8779` 即通，对外仍只有 8787** ✅（验证后已停假服务、清理临时脚本）

## 七、回归基线（收敛前后对照）

| 前缀 | 收敛前 | 收敛后 |
|---|---|---|
| `/` `/studio` `/board` `/console` `/api/projects` `/api/logs` `/hub` | 全 200 | 全 200（无回归） |
| `/demo` | 无此路由 | 200（新增即通） |
