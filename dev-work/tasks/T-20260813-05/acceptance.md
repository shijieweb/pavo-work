# T-20260813-05 验收（acceptance）· 看板外部指导 API（/ext/*）+ 状态对齐

## AC 勾表
| AC | 描述 | 结果 | 证据 |
|---|---|---|---|
| AC-1.1 | GET /ext/status → 200：projects + in_flight_tasks + recent_audit(8) + generated_at | ✅ | [test.md §二] 8787/8788 双路径实测 |
| AC-1.2 | /ext/projects、/tasks?pid、/audit、/presence → 200 + 错误路径 400/404 | ✅ | [test.md §二] 含 4 个错误分支实测 |
| AC-1.3 | POST /ext/notes → 写库 + 审计 agent=远程指导 + 前端可见 | ✅ | [test.md §二] id=2 读回精确匹配 + 审计流渲染 |
| AC-1.4 | 无 token 直达 /ext/*；不污染现有路由 | ✅ | [test.md §二] 6GET+1POST 无 token 全 200；现有路由零污染 |
| AC-1.5 | 状态对齐：已闭环任务补标 done | ✅ | [test.md §二] 10done+2todo，#26/#23 done，#24/#25 保持 todo 无误标 |

## 主理人把关结论
- **放行决定**：✅ 放行（完成）
- **亲自复验**：主会话核产（cc00088 最小集 + agnes_proxy 零改动确认 + py_compile）+ 干净重启 8787/8788（新 PID 19632/25660）+ 线上全链路实测（6 端点 200 + POST 写库 + 不污染 + AC-1.5 查库核对 + 回归 35 全过）
- **闭环**：PRD → 开发文档 → 测试文档 → 主理人双审 → 开发实现（cc00088）→ 主理人核产+线上验证 → QA 独立验收（全 PASS 无 BUG）→ 放行
- **WARN 记录**（均非阻塞）：
  1. 主理人 18:39 测试留言中文变 `?`（PowerShell 客户端发送缺陷，非服务端 bug；QA 用 curl.exe UTF-8 证明无损）
  2. 验收在 board.db 留测试留言 id=2/3（唯一标记，按协议不删）
  3. GET /ext 裸前缀 404 属正常（转发生效佐证）
- **遗留**：注册表热加载（分析师 #4 建议）登记为后置小项，T-05 验证通过后可评估
