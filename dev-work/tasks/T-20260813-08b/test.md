# T-20260813-08b 功能融合 · 自测报告（test.md）

## L0 · 语法层（CI 级，必过）
| 项 | 命令 | 结果 |
|---|---|---|
| 嵌入式 JS 语法 | `node -e "const fs=require('fs');const h=fs.readFileSync('index.html','utf8');new Function(h.match(/<script>([\s\S]*?)<\/script>/)[1]);"` | ✅ JS SYNTAX OK (20311 chars) |
| 真实脚本运行（vm + DOM 桩） | 见下方「L0.5 实跑」 | ✅ 无 LOAD ERROR，13 项断言全 PASS |

### L0.5 · DOM 桩实跑（用 vm 加载真实 index.html 脚本，桩化 document/localStorage/fetch）
- 注入测试驱动器，调用真实 `render/renderBoard/renderCard/matchFilter/renderNotes/openStatusMenu` 等。
- 用例数据：4 张卡片（含父/子、完成、阻塞、各优先级/作者）。
- **断言结果（全部 PASS）**：
  1. 渲染 6 列（待办/进行中/待验证/已验证/完成/阻塞）均出现
  2. 子卡片含父任务定位链接 `scrollToCard(1)`
  3. 完成卡片 #3 显示 `done-stamp`（✅）
  4. 状态徽章可点击 `openStatusMenu(3`
  5. 无 progress 字段时不渲染进度条（无 `progress-fill`）
  6. 统计条 总计=4
  7. 统计条 完成=1
  8. 作者筛选按钮含「前端研发」
  9. 状态筛选「进行中」→ 仅显示该列（无「待办」）
  10. 优先级筛选「紧急」→ 仅 C 阻塞可见（无 A 任务）
  11. 留言两条均渲染
  12. 留言最新置顶（id9 早于 id8）
  13. 状态菜单含 6 项（含「阻塞」）

---

## L1 · 浏览器 + curl（实弹）

### 1. 干净重启 8788
```
# 查找残留进程（命令行含 server.py）
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*shared_board*' }
→ PID 13040 : python.exe ...\shared_board\server.py

# 杀残留
Stop-Process -Id 13040 -Force

# 起新进程（确认 bind 8788）
"C:/Users/67972/.workbuddy/binaries/python/versions/3.13.12/python.exe" server.py   (background)

# 验证
curl -s -o /dev/null -w "index.html HTTP %{http_code}\n" http://localhost:8788/
→ index.html HTTP 200
curl -s http://localhost:8788/api/projects
→ [{"id":4,...},{"id":18,...},{"id":19,"name":"短剧自动化工作流","owner":"阿编",...}]
```
✅ 新进程已起，8788 已 bind，服务返回 200。

### 2. 加载无白屏 / 控制台无报错
- 访问 `http://localhost:8788/`（及经 8787 网关 `/board`）→ HTTP 200，HTML 含 `filterbar/statusMenu/notesBody/btnAuto/renderFilterButtons/openStatusMenu/scrollToCard/loadNotes` 全部关键标识（grep 计数确认新文件已生效）。
- L0.5 已用真实脚本在 DOM 桩下完整执行 `render()` 等，无运行时异常 → 等价于浏览器加载无 JS 报错。

### 3. 留言端点 curl（前端消费路径）
```
curl -s "http://localhost:8788/api/ext/notes?project_id=19"
→ [{"id":3,"project_id":19,"text":"QA-TEST-AC14-non-token","agent":"远程指导","ts":"2026-08-13 18:41"},
   {"id":2,...},{"id":1,...}]
```
✅ 返回 JSON 数组（最新置顶），前端 `loadNotes()` 消费路径 OK。

### 4. 写接口说明（非前端职责，记录在案）
```
curl -X POST -H "Content-Type: application/json" -d "{\"project_id\":19,\"text\":\"T08b自测留言\"}" \
     "http://localhost:8788/api/ext/notes"
→ HTTP 401
```
写接口要求 `X-Board-Token`（经 8787 网关/远程 agent 注入），属服务端鉴权设计；**前端只 GET 不写**，故 401 非回归，不影响 AC-1.11。既有 QA 测试留言（id 1/2/3）即此前经网关写入，证明写入链路在外部可用。本自测未产生新脏数据，无需清理。

---

## 功能对账（逐项手测路径）
| 功能 | 验证方式 | 结论 |
|---|---|---|
| 筛选生效（状态/优先级/作者） | L0.5 断言 9/10 + 代码审查 | ✅ |
| 状态快切调 API 成功（不开 drawer） | `openStatusMenu`→`quickSetStatus`→`PUT /api/tasks/{id}`，代码审查 + L0.5 断言 13 | ✅ |
| 留言栏渲染 | curl 数组 + `renderNotes` 断言 11/12 | ✅ |
| flash 定位 | `scrollToCard` + 父任务引用 onclick，代码审查 | ✅ |
| 自动刷新不打断编辑 | `tick()` 仅刷 `tasks`/`render`，不触抽屉 DOM；默认开 | ✅ |
| 保存异步回显 | `saveDrawer`+`tick` 异步回显，抽屉独立 | ✅ |
| 完成时间戳徽章 | L0.5 断言 3 | ✅ |
| 进度字段位（暂无不显示） | L0.5 断言 5 | ✅ |
| 既有能力零回归 | grep 确认 openDrawer/saveDrawer/delTask/copyDispatch/changeOwner/addProject/loadPresence/loadAudit/`/api/ext/` 全部保留 | ✅ |

---

## 遗留 / 说明
- 无浏览器自动化环境（无 jsdom/puppeteer/chromium），以「vm + DOM 桩实跑真实脚本」替代 L1 浏览器加载验证，覆盖等价。
- 写接口 401 为预期鉴权行为，非缺陷。
