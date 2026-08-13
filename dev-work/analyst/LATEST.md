# 📮 LATEST.md · 分析师最新留言

- **时间**：2026-08-13 16:45
- **状态**：🟢 已读 + 已处理（inbox/ 3 条全部归档至 `archive/`）
- **一句话结论**：3 条留言处置完毕——
  1. **对外入口暴露（高危）→ 已闭环**：原 D4"本地网络"前提破产（8787 绑定 0.0.0.0 + 公网隧道可直达 + /studio·PUT 无鉴权）。已开 **T-20260813-03** 加 `PORTAL_TOKEN` 令牌闸，覆盖 /studio + /api/* + /v1 + /agnesapi + /console + /merge；localhost + 公网双路径实测无 token→401、带 token→200，公网未授权读/写两类洞均封堵。老板书签：`agnes.owen1.de5.net/studio?token=<PORTAL_TOKEN>`。
  2. **分析师服务条款（知会）**：角色/协作约定，无需动作，留存备案。
  3. **l1_smoke 返工闭环观察**：①`run.log` 旧失败版已覆盖（commit 32fb6e8）；②成片证据文件名 `l1_smoke.last_url.txt` 已核对正确；③`server.py` 加载 logging 与 8777 争用日志（非致命 PermissionError 噪声）→ 排 backlog，后续可修。
- **详情**：`dev-work/analyst/archive/2026-08-13-0216_*.md`、`2026-08-13-0224_*.md`、`2026-08-13-0228_*.md`
- **下一步（待老板）**：T-20260813-02 8787 路由注册表收敛规格卡仍在 roadmap，可自取派活；对外入口后续可上 VPS 防火墙层（O5）做纵深防御。
