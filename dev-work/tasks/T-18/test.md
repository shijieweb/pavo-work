# T-18 test.md（测试填）

> 按 `dev-work/templates/TEMPLATE_TEST.md` 填。独立验收、不盲信开发自报、实跑、推「已验证」即停，无 done 权。

## 验证矩阵（覆盖 PRD AC-1.1~1.8）

| AC | 验证手法 | 期望 |
|----|---------|------|
| AC-1.1 | 起 8799 隔离实例，curl `/batch/__asset__/cand/w01_1.png` / `/ref/charA_front.png`；curl 穿越 `/batch/__asset__/cand/../x.png` | 200 image/png；穿越 403 |
| AC-1.2 | 读 training_panel.html，统计 img src 含 `/batch/__asset__/cand/`(54) / `/ref/`(2)；中文目录 `01_配方训练` 在 src 出现次数 | 54/2；src 中中文目录=0 |
| AC-1.3 | 读 HTML 确认 openLightbox 用 it.rel_path（已改为 ASCII）；openRefLightbox 用 img src（已改 ASCII）；点击逻辑无需改 | 大图 URL 全 ASCII |
| AC-1.4 | 统计 `class="wp-cmp"` 计数；抽 3 写法号看文字 | ==27；含「无区别」「仅随机种子不同」 |
| AC-1.5 | 主理人式计数脚本：`<img`=56 / thumb=54 / wXX_Y=54 / base64=0 / 中文锚点=54 / data-writing=27 / writing-purpose=27 | 全匹配 |
| AC-1.6 | grep 新增块禁项 | `<img` 新增=0 / base64=0 / 「同一个齐肩黑发」=0 |
| AC-1.7 | 8799 隔离 + 线上 8787 复验：54候选+2参考全 200；6 路由+35 反代回归零破坏；穿越 403 | 全绿 |
| AC-1.8 | 查 WorkBuddy/workbuddy 仓 git log 含 `before:` 提交 | 存在 |

## 缺陷清单（仅报不改）
（[BUG][S|P] 格式）

## 结论
（建议放行 / 退回）
