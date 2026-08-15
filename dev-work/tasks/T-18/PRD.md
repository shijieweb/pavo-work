# 任务卡 T-18 · batch 面板外网图片修复 + 每写法号「两张图生成参数对比」行

- 需求基线闸：老板连续指令亲签（「把这个URL加进去让我外网访问」→「是那个batch面板啊」→「外网看不见图片了顺便修」+「合并建议下面加一个两张图的提示词生成区别就是图片生成区别，没区别就写无区别」）。视同闸1老板签核。
- 自签依据（R1）：属 A-1 闸1 自签（纯静态展示修复 + 文本增强，不改需求基线）。白名单核验：新增 `/batch/__asset__/` 静态资产路由属「接口变更」，但系老板明确授权"让 batch 面板外网可达（含修图）"的必需修复，授权成立；**未触碰** 鉴权 / 生产数据 / 生成逻辑 / 大额度 / VIP。
- 目标：
  1. 修复外网图片不可见。根因 = 面板 `<img src>` 用中文目录 URL（`/batch/01_配方训练/...`），外网隧道/代理层对百分号编码的中文路径拒载或转坏 → 页面能开、图裂。
  2. 每个写法号「合并建议」下加「两张图生成参数对比」行。事实（run_batch001.py）：同写法号两张图 `image_to_image(prompt, REF, size=2K, ratio=9:16)` 调用完全相同，prompt/参考图/尺寸/比例/负向词全同，**唯一差别是模型随机种子（未显式传入）** → 诚实结论=无区别。
- 产出路径（单源真理：只改生成器 + 代理，重生成 HTML，禁手改 HTML）：
  - 改 `C:\Users\67972\WorkBuddy\workbuddy\agnes_proxy.py`：do_GET 的 `/batch` 分支增加 `__asset__` 子路由 → 新增 `_serve_batch_asset(kind, name)`。
  - 改 `C:\Users\67972\projects\short-drama-training\build_training_panel.py`：render_card 的 `rel_path` 与 ref_cards 的 `r["rel_path"]` 改为 ASCII 资产 URL；writing-purpose 块「合并建议」后加参数对比行 + 对应 CSS。
  - 重生成 `C:\Users\67972\projects\short-drama-training\training_panel.html`。

## 验收标准（AC 锚点）

- [ ] **AC-1.1** 代理新增 `/batch/__asset__/cand/<name>` 与 `/batch/__asset__/ref/<name>` 路由，返回对应磁盘 PNG（HTTP 200 image/png）；路径含 `..` 或 `/` 等穿越字符 → 403。
- [ ] **AC-1.2** HTML 内 54 张候选图 `<img src>` 全部为 `/batch/__asset__/cand/<file>`、2 张参考图为 `/batch/__asset__/ref/<file>`；HTML 中**不再出现任何中文目录**出现在 img src（`01_配方训练` 等字眼在 src 里计数为 0）。
- [ ] **AC-1.3** lightbox 候选大图（openLightbox 用 `it.rel_path`）与参考大图（openRefLightbox 用 img src）均走 ASCII URL，点击放大不裂。
- [ ] **AC-1.4** 每个写法号 `writing-purpose` 块「合并建议」后出现「两张图生成参数对比：无区别（prompt / 参考图 / size=2K / ratio=9:16 / 负向词 NEG 全部相同，仅模型随机种子不同，未显式传入）」行（期望 27 个 `wp-cmp`）。
- [ ] **AC-1.5** 铁律不变：`<img` 总数=56、tag 级 `data-role="thumb"`=54、唯一 `wXX_Y.png`=54、base64=0、中文锚点「同一个齐肩黑发」=54、`data-writing` 去重=27、`writing-purpose`=27。
- [ ] **AC-1.6** 新增块禁引入 `<img`/`base64`/`data:image` 之外的新 img 标签；新增文本禁写「同一个齐肩黑发」6 字。
- [ ] **AC-1.7** 先在隔离实例 **8799** 全量验证（54 候选 + 2 参考经 `/batch/__asset__/` 全 200；既有 6 路由 + 35 反代回归零破坏；目录穿越 403）再切线上 8787；线上 8787 复验全绿。
- [ ] **AC-1.8** 代理改动前对 `agnes_proxy.py`（WorkBuddy/workbuddy 仓）做 `git commit before:`，仅落盘、不碰训练项目 git（训练项目无 git 跟踪）。

## 证据要求

- 开发：git diff（agnes_proxy.py）+ 重生成命令输出 + `self_check` 全 PASS 数字（9 项铁律 + wp-cmp 27）+ 隔离实例 8799 验证脚本 stdout（无输出=未测=不通过）。
- 测试：实跑 8799 隔离 + 线上 8787 验证脚本输出 + pass/fail + 缺陷清单（`[BUG][S|P]` 格式，仅报不改）。

## 边界禁止项

- 禁改生成逻辑 / AGNES 调用 / 鉴权 / VIP。
- 禁手改 `training_panel.html`（只改生成器重生成）。
- 禁引入 base64 内嵌图片。
- 禁破坏 T-16/T-17 铁律锚点（`<img`=56 等）。
