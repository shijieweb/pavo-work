# test · T-20260812-02 L1 真·管线冒烟

> 模板：`dev-work/templates/TEMPLATE_TEST.md`。**测试填写**，推「已验证」时交付。
> 本任务核心就是"真测"——测试用免费KEY 跑端到端，全程禁止用 VIP。当前状态：**待填（待闸1 签后派活）**。

---

## 一、测试用例 + 覆盖矩阵

| 用例ID | 对应 AC | 输入/动作 | 预期 | 实际 | 结果 | 证据 |
|---|---|---|---|---|---|---|
| TC-1 | AC-1.1 | build_variants(v2) → 查 images | 关键帧为 data:image/...;base64 | | | |
| TC-2 | AC-1.2 | _submit_video(免费KEY) 真实提交 | AGNES 返回 job id | | | |
| TC-3 | AC-1.3 | wait_for_video 轮询 | 取回视频 url/路径 | | | |
| TC-4 | AC-1.4 | 日志确认所用 KEY | 仅 AGNES_TEST_API_KEY，零 VIP | | | |
| TC-5 | AC-1.5 | 排队期回报 | 心跳 + 阿编报平安 | | | |

---

## 二、L1 真·管线冒烟（本任务主体，用免费KEY）

- **是否触发 L1**：是（本任务即 L1 本身）
- 免费KEY：`AGNES_TEST_API_KEY`（无限额度，仅排队，不占 VIP）
- 真实镜头：模板 camera_move_v2 + 关键帧源（参考图或本地测试 PNG 经 data_uri）→ 调 `_submit_video`
- 命令 + 输出：
```
<派活后填：真实调用命令与 AGNES 返回>
```
- 断言：payload（keyframes/data_uri/prompt/negative/seed）真传到 AGNES、返回可拼 → [PASS/FAIL]

---

## 三、重跑研发回归（不盲信研发输出）
```
<派活后填>
```

## 四、缺陷清单（[BUG] 格式，仅报告不改）
- [若发现 P0-1 真实管线 bug，按 [BUG] 格式提单，回 T-20260812-01 修复]

## 五、整体结论
- [ ] 建议阿编放行 / [ ] 退回开发修复
- 覆盖矩阵：AC-1.1~1.5 全部 PASS / 存在 FAIL
- P0/P1：无 / 有（列出）
- 证据存档：本文件 + [截图/日志路径]
