# -*- coding: utf-8 -*-
"""
T-15 独立验收脚本（QA 自写，不依赖研发 test_panel_logic.js / build_training_panel.py）
重跑研发脚本 + 独立解析 HTML/CSV 逐项给数字证据。
"""
import csv, html, json, re, os, subprocess, sys

PROJ = r"C:\Users\67972\projects\short-drama-training"
HTML = os.path.join(PROJ, "training_panel.html")
CSV  = os.path.join(PROJ, r"01_配方训练\实验批次\batch-001\out\prompts.csv")

print("=" * 70)
print("STEP 1: 重跑研发无头测试 scripts/test_panel_logic.js")
print("=" * 70)
r = subprocess.run(["node", "scripts/test_panel_logic.js"], cwd=PROJ,
                   capture_output=True, text=True)
print(r.stdout)
print("研发脚本 EXIT CODE =", r.returncode)
# 统计 PASS 数（粗略：PASS 行数）
pass_n = r.stdout.count("[PASS]")
fail_n = r.stdout.count("[FAIL]")
print(f"断言统计: PASS={pass_n} FAIL={fail_n}  EXIT={r.returncode}")

print("\n" + "=" * 70)
print("STEP 2: 独立结构核验（直接解析 HTML + CSV）")
print("=" * 70)

# --- 读 HTML（去 BOM 无关，HTML 本身无 BOM；用 utf-8 读） ---
with open(HTML, "r", encoding="utf-8") as f:
    ht = f.read()

# 2.1 <img> 标签总数
img_total = len(re.findall(r"<img", ht))
# 2.2 data-role="thumb" 数量
thumb = ht.count('data-role="thumb"')
# 2.3 参考图 <img class="ref-img">
ref_img = len(re.findall(r'class="ref-img"', ht))
print(f"[2.1] <img 标签总数         = {img_total}   (期望 56 = 54缩略图 + 2参考图)")
print(f"[2.2] data-role=\"thumb\" 数  = {thumb}   (期望 54)")
print(f"[2.3] class=\"ref-img\" 数     = {ref_img}   (期望 2)")

# 2.4 base64 内嵌（铁律：必须 0）
b64 = len(re.findall(r'data:image/(png|jpeg);base64', ht))
print(f"[2.4] data:image/*;base64 次数 = {b64}      (铁律: 必须 0)")

# --- 读 CSV（去 BOM） ---
with open(CSV, "r", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
csv_files = [ (row.get("file") or "").strip() for row in rows ]
csv_prompts = [ (row.get("prompt") or "") for row in rows ]
csv_writing = [ (row.get("写法号") or "").strip() for row in rows ]
print(f"\n[CSV] 数据行数 = {len(rows)}")
print(f"[CSV] 唯一 file 数 = {len(set(csv_files))}")
print(f"[CSV] 唯一写法号 = {sorted(set(csv_writing), key=lambda x:int(x) if x.isdigit() else 999)}")

# 2.5 54 个唯一 wXX_Y.png 文件名全部出现在 HTML
missing = [fn for fn in set(csv_files) if fn not in ht]
print(f"[2.5] 唯一 wXX_Y.png 文件名数 = {len(set(csv_files))} ; 缺失 = {len(missing)}")
if missing:
    print("       缺失文件:", missing)

# 2.6 prompt 完整全文（含尾部 40 字符）出现在 HTML（0 截断/缺失）
# HTML 中 prompt 经 html.escape 输出，故对 CSV prompt 做同款转义再匹配
esc_missing = []
tail_missing = []
for fn, p in zip(csv_files, csv_prompts):
    pe = html.escape(p)
    if pe not in ht:
        esc_missing.append(fn)
    # 尾部 40 字符（转义后）必须完整出现
    tail = html.escape(p)[-40:]
    if tail and tail not in ht:
        tail_missing.append(fn)
print(f"[2.6] prompt 全文(转义后)缺失数 = {len(esc_missing)}")
print(f"[2.6] prompt 尾部40字符缺失数    = {len(tail_missing)}")
if esc_missing:
    print("       全文缺失:", esc_missing)
if tail_missing:
    print("       尾部缺失:", tail_missing)

# 2.7 data-writing 去重 == 27 连续 1-27
dw = re.findall(r'data-writing="(\d+)"', ht)
dw_unique = sorted(set(int(x) for x in dw))
print(f"[2.7] data-writing 去重值 = {dw_unique}")
print(f"       数量={len(dw_unique)} 连续1-27? {dw_unique == list(range(1,28))}")

# 2.8 分组数（group）
groups = re.findall(r'class="group" data-writing="(\d+)"', ht)
print(f"[2.8] 分组 group 数 = {len(groups)} (期望 27)")

# 2.9 三态开关组数（card 数）
cards = re.findall(r'class="card" data-file="([^"]+)"', ht)
print(f"[2.9] 预渲染 card 数 = {len(cards)} (期望 54)")

# 2.10 内联 ITEMS 长度（从 <script> 提取）
m = re.search(r'const ITEMS = (\[.*?\]);', ht, re.S)
items_len = None
if m:
    try:
        items = json.loads(m.group(1))
        items_len = len(items)
    except Exception as e:
        items_len = f"JSON解析失败: {e}"
print(f"[2.10] 内联 ITEMS 长度 = {items_len} (期望 54)")

# 2.11 相对路径是否为本地相对路径（非 http）
http_src = re.findall(r'<img[^>]*src="(https?://[^"]+)"', ht)
print(f"[2.11] <img> 用 http(s) 远程 src 数 = {len(http_src)} (期望 0, 全本地相对路径)")

# 2.12 文件名唯一性 / 写法号均匀性（从 card 与 csv）
from collections import Counter
c = Counter(csv_writing)
print(f"[2.12] 每写法号张数分布 = {dict(sorted(c.items(), key=lambda kv:int(kv[0])))}")
print(f"       是否全部为 2 张? {set(c.values()) == {2}}")

print("\n" + "=" * 70)
print("STEP 3: 抽样 3 条 prompt 完整全文核验（含最长那条）")
print("=" * 70)
# 选定样本：最长那条 + 2 条随机（固定种子可复现）
lengths = [ (i, len(p)) for i, p in enumerate(csv_prompts) ]
longest_i = max(lengths, key=lambda x: x[1])[0]
import random
random.seed(42)
others = random.sample([i for i in range(len(csv_prompts)) if i != longest_i], 2)
sample_idx = sorted([longest_i] + others)
print(f"样本索引(0基): {sample_idx}  => 文件名: {[csv_files[i] for i in sample_idx]}")
print(f"各自 prompt 长度: {[len(csv_prompts[i]) for i in sample_idx]}")
for i in sample_idx:
    fn = csv_files[i]
    p = csv_prompts[i]
    pe = html.escape(p)
    in_html = pe in ht
    tail = pe[-40:]
    tail_in = tail in ht
    print(f"\n  样本 file={fn}")
    print(f"    prompt 长度 = {len(p)}")
    print(f"    完整全文(转义)在HTML? {in_html}")
    print(f"    尾部40字符 = {tail!r}")
    print(f"    尾部40字符在HTML? {tail_in}")
    if not in_html:
        print(f"    [!] 全文未命中，可能截断/缺失")

print("\n" + "=" * 70)
print("STEP 4: 汇总判定")
print("=" * 70)
checks = {
    "img_total==56": img_total == 56,
    "thumb==54": thumb == 54,
    "ref_img==2": ref_img == 2,
    "base64==0": b64 == 0,
    "csv行数==54": len(rows) == 54,
    "文件名0缺失": len(missing) == 0,
    "prompt全文0缺失": len(esc_missing) == 0,
    "prompt尾部0缺失": len(tail_missing) == 0,
    "data-writing连续1-27": dw_unique == list(range(1,28)),
    "group==27": len(groups) == 27,
    "card==54": len(cards) == 54,
    "ITEMS==54": items_len == 54,
    "img本地相对路径(0 http)": len(http_src) == 0,
    "每写法号均2张": set(c.values()) == {2},
}
all_pass = all(checks.values())
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
print("\n全部结构核验通过?", all_pass)
print("研发脚本 EXIT==0 且 全 PASS?", (r.returncode == 0 and fail_n == 0))
