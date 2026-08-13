# acceptance · T-20260813-01 l1_smoke 固化进回归套件

> 模板来源：`dev-work/templates/TEMPLATE_ACCEPTANCE.md`。**阿编填写**，对照 PRD 的 AC 逐条勾，推「完成」。
> 铁律：每条 AC 必须附证据链接（到 design.md / test.md / 截图 / git commit）。

---

## 验收对照表（逐条勾，每条附证据）

| AC 编号 | 验收点 | 结果 | 证据链接 | 备注 |
|---|---|---|---|---|
| AC-1.1 | 端到端 L1 免费KEY 真测跑通 + 成片 URL 200 | ✅ | [design.md#3.2 / test.md#三] | 主理人主会话 curl 200+video/mp4（2.2s） |
| AC-1.2 | 入口 assert 守卫：非 test 模式提前中止 | ✅ | [test.md#三] | 主理人主会话 `AGNES_TEST_API_KEY=`→EXIT=3，无提交 |
| AC-1.3 | 零 VIP 消耗 | ✅ | [test.md#三] | run.log mode=test；ensure_test_mode 断言在 images_to_video 前 |
| AC-1.4 | 单命令 `python l1_smoke.py` 可触发 | ✅ | [test.md#三] | 根目录 --help EXIT=0，无 required |

---

## 阿编把关结论

- **放行决定**：✅ 放行（完成）
- **亲自复验证据**（主会话可控实跑，不盲信研发/子agent）：
  1. AC-1.1 `curl --max-time 20 -sI <URL>` → `HTTP/1.1 200 OK` + `Content-Type: video/mp4`（2.2s，531700 字节）。
  2. AC-1.2 `AGNES_TEST_API_KEY= python l1_smoke.py` → `EXIT=3`、守卫提示、输出无 `[提交中]/[poll]/task_id`（零 VIP、零提交）。
  3. AC-1.3 run.log 提交后 `key_pool_status`=`mode:test,has_test_key:true`；`ensure_test_mode()` L92 `assert mode=="test"` 在 `images_to_video`(L261) 前。
  4. AC-1.4 仓库根目录 `python short_drama_workflow/scripts/l1_smoke.py --help` → `EXIT=0`、全默认、无 required。
- **闭环是否跑通**：开发(提交 5 fix)→测试 subagent 静默失败(返回空、未写 test.md、无挂死进程)→主理人依 SOP(current_state 行324 先例)接手主会话实证→全部 PASS→完成。闭环完整（测试角色由主理人实证兜底，符合已立先例）。
- **模型表现**：测试 subagent 异常（静默空返回，非挂死），已记教训并固化"主会话实证"纪律。
- **本次发现的问题**：
  1. [已修] 开发 5 bug（import server / DIAG_DIR 基准 / 桩 basename / sys.modules 注册 / HERE 注释）全闭环，L1 真测端到端 PASS。
  2. [遗留·非阻塞] 把"实跑代码+碰外网"验证甩给子 agent 会静默失败 → 已固化为 §3.5/§7#11 + 本任务实证先例：此类验证必须由主理人在主会话跑。

---

## 下一步建议

- [后续任务 / 遗留项处理]
