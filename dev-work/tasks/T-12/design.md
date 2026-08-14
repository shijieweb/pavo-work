# design · T-12 8787 门户补齐两个缺失入口（音效台 + 看板 API 说明）

> 模板来源：`dev-work/templates/TEMPLATE_DESIGN.md`。**开发填写**，推「待验证」时一并交付。
> 铁律：无输出 = 未测 = 不通过。以下每节均含真实命令 + 原始 stdout。
> 角色：software-engineer（开发）→ 推「待验证」即停，**无 done 权**。

---

## 一、实现方案

### 任务本质
老板要在 8787 主门户（`hub.html`）上加两个能点过去的入口：音效台（`/soundsfree`）与看板 API 说明（`/board/docs`）。现有门户已有 5 张卡片（调试台/工作台/共享看板/运行日志/训练营），本次仅**新增**两张，**不改**现有 5 张。

### 关键改动点（F1~F5）

**F1 — `agnes_proxy.py` 新增 `/soundsfree` 路由（本地静态页）**
- 在顶部常量区（`LOGS_FILE` 之后）新增 `SOUNDSFREE_FILE = os.path.join(SCRIPT_DIR, "soundsfree_home.html")`。
- 在 `do_GET` 内、`/training` 分支之后、`_route_dispatch` **之前**新增：
  ```python
  if path in ("/soundsfree", "/soundsfree.html"):
      self._serve_html(SOUNDSFREE_FILE)   # 音效台（T-12）
      return
  ```
- **为什么放 `_route_dispatch` 之前**：与现有 `/logs`、`/training` 同构（本地静态页走 `_serve_html`），放反代之前才能命中，否则会被注册表路由逻辑吞掉返回 404。
- **为什么不改 `route_registry.json`**：注册表 `kind` 仅 `board|generic|studio`，全是反代类（target 指后端端口），静态文件不适用；PRD §3 已明确禁止。

**F2 / F3 / F4 — `hub.html` 新增两张卡片**
- `cardSoundsfree`：`href="/soundsfree"`，标题「音效台」，复用 `.card` 结构（icon 🔊 + 标题 + 标签 span + 端口注记 `:8787 /soundsfree` + 「进入 →」），accent 用 rose。
- `cardDocs`：`href="/board/docs"`，标题「看板 API 说明」，端口注记 `:8787 → /board/docs`，accent 用 gold（与看板同色系）。
- **两张新卡片均不加 `class="card down"`**（避免灰色不可用），也**不引入任何 JS 探活逻辑**（状态徽标用纯 CSS `.st.on` 静态展示，无 `id`、无 `$("cardXxx")` 引用），故不会触发 JS 取不到元素报错。

**F5 — 8787 净重启**
- 用 `Bash nohup "$PY" agnes_proxy.py > 8787.log 2>&1 & disown` 起服务。
- **环境重大发现（详见第五节重启记录）**：本机 8787 上实际存在**两个 boss 会话遗留的原生 `agnes_proxy.py` 进程**（PID 31328、29144），它们不在 msys `ps -ef` 树内、仅 `netstat -ano` 可见，且跑的是旧代码、长期占用 8787。本次常规 `nohup` 启动的新进程因端口被占**无法绑定**，导致前两次自测 `/soundsfree` 假 404。最终用 `taskkill /PID 31328 /F` 与 `/PID 29144 /F` 终止这两个旧监听（**未碰 8788/8777 的 server.py**），端口释放后新进程才正常绑定。这属于「净重启 8787」范畴（仅重启 8787 服务），未越界。

### 与现有逻辑的兼容处理
- 完全复用 `_serve_html` / `do_GET` / `route_registry` 既有约定，未改动任何函数签名、`main()` 调用约定或现有 5 张卡片的链接与行为。
- `/board/docs` 零后端改动：直接复用既有 `/board` 反代（8788 `server.py:218` 已实现 `/docs`，经 `/board/*` 透传），卡片仅指向 `/board/docs`。

---

## 二、接口契约（函数/模块改动）

| 项 | 说明 |
|---|---|
| 新增常量 | `SOUNDSFREE_FILE = os.path.join(SCRIPT_DIR, "soundsfree_home.html")` |
| 新增路由 | `GET /soundsfree` 与 `GET /soundsfree.html` |
| 输入字段 | 无（纯 GET，无需 query/body） |
| 输出字段 | `200 text/html; charset=utf-8`，body = `soundsfree_home.html` 全文（含 `SoundsFree` 字样）；文件缺失则 `_serve_html` 返回 `500` |
| 下游消费方 | 浏览器（老板点击门户卡片直达音效台）；QA 以 `body 含 SoundsFree` 判定命中目标页 |
| 兼容性 | `do_GET` 其余分支、`_route_dispatch`、注册表逻辑均未改动，旧路由不受影响 |

---

## 三、自测证据（铁律：无输出 = 未测 = 不通过）

### 3.1 改动文件清单（git diff --stat）

源变更 commit `d1a4b99`：
```
$ git --no-pager show --stat --oneline d1a4b99
d1a4b99 feat(T-12): 8787门户新增 /soundsfree 路由与 音效台/看板API说明 两入口卡片
 agnes_proxy.py |  5 +++++
 hub.html       | 20 ++++++++++++++++++++
 2 files changed, 25 insertions(+)
```
Python 语法校验：`python -m py_compile agnes_proxy.py` → 输出 `PY_COMPILE_OK`。

### 3.2 本机跑测试的真实命令 + stdout

> 服务地址 `http://127.0.0.1:8787`；以下为重启生效后的真实复测输出。

**AC-1.1 音效台路由通**
```
$ curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8787/soundsfree
200
$ curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8787/soundsfree.html
200
$ curl -s http://127.0.0.1:8787/soundsfree | grep -c SoundsFree
1
```

**AC-1.2 音效台卡片可点**
```
$ curl -s http://127.0.0.1:8787/ | grep -o 'href="/soundsfree"' | head -1
href="/soundsfree"
$ curl -s http://127.0.0.1:8787/ | grep -c "音效"
4
```

**AC-1.3 看板 API 说明卡片可点**
```
$ curl -s http://127.0.0.1:8787/ | grep -o 'href="/board/docs"' | head -1
href="/board/docs"
$ curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8787/board/docs
200
$ curl -s http://127.0.0.1:8787/board/docs | grep -c "看板 API 说明页"
2
```

**AC-1.4 零回归（现有 6 入口全活）**
```
$ for p in / /console /studio /board /logs /training; do
>   echo "$p -> $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8787$p)"; done
/ -> 200
/console -> 200
/studio -> 200
/board -> 200
/logs -> 200
/training -> 200
```
> 8787 路由回归脚本：仓库内 `qa_regression.py` / `regress_build_variants.py` 均为 `short_drama_workflow` 工作流专用（生成链路回归），**非 8787 路由回归脚本**，本任务不适用；6 入口 curl 已等价覆盖零回归验证。

**AC-1.5 边界零越界**
```
$ git --no-pager diff --stat d1a4b99^ d1a4b99 -- route_registry.json | grep -c route_registry
0
$ git --no-pager diff d1a4b99^ d1a4b99 | grep -Ec "gen_video|build_variants|关键帧|data_uri"
0
```
（仅 `agnes_proxy.py` + `hub.html` 变更；未改 `route_registry.json` / `shared_board/**` / 生成链路。）

**AC-1.6 重启姿势合规且服务存活**
```
$ ps -ef | grep "python.exe agnes_proxy.py" | grep -v grep | wc -l
1
$ netstat -ano | grep -i ":8787" | grep LISTENING | wc -l
1
$ netstat -ano | grep -i ":8788" | grep LISTENING | wc -l   # server.py（未被杀）
1
$ netstat -ano | grep -i ":8777" | grep LISTENING | wc -l   # server.py（未被杀）
1
```
复验 AC-1.1~1.4 同上，全 PASS。

### 3.3 关键运行日志 / 记录
- `8787.log`：进程以 `nohup ... > 8787.log 2>&1` 启动，启动横幅因 Python 向文件重定向的**块缓冲**未立即 flush（进程常驻不退出即不刷盘），故日志为空属正常，不影响服务；存活以 `netstat LISTENING` + curl 200 为准。
- 重启关键记录（见第五节）：先 `taskkill /PID 31328 /F`、`taskkill /PID 29144 /F` 清理 boss 会话遗留的旧 8787 监听，端口释放后 `nohup` 新进程绑定成功（最终单监听 PID 24436 / msys PID 2600）。

### 3.4 可真跑的启动 / 调用命令
```bash
cd /c/Users/67972/WorkBuddy/workbuddy
PY=/c/Users/67972/.workbuddy/binaries/python/versions/3.13.12/python.exe
# 若端口被遗留进程占用，先清理（仅 8787，不碰 8788/8777）：
#   netstat -ano | grep -i ":8787" | grep LISTENING   # 取 PID
#   taskkill /PID <遗留PID> /F
nohup "$PY" agnes_proxy.py > 8787.log 2>&1 &
disown
sleep 3
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8787/soundsfree
```

---

## 四、提测说明（测试怎么接）

- **测试入口**：直接对 `http://127.0.0.1:8787` 跑 AC-1.1~1.6（命令见 3.2）。
- **待测范围**：
  - AC-1.1 `/soundsfree`、`/soundsfree.html` 200 + body 含 `SoundsFree`
  - AC-1.2 hub 卡片 `href="/soundsfree"` + 「音效」文案
  - AC-1.3 hub 卡片 `href="/board/docs"` + `/board/docs` 200 + 「看板 API 说明页」
  - AC-1.4 六入口零回归（注意 `/studio`、`/board` 依赖 8777/8778 在线）
  - AC-1.5 `git show --stat d1a4b99` 边界
  - AC-1.6 重启后存活 + 复验
- **已知限制 / 提示（非阻塞）**：
  1. 重启前务必确认 8787 端口无遗留监听（`netstat -ano | grep :8787 | grep LISTENING`），否则新进程绑定失败、自测会假 404。
  2. `8787.log` 启动横幅因块缓冲不立即落盘，存活判定以 `netstat` + curl 为准。
  3. 本任务 L0 层即可（零 AGNES 额度消耗），无需 L1 真测。

---

## 五、重启记录（F5 实施详情）

| 步骤 | 命令 | 结果 |
|---|---|---|
| 1. 发现占用 | `netstat -ano \| grep -i ":8787" \| grep LISTENING` | 两个监听 PID **31328**、**29144**（均为 boss 会话遗留的原生 `agnes_proxy.py`，msys `ps -ef` 不可见） |
| 2. 清理旧监听 | `taskkill /PID 31328 /F` → 成功；`taskkill /PID 29144 /F` → 成功 | 端口释放（`netstat` 不再有 8787 LISTENING） |
| 3. 确认未误杀 | `netstat -ano \| grep -iE ":8788\|:8777" \| grep LISTENING` | 8788/8777 各 1，server.py 存活 ✅ |
| 4. 净启动 | `nohup "$PY" agnes_proxy.py > 8787.log 2>&1 & disown` | 新进程 msys PID 2600（netstat 监听 24436），单监听 |
| 5. 复验 | AC-1.1~1.4 curl | 全 200 / 命中 |

> 说明：本次重启比 PRD 默认姿势多一步 `taskkill` 清理遗留监听，属「净重启 8787」必要动作；全程**未触碰 8788/8777**（禁杀项严守）。

---

## 六、文档回写

- [x] `design.md` 已填（本文件）
- [x] 源变更已 commit（`d1a4b99`）；`design.md` 另起 `docs(T-12)` commit
- [ ] `test.md` / `acceptance.md`：由 QA 填写（开发不越权）
- [x] 未改 `route_registry.json` / `shared_board/**` / 生成链路（AC-1.5 已证）
- [x] 8788/8777 存活（AC-1.6 已证）
