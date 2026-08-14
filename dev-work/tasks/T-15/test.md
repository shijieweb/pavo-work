# test · T-15（独立测试填写，推「已验证」即停，不修 bug）

> QA 独立验收 + 实跑。重点核验"全量数据"老板铁律（54 张全显示，一张不漏）。
> 验收角色：qa-t15。纪律：只验收、绝不改代码；发现 BUG 仅报告。

## 一、验收环境与独立脚本

- 训练项目根：`C:\Users\67972\projects\short-drama-training`
- 面板产物：`training_panel.html`（108,013 B，自包含）
- 研发自测脚本：`scripts/test_panel_logic.js`（重跑，作证据）
- QA 独立脚本（不依赖研发代码，落盘于本任务目录，未污染产品线）：
  - `qa_independent_verify.py` —— 独立解析 HTML+CSV，结构核验 + 抽样 prompt 全文
  - `qa_export_exec.js` —— 自建最小 DOM/Blob/URL/localStorage stub，实跑面板 `exportJson/exportCsv`

## 二、覆盖矩阵（每条 AC：验证命令 + 证据 + 结果）

| AC | 验证命令/动作 | 证据 | 结果 |
|---|---|---|---|
| AC-1.1 | 跑 `node scripts/test_panel_logic.js`（组[1] ITEMS=54）+ `python3` grep `<script src=`/`<link>`/CDN | `<script src=>`=0、`<link href=>`=0、CDN 引用=0；内联 `ITEMS` 长度=54；全部 `<img>` 的 src 为本地相对路径（http(s) src=0），无外部请求依赖 | **PASS** |
| AC-1.2 | `python3 qa_independent_verify.py`（STEP2）+ grep | `data-role="thumb"`=54；全部 `<img>`=56（54 缩略图+2 参考图）；54 个唯一 `wXX_Y.png` 文件名 **0 缺失**；`data-writing` 去重=连续 1–27；预渲染 card=54；`ITEMS`=54 | **PASS** |
| AC-1.3 | `qa_independent_verify.py`（STEP2.6 + STEP3 抽样 3 条含最长） | prompt 全文(转义后)缺失=**0**；尾部 40 字符缺失=**0**；抽样 `w01_1.png`(382)/`w05_1.png`(279)/`w21_2.png`(271) 全文+尾部均在 HTML；含 url 链接块=54 | **PASS** |
| AC-1.4 | `node scripts/test_panel_logic.js`（组[3]）+ grep | 三态按钮 pending/adopt/reject 各 54（共 162=54×3）；组[3] 8/8 PASS（切 adopt→状态/高亮/角标「已采纳」/统计+1/localStorage 落盘；切 reject→旧高亮移除） | **PASS** |
| AC-1.5 | `node qa_export_exec.js`（独立实跑 exportJson/exportCsv）+ 组[5][7] | 独立导出 JSON `total=54`/`records=54`（含 6 字段、prompt 非截断 最短=212）；CSV 首字符 BOM(0xFEFF)+55 行(表头+54)、每行 6 字段、54 文件名全含；localStorage 键名 `training_panel_adoption_batch001` 存在于源码；组[7] 落盘 54 条、刷新不丢 | **PASS** |
| AC-1.6 | `node scripts/test_panel_logic.js`（组[6]）+ grep | 写法号下拉 `option`=27；含 全部/已采纳/不采纳/待定 筛选项；组[6] 3/3 PASS（状态=已采纳 可见 1 / 写法号=1 可见 2 / 复位 可见 54） | **PASS** |
| AC-1.7 | `node scripts/test_panel_logic.js`（组[4]）+ grep | 含「全选采纳」「全部清除」文案；组[4] 4/4 PASS（全选采纳→已采纳 54/待定 0/采纳率 100%，全部卡高亮） | **PASS** |
| AC-1.8 | `node scripts/test_panel_logic.js`（组[2][3][4]）+ grep | 含 总图数/已采纳/不采纳/采纳率/待定 文案；组[2]初始 54/54/0/0%；组[3]切 adopt→已采纳 1；组[4]全选→已采纳 54/采纳率 100% | **PASS** |
| AC-1.9 | `python3` grep `class="ref-img"` | `ref-img`=2；src=`01_配方训练/角色参考图/charA_front.png` 与 `charA_side.png`（本地相对路径） | **PASS** |
| AC-1.10 | `python3` grep 顶部门槛文案 | 含「阶段说明」+「采纳门槛（三闸并行）」：①至少 2–3 个新场景 下角色形象稳定 ②裁判模型 2.5-flash 均分 ≥90 ③老板抽验。三者均存在 | **PASS** |

## 三、重跑研发无头测试（交叉证据）

```
命令: node scripts/test_panel_logic.js   (cwd = 训练项目根)
结果: 退出码 = 0 ; [PASS] = 35 行 ; [FAIL] = 0
分组: [1]数据与索引 5/5 | [2]初始统计 4/4 | [3]三态+持久化 8/8
      | [4]批量 4/4 | [5]导出 9/9 | [6]筛选 3/3 | [7]刷新不丢 2/2
结论: 研发自写测试全 PASS，与 QA 独立核验一致。
```

## 四、独立结构核验关键数字（qa_independent_verify.py）

```
[2.1] <img 标签总数        = 56   (54 缩略图 + 2 参考图)        PASS
[2.2] data-role="thumb" 数 = 54                                 PASS
[2.3] class="ref-img" 数    = 2                                  PASS
[2.4] data:image/*;base64 次数 = 0        (铁律: 禁内嵌防卡死)  PASS
[2.5] 唯一 wXX_Y.png 文件名  = 54 ; 缺失 = 0                    PASS
[2.6] prompt 全文(转义)缺失 = 0 ; 尾部40字符缺失 = 0            PASS
[2.7] data-writing 去重 1..27 连续 = True                       PASS
[2.8] 分组 group 数        = 27                                 PASS
[2.9] 预渲染 card 数        = 54                                 PASS
[2.10] 内联 ITEMS 长度      = 54                                 PASS
[2.11] <img> http(s) 远程 src = 0        (全本地相对路径)       PASS
[2.12] 每写法号张数均 2 张   = True (27 写法号各 2 张)           PASS
抽样 3 条: w01_1.png(382)/w05_1.png(279)/w21_2.png(271) 全文+尾部40字符均在 HTML
```

## 五、独立导出实跑（qa_export_exec.js，复用面板内联 exportJson/exportCsv）

```
JSON: total=54, records=54, adopted=0, rejected=0, pending=54
      每条含6字段(file/writing_no/state/state_label/prompt/url/rel_path)
      prompt 非截断 最短=212 ; 唯一 file=54
CSV : 首字符 BOM(0xFEFF)=True ; 行数=55(表头+54) ; 表头="file","写法号","采纳状态","prompt","url","本地相对路径"
      全部54数据行均6字段 ; 含全部54文件名(缺失=0)
localStorage 键名 training_panel_adoption_batch001 存在于源码 = True
退出码 = 0 ; 全部 PASS
```

## 六、缺陷清单

**无 BUG。**

- 老板铁律「54 张全显示」经多重独立证据确认满足：静态预渲染 54 张 `<img data-role="thumb">` + 54 个唯一文件名 0 缺失 + `ITEMS`=54 + 预渲染 card=54，且图片走本地相对路径（非抽样、非 base64 内嵌）。
- 未发现「数据未全显示 / prompt 截断 / 内嵌导致卡死」类缺陷。

## 七、局限声明（观察项，非 BUG，不因此判 FAIL）

- **真机图片解码（观察项）**：无头环境（Node + 最小 stub）无法真正解码 PNG/渲染像素。已确证 HTML 结构层面 54 张缩略图标签齐全且 `src` 指向真实存在的本地相对路径（`batch-001/out/wXX_Y.png` 共 194MB 已由数据真值确认存在），但 **`file://` 双击后 54 张缩略图是否真实渲染（非碎图/占位）需老板/主理人开浏览器确认**。此为主观/环境观察项，不计入缺陷。
- **`04_采纳区/` 未自动写入（符合预期）**：浏览器安全模型下网页无法直写本地目录，导出走浏览器下载，需老板手动移入。设计如此，非缺陷。
- **localStorage 作用域**：以 `file://` + 浏览器 profile 为界；换浏览器/无痕/清缓存会丢标记 —— 提醒老板审完及时导出存 `04_采纳区/`。

## 八、验收结论

**建议放行（PASS）。** 10 条 AC 全部 PASS，老板铁律（AC-1.2 全量 54 张）经独立交叉验证满足；研发自测（35 断言全 PASS，退出码 0）与 QA 独立核验结论一致；导出 JSON/CSV 全量 54 条、localStorage 持久化键名正确。仅余「真机渲染」观察项需老板开浏览器最终确认（非 BUG）。
