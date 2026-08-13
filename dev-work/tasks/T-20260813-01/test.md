# test · T-20260813-01 l1_smoke 固化进回归套件

> 模板来源：`dev-work/templates/TEMPLATE_TEST.md`。**本文件由主理人(阿编)接手填写**——  
> 独立测试 subagent 静默返回空（未写本文件、无残留进程），依 `current_state.md` 行 324 先例  
> 「测试 Agent 异常→主理人接手实证+落文件」，主理人于主会话可控实跑逐项复核（非研发自报、非子agent黑箱）。  
> 铁律：独立验证亲自跑；无 P0/P1；每条结论附证据。

---

## 一、测试用例 + 覆盖矩阵

| 用例ID | 对应 AC  | 输入/动作                                                   | 预期                                         | 实际                                                                                       | 结果   | 证据                 |
| ---- | ------ | ------------------------------------------------------- | ------------------------------------------ | ---------------------------------------------------------------------------------------- | ---- | ------------------ |
| TC-1 | AC-1.1 | 主理人主会话 `curl --max-time 20 -sI <成片URL>`                 | 200 + video/mp4                            | `HTTP/1.1 200 OK`、`Content-Type: video/mp4`、`Content-Length: 531700`                     | PASS | §三 / design.md#3.2 |
| TC-2 | AC-1.2 | `AGNES_TEST_API_KEY= python l1_smoke.py`（强制非 test 模式）   | 入口守卫中止、非零退出、不调 gen_video                   | `EXIT=3`、守卫提示、`mode=prod`、无 `[提交中]/[poll]/task_id`                                       | PASS | §三                 |
| TC-3 | AC-1.3 | 查 run.log `key_pool_status` + 代码审查 `ensure_test_mode()` | mode=test、零 VIP、prod 路径不可达 images_to_video | 提交后 `mode:test,has_test_key:true`；L92 `assert mode=="test"` 在 `images_to_video`(L261) 之前 | PASS | §三 / design.md#3.2 |
| TC-4 | AC-1.4 | 从仓库根目录 `python <绝对路径>/l1_smoke.py --help`               | exit 0、参数全默认、无 required                    | `EXIT=0`、7 个参数均带默认值、无 required                                                           | PASS | §三                 |

> 覆盖矩阵 100% 覆盖 PRD 的 AC-1.1~1.4。

---

## 二、L1 真·管线冒烟（触及生成逻辑必做，用免费KEY）

- **是否触发 L1**：是。happy-path 真测由主理人于 2026-08-13 02:12 在主会话可控后台实跑（task V3gwmQ）完成：  
  `build_variants` → `images_to_video(免费KEY)` → 轮询 → 取回成片，全程 `mode=test`、零 VIP。
- 成片证据：`short_drama_workflow/scripts/l1_smoke.last_url.txt`（URL）+ `l1_smoke.run.log`（完整 stdout，已覆盖 01:54 失败版）。
- 断言：data_uri 关键帧真传到 AGNES（AC-1.1 的 `data:image/...`）、返回可访问成片（TC-1 curl 200）→ **PASS**。

---

## 三、主理人主会话重跑（不盲信研发/子agent 输出）

### TC-1（AC-1.1）成片可达

```bash
URL="$(cat short_drama_workflow/scripts/l1_smoke.last_url.txt)"
curl --max-time 20 -sI "$URL"; echo "CURL_EXIT=$?"
```

```
HTTP/1.1 200 OK
Content-Type: video/mp4
Content-Length: 531700
Accept-Ranges: bytes
CURL_EXIT=0   # 实测耗时 2.2s
```

### TC-2（AC-1.2）入口守卫中止（零 VIP，核心独立验证）

```bash
cd short_drama_workflow/scripts
AGNES_TEST_API_KEY= python l1_smoke.py 2>&1; echo "EXIT=$?"
```

```
== l1_smoke 开始: 2026-08-13 16:11:15 ==
❌ 入口守卫：当前 mode=prod（VIP/prod），且无 AGNES_TEST_API_KEY 可切免费 KEY；为杜绝误烧 VIP，立即非零退出，绝不进入 gen_video。
EXIT=3
```

> 关键点：输出中**完全没有** `[提交中]` / `[poll]` / 任何 `task_xxx` → 证明在 `images_to_video` 之前已 `sys.exit(3)`，零网络提交、零 VIP 消耗。机制：`load_env` 仅在变量不在 `os.environ` 时读 `.env`，故 shell 传入空 `AGNES_TEST_API_KEY=` 使 `agnes_client._pool.test_key=""` → `use_test()` 返回 False → 守卫触发。

### TC-3（AC-1.3）零 VIP + 代码审查

- run.log 提交后快照（design.md#3.2）：`{"total":3,"active":3,"bad":[],"switches":1,"cooldown":[],"mode":"test","has_test_key":true}` → 全程免费 KEY，零 VIP。
- `l1_smoke.py` `ensure_test_mode()`（L75-94）：先读 `key_pool_status()["mode"]`；非 test 且 `use_test()` 为 False → `sys.exit(3)`；最后 `assert mode=="test"`（L92）双重保险。`images_to_video` 仅在 `ensure_test_mode()` 返回后调用（L261）。→ 任何 prod 路径都不可能到达 `images_to_video`，VIP 永不触发。

### TC-4（AC-1.4）单命令、任意目录

```bash
cd C:/Users/67972/WorkBuddy/workbuddy        # 注意：从 非 scripts 目录 触发
python short_drama_workflow/scripts/l1_smoke.py --help; echo "EXIT=$?"
```

```
usage: l1_smoke.py [-h] [--width WIDTH] [--height HEIGHT]
                   [--num-frames NUM_FRAMES] [--frame-rate FRAME_RATE]
                   [--timeout TIMEOUT] [--interval INTERVAL]
                   [--negative NEGATIVE]
L1 免费KEY 端到端真测冒烟（回归守卫）
options:  (全部带默认值，无 required 项)
EXIT=0
```

> 证明 `HERE=os.path.dirname(os.path.abspath(__file__))` 用绝对路径定位 server.py / prompt_training / assets，不依赖 cwd；零参数即可跑（主理人 V3gwmQ 即以零参数端到端跑通）。

---

## 四、缺陷清单（[BUG] 格式，仅报告不改）

无。AC-1.1~1.4 全部 PASS，无 P0/P1。

---

## 五、整体结论

- [x] 建议阿编放行（完成）
- [ ] 覆盖矩阵：AC-1.1~1.4 **全部 PASS**
- [ ] P0/P1：无
- [ ] 证据存档：本文件 + `design.md`#3.2 + `l1_smoke.run.log` + `l1_smoke.last_url.txt`
- [ ] 过程备注：独立测试 subagent 本轮静默失败（返回空、未写本文件、无挂死进程），主理人依 `current_state.md` 行 324 先例接手主会话实证，结论同上，真实可信。
