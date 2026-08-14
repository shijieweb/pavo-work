# acceptance · T-15（主理人把关填写，对照表逐条勾，附证据）

> 阿编终验：对照每条 AC 勾选 + 证据；全部 PASS 才标「完成」。
> 特别严卡 AC-1.2（54 图全显示）——违反即不通过。

## 主理人读盘核产（§4.3，独立于研发自述，直接解析产物）
- `training_panel.html` = 108,013 B（自包含，无外部请求，远低于 5MB 上限）
- `<img` 总数 = 56（54 缩略图 + 2 角色参考图）；`data-role="thumb"` = 54
- 54 个唯一 `wXX_Y.png` 全部出现在 HTML，**0 缺失**
- `data:image/(png|jpeg);base64` 出现 **0 次** → 确认未把 194MB 图内嵌成卡死浏览器的巨型 HTML（关键工程决策正确）
- 54 条 prompt：文件缺失 0、尾部 40 字符截断 0（CSV 54 行逐条比对）
- `data-writing` 去重 = 27 个（写法号 1–27 连续），分组展示成立
- git `0151ddb` 已提交 `design.md`（训练项目无 git 仓库，生成器/HTML/测试脚本仅落盘，符合任务约定）

## AC 对照表
| AC | 证据 | 结果 |
|---|---|---|
| AC-1.1 | build_training_panel.py（utf-8-sig 去 BOM 读 54 行 + 扫 PNG + 2 参考图，CSS/JS 全内联）；无 `<script src>`/`<link>`/CDN | ✅ PASS |
| AC-1.2 | 主理人核验：56 `<img>`（54 缩略图 + 2 参考图）、54 唯一 `wXX_Y.png` 0 缺失；QA 独立脚本同证 | ✅ PASS（铁律满足·一张不漏） |
| AC-1.3 | 缩略图（本地相对路径）+ 写法号 + 完整 prompt（54/54 未截断）+ url 原文及链接；主理人尾部 40 字符比对 0 截断 | ✅ PASS |
| AC-1.4 | 三态按钮 162=54×3，切换即时高亮边框+角标+按钮；localStorage 落盘 | ✅ PASS |
| AC-1.5 | localStorage 键 `training_panel_adoption_batch001`；导出 JSON=54 条 + CSV=55 行（首字符 BOM 0xFEFF）；QA 实跑确认 | ✅ PASS |
| AC-1.6 | 写法号（27 选项）/ 状态（全部·已采纳·不采纳·待定）筛选生效；空组自动隐藏 | ✅ PASS |
| AC-1.7 | 全选采纳 / 全部清除（confirm 二次确认）生效 | ✅ PASS |
| AC-1.8 | 5 格统计条（总数/已采纳/不采纳/待定/采纳率）实时更新 | ✅ PASS |
| AC-1.9 | 角色参考图区 charA_front + charA_side（本地相对路径） | ✅ PASS |
| AC-1.10 | 顶部阶段说明 + 采纳门槛（三闸：2–3 新场景稳定 / 2.5-flash 均分 ≥90 / 老板抽验） | ✅ PASS |

## 阿编把关结论
**放行决定：✅ 放行（完成）。** AC-1.1~1.10 全部 PASS；老板铁律「54 图一张不漏」经主理人独立读盘 + QA 独立验收双重交叉验证满足（54 唯一图 0 缺失、0 截断、0 base64 内嵌卡死风险）。研发自测（无头 35 断言 0 FAIL）与 QA 独立核验结论一致，无 BUG。

闭环流程跑通：engineer-t15 构建（推待验证）→ qa-t15 独立验收 10/10 PASS（推已验证）→ 主理人读盘核产 + 填 acceptance → 放行完成。研发/测试分离铁律已守。

## 上线须知（转老板）
- 面板路径：`C:\Users\67972\projects\short-drama-training\training_panel.html`，**双击 file:// 打开**即离线可见全部 54 图 + 采纳开关。
- 图片走本地相对路径（非内嵌），故面板**必须留在训练项目根目录**，移走则图失效（不内嵌的固有代价）。
- 真机缩略图渲染需老板开浏览器确认（无头环境无法解码 PNG，已结构确证 src 指向真实存在的本地文件）。
- 采纳标记存 `localStorage`（按 file:// + 浏览器 profile 为界，换浏览器/无痕/清缓存会丢）；审完及时点「导出」存 `04_采纳区/`。
- 训练项目目录无 git 仓库，生成器/HTML 仅落盘；若要纳管建议 `git init` 并把 `out/*.png`、`training_panel.html` 加 `.gitignore`（产物可由生成器一键重建）。
