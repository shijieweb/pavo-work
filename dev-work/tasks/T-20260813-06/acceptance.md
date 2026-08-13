# T-20260813-06 验收（acceptance）· P0-2 图视冲突预检

## AC 勾表
| AC | 描述 | 结果 | 证据 |
|---|---|---|---|
| AC-1.1 | 预检函数：单镜 shot+首尾帧 → match/warn/fail + conflicts | ✅ | [test.md §二] 真视觉实测 match（free key） |
| AC-1.2 | 空镜免检：no people → n/a | ✅ | [test.md §二] TC-1.2.1 |
| AC-1.3 | 解耦：失败=提示不崩溃；零额度 dry-run | ✅ | [test.md §二] TC-1.3.1~1.3.4 |
| AC-1.4 | 接入：方案 A `/api/precheck` 独立端点（主理人拍板） | ✅ | [test.md §二] POST 200/404 实测 |
| AC-1.5 | 真实项目 dry-run 证据报告 | ✅ | [precheck_dryrun_report.json + qa_acceptance_evidence.json] |

## 缺陷闭环
| BUG | 级别 | 发现者 | 修复 | 复验 |
|---|---|---|---|---|
| BUG-1 真视觉路径无 test 守卫（可能烧 VIP） | P2 | QA 独立验收（fresh eyes） | a04c8f1（ensure_test_mode 硬守卫 + 端点默认 dry_run=true + 文档纠正） | Round 2 ✅ 守卫拦截 `blocked` exit 3；有 key 真视觉 match 零 VIP |
| OBS-1 裸路径缺失未识别 | P3 | QA 独立验收 | a04c8f1（_frame_src 统一判缺失） | Round 2 ✅ warn |

## 主理人把关结论
- **放行决定**：✅ 放行（完成）
- **亲自复验**：主会话核产（git 双 commit + diff 最小集 + py_compile）+ 干净重启 8787/8777 + 线上验证（端点 200、默认零额度、守卫拦截 blocked）+ 注册表回归 34 PASS
- **闭环**：PRD → 开发文档 → 测试文档 → 主理人双审 → 开发实现 → 主理人核产+线上验证 → QA 独立验收（抓 BUG-1）→ 修复 → Round 2 回归 → 放行
- **流程验证**：老板 18:09 定的新流程（开发先写文档、测试先写文档、主理人审过再实现）首次完整跑通，防线真实有效
- **遗留**：route_diff_test.py 在 GBK 控制台 print 报 UnicodeEncodeError（P3 脚本兼容，需 PYTHONIOENCODING=utf-8，记 backlog 非阻塞）
