# design · T-20260813-02 8787 统一网关：路由收敛为 route_registry.json 单一事实源

> 需求基线闸：老板已签 ☑（2026-08-13 02:08 拍板：**只做入口层，其他不动**）。
> 铁律：只动入口层；绝不运行/重启 agnes_proxy.py、绝不 kill 进程（8787 线上 PID 26296，schtasks 托管）；不新增对外端口；不引入新依赖；不重构反代核心转发逻辑。

---

## 一、实现方案（核心设计一句话）

**把 8787 的路由判定从「代码里 STUDIO_PREFIXES 元组 + _is_studio/_is_board 硬编码」改为「route_registry.json 单一事实源 + 注册表驱动匹配」，加服务 = 注册表加一行；无注册表/解析失败/空 routes 自动回退硬编码，兼容不崩。**

### 1. 新增 `route_registry.json`（schema，保持简单）

```jsonc
{
  "version": 1,
  "_doc": "说明字符串，加载器忽略",
  "routes": [
    {
      "prefix": "/studio",                 // 挂载前缀（必填，以 / 开头）
      "target": "http://127.0.0.1:8777",   // 目标 base url（必填，http(s)://）
      "kind": "studio",                    // 可选：studio/board/generic，选转发实现（默认 generic）
      "flags": {},                         // 可选：{ board_token_inject, rewrite_html_api }
      "demo": false,                       // 可选：true = AC-1.5 演示条目（柔性断言）
      "note": "人读注释，加载器忽略"
    }
  ],
  "examples": [ /* 仅为「新增服务」写法示例，加载器不读 */ ]
}
```

- 真实路由 33 条 = 工作台 31 条（`/studio` + 全部工作台 `/api/*`、`/assets/`、`/projects/`、`/vendor/`，与旧 `STUDIO_PREFIXES` 一一对应，全部 `kind=studio` → 走原 `_proxy_studio`，含自愈拉起/缓存透传/900s 超时）+ 看板 1 条（`/board → 8788`，`kind=board`，`flags.board_token_inject=true` + `rewrite_html_api=true`，完整保留 token 注入与 `/api/`→`/board/api/` 改写语义）+ 演示 1 条（`/demo → 127.0.0.1:8779`，`kind=generic`，`demo=true`，供 AC-1.5）。
- `examples` 字段仅文档用途（加载器只读 `routes`），演示「加一行即通」的写法。

### 2. `agnes_proxy.py` 改造点（只换路由来源，其余逻辑不动）

| 位置 | 改动 |
|---|---|
| 模块级（`_is_board` 之后） | 新增 `RouteRegistryError`、`_find_prefix_conflict(prefixes)`、`_load_route_registry(path)`、`_ROUTE_REGISTRY`（加载 + 冲突即 `raise SystemExit`）、`_route_matches`、`_route_for(path)` |
| `H._route_dispatch(path, method, data)` | 新方法：注册表驱动分发。有注册表→`_route_for` 命中→按 `kind` 走 `_proxy_studio` / `_proxy_board` / `_proxy_route`；无注册表→回退 `_is_board`/`_is_studio` 原逻辑 |
| `H._proxy_route(method, data, route)` | 新方法：generic 路由通用转发（去挂载前缀拼 target，可选 token 注入/HTML 改写；目标不可达返回 503） |
| `do_GET/do_POST/do_PUT/do_DELETE` | 原 `_is_board`/`_is_studio` 两段改为 `if self._route_dispatch(...): return`；**PUT/DELETE 对注册表内所有前缀（含 board、demo）生效**，未命中才 501 |
| `__main__` 启动横幅 | 增加一行打印注册表条数（或「缺失→回退硬编码」） |
| 未动 | `_proxy_studio`/`_proxy_board` 核心转发、`_hub_status`、一键拉起、日志、健康检查、`_load_env`/`_load_state`、`_merge` 等全部原样 |

### 3. 前缀唯一校验（AC-1.2）

- 规则：任意两条 prefix 满足 `a == b` 或 `a.startswith(b + "/")` 或 `b.startswith(a + "/")` → 抛 `RouteRegistryError` → 模块级 `raise SystemExit`，**启动即报错**，防两服务抢同一路径（如 `/api` 与 `/api/spec`）。
- 设计决策（与需求字面微调，已在注释与自测中说明）：采用**路径段感知**而非裸字符串 `startswith`。原因：现有工作台白名单本就共存 `/api/log` 与 `/api/logs`、`/api/projects` 与 `/api/project/` 等**独立端点**（且同挂 8777），裸字符串前缀会误报冲突导致合法注册表无法启动；路径段感知既拦截 AC 示例 `/api` vs `/api/spec`，又不误伤真实路由（自测 ② 已覆盖）。

### 4. 回退策略（AC 兼容性）

- 无注册表 / json 解析失败 / `routes` 非空列表缺失 / 单条缺 prefix 或 target / 空 routes → `_load_route_registry` 返回 `None` → `_route_dispatch` 走 `_is_board`/`_is_studio` 硬编码回退，行为与旧版完全一致（自测 ③ 已覆盖：`_ROUTE_REGISTRY=None` 时 `/api/projects` 仍判 studio、`/board/x` 仍判 board）。
- **前缀冲突是唯一「硬失败」**：宁可启动报错，也不让两服务静默抢路径。

### 5. 新增回归脚本 `short_drama_workflow/scripts/route_diff_test.py`

- `python route_diff_test.py --base http://127.0.0.1:8787`（默认即 8787）。
- 复用 `agnes_proxy._load_route_registry`（同一 schema 单一事实源，永不漂移）。
- 每前缀三条探测：`GET <prefix>`（期望 200/404 = 转发目标正确，board 命中 200 时额外校验 body 含 `/board/api/` 改写生效）、`PUT/DELETE <prefix>/__route_diff_probe__`（期望非 501 = AC-1.3 注册表内所有前缀 PUT/DELETE 生效）。
- **柔性断言（AC-1.5 demo 条目）**：`demo=true` 路由命中 200/404/502/503 均 PASS（假服务 8779 未跑，502/503 恰证明注册表行已被加载并转发）；唯一 FAIL = 门户返回 `404 unknown path` 或 `501`（注册表行未加载）。
- 只探测不修改；零 AGNES 额度（只打 127.0.0.1:*）。
- 退出码：0=全过 / 1=有 FAIL。

### 6. 自测脚本 `short_drama_workflow/scripts/route_registry_selftest.py`

- importlib 加载 `agnes_proxy.py`（模块级初始化只读注册表/env/state，**不 bind 端口**——bind 在 `if __name__ == "__main__"` 内），纯函数自测 ①~④，退出码 0/1。

---

## 二、接口契约

| 函数 | 签名 | 说明 |
|---|---|---|
| `_find_prefix_conflict` | `(prefixes: list[str]) -> tuple[str,str] | None` | 纯函数：返回冲突对或 None |
| `_load_route_registry` | `(path: str|None = None) -> list[dict] | None` | 缺失/解析失败/空→None；冲突→抛 `RouteRegistryError` |
| `_route_for` | `(path: str) -> dict | None` | 注册表驱动：命中第一条路由；无注册表→None |
| `_route_matches` | `(path: str, route: dict) -> bool` | board 需边界匹配；其余 == 或 startswith |
| `H._route_dispatch` | `(path, method, data) -> bool` | True=已分发转发；False=未命中（回退/继续后续处理） |
| `H._proxy_route` | `(method, data, route)` | generic 路由通用转发 |

- 复用的既有契约不变：`_proxy_studio(method, data)`（8777 整段、自愈、缓存透传）、`_proxy_board(method, data)`（8788、token 注入、HTML 改写）、`_board_token()`、`_launch_studio/_launch_board`、`_hub_status` 等。

---

## 三、自测证据（铁律：无输出 = 未测 = 不通过）

### 3.1 改动文件清单（`git diff --stat before..HEAD`，见下节 3.3 真实输出）

- 新增：`route_registry.json`（33 条路由 + examples）
- 修改：`agnes_proxy.py`（+约 130 行注册表机制与分发，核心转发零改动）
- 新增：`short_drama_workflow/scripts/route_diff_test.py`（回归脚本）
- 新增：`short_drama_workflow/scripts/route_registry_selftest.py`（纯函数自测）
- 新增：`dev-work/tasks/T-20260813-02/design.md`（本文件）

### 3.2 提交链

- `890f8ff4a3c7b984430bb10ff8490eba749e3612` before: T-20260813-02 8787 路由收敛改造前快照（仅入口层）
- `<完成提交 hash>` 见交付回报

### 3.3 py_compile（真实输出）

```
$ python.exe -m py_compile agnes_proxy.py short_drama_workflow/scripts/route_diff_test.py short_drama_workflow/scripts/route_registry_selftest.py
PY_COMPILE_OK        # exit 0
```

### 3.4 纯函数自测（真实输出，完整见交付回报）

```
== route_registry_selftest（不启动 8787，纯函数自测）==
  模块加载完成: ...\agnes_proxy.py (bind 在 __main__ 内, 未 bind 端口)
    → 注册表 33 条, 含 /studio→8777(kind=studio) 与 /board→8788(flags 保留)
  [PASS] ① 注册表加载成功且含两条真实路由
  [PASS] ② 前缀唯一校验: 冲突→报错
  [PASS] ② 前缀唯一校验: 合法集合通过
  [PASS] ③ 无注册表→回退硬编码
  [PASS] ④ 注册表驱动 _route_for 匹配
自测结果: 5 PASS, 0 FAIL    # exit 0
```

> 说明：本任务交付前按要求只跑 py_compile + 纯函数自测；`route_diff_test.py` 实跑属 QA/重启后步骤（PRD 证据要求「独立实跑回归 + 老板实机验证」），因 8787 线上仍是旧代码（PID 26296），此时跑 demo 条目必然 FAIL，属预期，待主理人重启后由测试实跑。

### 3.5 铁律声明

- **未运行/重启 agnes_proxy.py；未 kill/启动任何进程**；8787 保持线上原状（PID 26296）。
- 只动入口层 4 个文件；未碰生成链/云 API/多角色框架/shared_board/server.py/html_prototype/server.py。
- 未新增对外端口（新服务 demo target 为 127.0.0.1:8779）；未引入新依赖（仅标准库）。

---

## 四、AC 对应（逐条标注）

| AC | 如何满足 | 证据 |
|---|---|---|
| AC-1.1 注册表含 `/studio→8777`、`/board→8788(board-token + rewrite)` 两条真实路由，加载即生效 | `route_registry.json` routes 含 33 条，其中 `/studio`(kind=studio, target=8777)、`/board`(kind=board, target=8788, flags.board_token_inject + rewrite_html_api)；模块级 `_ROUTE_REGISTRY = _load_route_registry()` 启动即加载 | 自测 ①（含 flags 断言）；`route_diff_test.py` 实跑待 QA |
| AC-1.2 前缀唯一校验：重复前缀启动即报错 | `_find_prefix_conflict`（路径段感知：`a==b` 或互为 `/` 前缀）→ 冲突抛 `RouteRegistryError` → 模块级 `raise SystemExit`；手工构造 `/api`+`/api/spec` 冲突注册表已自测抛错 | 自测 ② |
| AC-1.3 `do_PUT`/`do_DELETE` 对注册表内所有前缀生效（不再只 `/api/*`） | do_PUT/do_DELETE 改为 `_route_dispatch` 注册表驱动；注册表内任何前缀（studio/board/demo/generic）PUT/DELETE 均转发到对应 target，未命中才 501 | `route_diff_test.py` 对每前缀做 PUT/DELETE 断言（非 501）；逻辑上 board/demo 均命中 |
| AC-1.4 路由清单 diff 回归脚本：每前缀 curl 断言 200/404/转发目标（零 AGNES 额度） | `route_diff_test.py`：GET 断言 200/404 + 转发目标（board 校验 rewrite 生效），只打 127.0.0.1:*，零外部 API；退出码 0/1 | 脚本 CLI `--help` 已自测通过；实跑待 QA |
| AC-1.5 示例：新增假想服务条目（127.0.0.1:8779），验证「注册表加一行即通」，对外仍仅 8787 | routes 内置 `/demo → http://127.0.0.1:8779`（`demo=true`）真实激活；加载即被 `_route_for` 命中并转发（目标不可达返回 503 = 注册表生效的柔性证据）；对外仍只有 8787 一个端口 | 自测 ④ `/demo` 命中；`route_diff_test.py` 对 demo 柔性断言（502/503 也算预期） |

---

## 五、文档回写

- [x] `design.md` 已填（本文件）
- [ ] 任务卡 AC 进度回写 `current_state.md`（待主理人/测试确认后）
- [ ] 主理人主会话：干净重启 8787 后跑 `route_diff_test.py` + 老板实机 `/studio` `/board` 验证
