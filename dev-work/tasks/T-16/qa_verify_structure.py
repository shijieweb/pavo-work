# -*- coding: utf-8 -*-
"""
T-16 QA 独立结构核验 (QA 自写, 不复用研发脚本).

只读: training_panel.html + prompts_zh.csv + prompts.csv + out/*.png
不改任何源码。用正则/csv 独立重新解析, 逐项打印数字。

运行: python qa_verify_structure.py
退出码: 0 = 全部核验点通过, 1 = 存在 FAIL
"""
import csv
import os
import re
import sys

PANEL = r"C:\Users\67972\projects\short-drama-training\training_panel.html"
BATCH = r"C:\Users\67972\projects\short-drama-training\01_配方训练\实验批次\batch-001"
OUT = os.path.join(BATCH, "out")
ZH_CSV = os.path.join(OUT, "prompts_zh.csv")
EN_CSV = os.path.join(OUT, "prompts.csv")

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    flag = "PASS" if cond else "FAIL"
    print("  [%s] %s%s" % (flag, name, ("  -> " + detail) if detail else ""))


html = open(PANEL, encoding="utf-8").read()
print("面板文件: %s" % PANEL)
print("面板大小: %d 字节 (%.1f KB)\n" % (len(html.encode("utf-8")), len(html.encode("utf-8")) / 1024.0))

# ---------------------------------------------------------------- 1. img 标签
print("[1] 图片标签总量 (AC-7 铁律)")
img_tags = re.findall(r"<img\b[^>]*>", html, re.I)
check("<img> 标签总数 == 56 (54 缩略图 + 2 参考图)", len(img_tags) == 56,
      "实测 %d" % len(img_tags))

thumb_tags = [t for t in img_tags if re.search(r'data-role\s*=\s*"thumb"', t)]
check('tag 级 data-role="thumb" == 54', len(thumb_tags) == 54,
      "实测 %d" % len(thumb_tags))

ref_tags = [t for t in img_tags if not re.search(r'data-role\s*=\s*"thumb"', t)]
print("       (非 thumb 的 <img> = %d 个: %s)"
      % (len(ref_tags), [re.search(r'src="([^"]*)"', t).group(1) if re.search(r'src="([^"]*)"', t) else "?" for t in ref_tags]))

# ---------------------------------------------------------------- 2. 54 唯一文件名
print("\n[2] 54 张 wXX_Y.png 全覆盖 (AC-7)")
disk_pngs = sorted(f for f in os.listdir(OUT) if re.fullmatch(r"w\d{2}_\d\.png", f))
check("磁盘上 wXX_Y.png 数量 == 54", len(disk_pngs) == 54, "实测 %d" % len(disk_pngs))

html_pngs = set(re.findall(r"(w\d{2}_\d\.png)", html))
check("HTML 中出现的唯一 wXX_Y.png == 54", len(html_pngs) == 54,
      "实测 %d" % len(html_pngs))

missing = [f for f in disk_pngs if f not in html_pngs]
check("磁盘 54 张全部出现在 HTML, 0 缺失", not missing,
      "缺失: %s" % missing if missing else "")

extra = sorted(html_pngs - set(disk_pngs))
check("HTML 无磁盘不存在的幽灵文件名", not extra, "多余: %s" % extra if extra else "")

# thumb src 逐一可解析 + 磁盘存在
thumb_srcs = []
for t in thumb_tags:
    m = re.search(r'src="([^"]*)"', t)
    thumb_srcs.append(m.group(1) if m else None)
check("54 个 thumb 均有 src", all(thumb_srcs), "")
bad_disk = []
for s in thumb_srcs:
    if not s:
        continue
    p = os.path.join(os.path.dirname(PANEL), s.replace("/", os.sep))
    if not os.path.isfile(p):
        bad_disk.append(s)
check("54 个 thumb src 相对路径在磁盘均存在", not bad_disk,
      "不存在: %s" % bad_disk[:5] if bad_disk else "")
check("54 个 thumb src 互不重复", len(set(thumb_srcs)) == 54,
      "唯一数 %d" % len(set(thumb_srcs)))

# ---------------------------------------------------------------- 3. base64
print("\n[3] 禁止 base64 内嵌 (AC-7, 防 194MB 膨胀)")
b64 = re.findall(r"data:image/[a-zA-Z0-9.+-]+;base64", html)
check("data:image/*;base64 出现次数 == 0", len(b64) == 0, "实测 %d" % len(b64))
size_kb = len(html.encode("utf-8")) / 1024.0
check("HTML 体积 < 1MB (自包含但不内嵌图)", size_kb < 1024, "实测 %.1f KB" % size_kb)

# ---------------------------------------------------------------- 4. 中文内联
print("\n[4] 中文 prompt 已内联 (AC-2)")
anchor = "同一个齐肩黑发"
cnt_anchor = html.count(anchor)
check("中文锚点「%s」出现 == 54" % anchor, cnt_anchor == 54, "实测 %d" % cnt_anchor)

# ---------------------------------------------------------------- 5. 写法号
print("\n[5] 写法号分组 (AC-3)")
writings = re.findall(r'data-writing\s*=\s*"(\d+)"', html)
uniq_w = sorted({int(x) for x in writings})
check("data-writing 去重 == 27", len(uniq_w) == 27, "实测 %d" % len(uniq_w))
check("写法号 1..27 连续无跳号", uniq_w == list(range(1, 28)),
      "实测 %s" % uniq_w if uniq_w != list(range(1, 28)) else "")

# ---------------------------------------------------------------- 6. 关键字符串
print("\n[6] 关键 DOM/逻辑锚点存在")
for token in ['id="lightbox"', "normalizeGroup", "双图优", "主图", "备选", "弃"]:
    c = html.count(token)
    check("字符串存在: %s" % token, c > 0, "出现 %d 次" % c)

print("\n[6b] T-15 遗留能力锚点 (AC-8 / 不回退)")
for token in ["角色参考图", "阶段", "导出", "localStorage"]:
    c = html.count(token)
    check("T-15 锚点存在: %s" % token, c > 0, "出现 %d 次" % c)

print("\n[6c] AC-4 规则说明块 + AC-5 统计条")
check("含「两张都可以」规则说明块",
      ("两张都可以" in html), "出现 %d 次" % html.count("两张都可以"))
for token in ["写法号采纳", "双图优", "采纳率"]:
    check("统计条含: %s" % token, token in html, "")

print("\n[6d] AC-1 lightbox 交互锚点")
for token in ["Escape", "lightbox"]:
    check("lightbox 交互锚点: %s" % token, token in html,
          "出现 %d 次" % html.count(token))

# ---------------------------------------------------------------- 7. 中文真实性抽查
print("\n[7] 中文真实性抽查 (AC-2, 全文 0 截断)")
zh_rows = list(csv.DictReader(open(ZH_CSV, encoding="utf-8-sig")))
check("prompts_zh.csv 行数 == 54", len(zh_rows) == 54, "实测 %d" % len(zh_rows))
cols = list(zh_rows[0].keys()) if zh_rows else []
check("prompts_zh.csv 列 = file/写法号/prompt_zh",
      cols == ["file", "写法号", "prompt_zh"], "实测 %s" % cols)
check("prompt_zh 无空值", all((r["prompt_zh"] or "").strip() for r in zh_rows), "")

# 抽 3 条: 写法号 24 / 5 / 19
sampled = 0
for target in ("24", "5", "19"):
    row = next((r for r in zh_rows if str(r["写法号"]).strip() == target), None)
    if row is None:
        check("抽查写法号 %s 存在于 CSV" % target, False, "未找到")
        continue
    zh = row["prompt_zh"].strip()
    sampled += 1
    print("       写法号 %s / %s / 中文长度 %d 字" % (target, row["file"], len(zh)))
    check("写法号 %s 中文 prompt 全文出现在 HTML (0 截断)" % target, zh in html,
          "" if zh in html else "HTML 中未找到完整中文, 首 30 字=%r" % zh[:30])
check("成功抽查 3 条", sampled == 3, "实测 %d" % sampled)

# 全量 54 条中文是否都完整内联 (更强的判定)
not_inlined = [r["file"] for r in zh_rows if r["prompt_zh"].strip() not in html]
check("54 条中文 prompt 全部完整内联 (全量强校验)", not not_inlined,
      "未内联: %s" % not_inlined[:5] if not_inlined else "")

# 中英 file 集合一致
en_rows = list(csv.DictReader(open(EN_CSV, encoding="utf-8-sig")))
en_files = {r["file"].strip() for r in en_rows}
zh_files = {r["file"].strip() for r in zh_rows}
check("中英 CSV file 集合一致", en_files == zh_files,
      "仅英 %s / 仅中 %s" % (sorted(en_files - zh_files)[:3], sorted(zh_files - en_files)[:3]))

# 英文 prompt 也全文内联 (对照, 0 截断)
en_key = "prompt" if "prompt" in (en_rows[0] if en_rows else {}) else list(en_rows[0].keys())[-1]
en_not_inlined = [r["file"] for r in en_rows if r[en_key].strip() and r[en_key].strip() not in html]
check("54 条英文 prompt 全部完整内联 (对照 0 截断)", not en_not_inlined,
      "未内联: %s" % en_not_inlined[:5] if en_not_inlined else "")

# ---------------------------------------------------------------- 8. 汇总
print("\n===== QA 独立核验汇总 =====")
n_pass = sum(1 for _, ok, _ in results if ok)
n_fail = len(results) - n_pass
print("通过: %d 条" % n_pass)
print("失败: %d 条" % n_fail)
if n_fail:
    print("\n失败明细:")
    for name, ok, detail in results:
        if not ok:
            print("  - %s  %s" % (name, detail))
print("[结果] %s" % ("QA 独立结构核验全部通过" if not n_fail else "存在 FAIL, 需打回"))
sys.exit(0 if not n_fail else 1)
