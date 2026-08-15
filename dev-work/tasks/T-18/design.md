# design · T-18 batch 面板外网图片修复 + 每写法号「两张图生成参数对比」行

> 模板来源：`dev-work/templates/TEMPLATE_DESIGN.md`。**开发填写**，推「待验证」时一并交付。
> 铁律：无输出 = 未测 = 不通过。以下每节均为真实内容。

---

## 一、实现方案

- **根因**：面板 `<img src>` 原用中文目录 URL（`/batch/01_配方训练/实验批次/batch-001/out/wNN_R.png`），外网隧道/代理层对百分号编码的中文路径拒载或转坏 → 页面能开、图裂。
- **修复思路**：新增纯 ASCII 资产路由 `/batch/__asset__/<kind>/<name>`，由代理 `agnes_proxy.py` 直接托管磁盘 PNG，彻底绕过中文目录 URL。生成器 `build_training_panel.py` 把所有 `<img src>` 与内联索引 `rel_path` 改为 ASCII URL（`cand_url`/`ref_url`）。HTML 为单源真理，**禁手改**，仅改生成器后重生成。
- **文本增强**：每写法号 `writing-purpose` 块「合并建议」后追加「两张图生成参数对比」行（`wp-cmp`）。事实（`run_batch001.py`）：同写法号两张图 `image_to_image(prompt, REF, size="2K", ratio="9:16")` 调用完全相同，prompt/参考图/尺寸/比例/负向词全同，唯一差别是模型随机种子（未显式传入）→ 诚实结论=无区别。
- **与现有逻辑兼容**：`do_GET` 的 `/batch` 分支先判 `__asset__` 子路由，否则仍走原 `_serve_batch`，零回归；生成器改动仅替换 URL 字符串与追加文本，不动 `main()` 调用约定、不动生成逻辑/鉴权/VIP。

---

## 二、接口契约（函数/模块改动）

### 2.1 agnes_proxy.py 新增方法

| 项 | 说明 |
|---|---|
| 函数签名 | `def _serve_batch_asset(self, path: str) -> None` |
| 输入字段 | `path`：原始请求路径，形如 `/batch/__asset__/cand/w01_1.png` 或 `/batch/__asset__/ref/charA_front.png` |
| 输出字段 | HTTP 响应：200 image/png（命中）/ 403（非法 kind 或路径穿越）/ 404（文件不存在）/ 403（非 .png）/ 500（读盘异常） |
| 下游消费方 | batch 训练面板 HTML 中的 `<img src>` 与 JS lightbox（经 `/batch/__asset__/cand|ref/<name>` 取图） |
| 路由装配 | `do_GET` 中 `if path.startswith("/batch"):` 内：`if path.startswith("/batch/__asset__/"): self._serve_batch_asset(path)` |

### 2.2 build_training_panel.py 新增常量/辅助

| 项 | 说明 |
|---|---|
| 常量 | `ASSET_BASE = "/batch/__asset__"` |
| 辅助函数 | `cand_url(file) -> f"{ASSET_BASE}/cand/{file}"`；`ref_url(file) -> f"{ASSET_BASE}/ref/{file}"` |
| 渲染点 | `render_card` 本地 `rel_path = cand_url(item["file"])`；`ref_cards` img `src=ref_url(r["file"])`；内联 `ITEMS_JSON` `rel_path = cand_url(it["file"])`；`collect_reference_images` `rel_path = ref_url(name)` |
| 文本块 | `WP_CMP_HTML`：每个写法号 writing-purpose 块 wp-merge 后插入的「两张图生成参数对比」div |

> 注：候选 `item["rel_path"]` 原始中文相对路径字段**保留不变**（供 self_check 本地文件可解析性校验使用），仅渲染侧与内联索引改用 ASCII URL，二者来源分离、互不干扰。

---

## 三、自测证据（铁律：无输出 = 未测 = 不通过）

### 3.1 改动文件清单（git diff）

**A. agnes_proxy.py（WorkBuddy/workbuddy 仓；改前已 `git commit before:` → `5038825` 之前；改后 commit `5038825`）**

```diff
@@ -364,7 +364,10 @@ class H(BaseHTTPRequestHandler):
             self._serve_html(SOUNDSFREE_FILE)
             return
         if path.startswith("/batch"):
-            self._serve_batch(path)
+            if path.startswith("/batch/__asset__/"):
+                self._serve_batch_asset(path)   # T-18: 纯 ASCII 资产路由
+            else:
+                self._serve_batch(path)
             return
@@ -699,6 +702,46 @@ class H(BaseHTTPRequestHandler):
         except Exception as e:
             self._send(500, json.dumps({"error": str(e)}))
 
+    def _serve_batch_asset(self, path):
+        """T-18: 纯 ASCII 静态资产路由, 绕过中文目录 URL 被外网隧道/代理层拒载."""
+        rel = path[len("/batch/__asset__/"):]
+        if "/" not in rel:
+            self._send(403, json.dumps({"error": "forbidden"})); return
+        kind, rest = rel.split("/", 1)
+        name = os.path.basename(rest)  # 拒绝含 / 或 .. 的穿越字符
+        if name != rest or ".." in rest or "/" in rest:
+            self._send(403, json.dumps({"error": "forbidden"})); return
+        if kind not in ("cand", "ref"):
+            self._send(403, json.dumps({"error": "forbidden"})); return
+        if kind == "cand":
+            full = os.path.normpath(os.path.join(
+                BATCH_PANEL_DIR, "01_配方训练", "实验批次", "batch-001", "out", name))
+        else:
+            full = os.path.normpath(os.path.join(
+                BATCH_PANEL_DIR, "01_配方训练", "角色参考图", name))
+        if not os.path.isfile(full):
+            self._send(404, json.dumps({"error": "not found: " + rel})); return
+        if os.path.splitext(full)[1].lower() != ".png":
+            self._send(403, json.dumps({"error": "forbidden"})); return
+        with open(full, "rb") as f:
+            data = f.read()
+        self._send(200, data, "image/png")
```

**B. build_training_panel.py（训练项目无 git 跟踪，列关键改动点）**

```python
# 新增常量/辅助（ZH_ANCHOR 之后）
ASSET_BASE: str = "/batch/__asset__"
def cand_url(file: str) -> str: return f"{ASSET_BASE}/cand/{file}"
def ref_url(file: str) -> str:  return f"{ASSET_BASE}/ref/{file}"
WP_CMP_HTML: str = ('<div class="wp-cmp">两张图生成参数对比：无区别'
    '（prompt / 参考图 / size=2K / ratio=9:16 / 负向词 NEG 全部相同，'
    '仅模型随机种子不同，未显式传入）</div>')

# collect_reference_images: rel_path -> ref_url(name)
{"file": name, "rel_path": ref_url(name)}

# render_card: 本地 rel_path 改 ASCII
rel_path = cand_url(item["file"])  # 候选图走纯 ASCII 资产路由

# render_groups writing-purpose 两分支: wp-merge 后插入 WP_CMP_HTML
f'<div class="wp-merge">合并建议：{html.escape(wp_merge)}</div>'
+ WP_CMP_HTML
+ f"</div>"
# (另一分支 wp-merge=（暂无测试目的记录）同理)

# 内联 ITEMS_JSON: rel_path 改 ASCII (供 lightbox / 导出)
"rel_path": cand_url(it["file"]),

# ref_cards: img src 改 ASCII
f'src="{ref_url(r["file"])}" '

# HTML_HEAD <style> 新增 .wp-cmp 样式 (浅色卡片, 与 wp-merge 区分)

# self_check 末尾增量断言
wp_cmp = html_text.count('class="wp-cmp"')
assert wp_cmp == group_count
zh_dir = html_text.count("01_配方训练")
assert zh_dir == 0   # img src / 索引 / refs 均已改 ASCII
```

### 3.2 本机跑测试的真实命令 + stdout

**命令**：`cd C:\Users\67972\projects\short-drama-training && python build_training_panel.py`

**self_check 关键数字（9 项铁律 + wp-cmp + 中文目录）**：

```
  内联索引 ITEMS 长度           = 54
  磁盘 PNG 实际数量             = 54
  缩略图 img.thumb[data-role]   = 54  (期望 54)
  参考图 class=ref-img          = 2   (期望 2)
  HTML <img 标签总数            = 56  (期望 56)   ★铁律
  base64 内嵌图片出现次数       = 0   (必须为 0)  ★铁律
  唯一 wXX_Y.png 文件名         = 54  (期望 54)   ★铁律
  中文锚点「同一个齐肩黑发」出现 = 54  (期望 54)  ★铁律
  data-writing 去重             = 27  (期望 27)   ★铁律
  每写法号目的块 writing-purpose = 27  (期望 27)  ★铁律
  两张图参数对比 wp-cmp          = 27  (期望 27)  ★新增
  中文目录字眼 01_配方训练        = 0   (必须为 0) ★新增 (img src 已改 ASCII)
[自检] 全部通过 ✔
```

> `data-role="thumb"`=54 与 `tag级 data-role="thumb"`=54 同源（缩略图 img.thumb[data-role] 计数=54）；`唯一 wXX_Y.png`=54；`base64`=0；「同一个齐肩黑发」=54；`data-writing` 去重=27；`writing-purpose`=27。9 项铁律全部守住。

**生成后 HTML 复核（额外 Python 校验）**：

```
cand src count (/batch/__asset__/cand/): 108   # 54 <img src> + 54 内联索引 rel_path
ref  src count (/batch/__asset__/ref/):   4     # 2  <img src> + 2  REFS_JSON
old chinese src count (01_配方训练): 0
img tag total: 56
base64 count: 0
wp-cmp count: 27
example cand src: /batch/__asset__/cand/w01_1.png
example ref  src: /batch/__asset__/ref/charA_front.png
「同一个齐肩黑发」出现: 54 (仅出现在中文 prompt, 新增块未写入该 6 字)
```

### 3.3 关键运行日志

- 代理隔离实例启动日志 `8799_t18.log`：`AGNES 短剧工作站 · 统一门户 http://localhost:8799` 正常监听。
- 验证脚本 `t18_verify_8799.py` stdout 见 3.4/四。

### 3.4 可真跑的启动 / 调用命令

```bash
# 1) 重生成 HTML（单源真理）
cd C:\Users\67972\projects\short-drama-training && python build_training_panel.py

# 2) 隔离实例 8799 验证（绝不碰线上 8787）
cd C:\Users\67972\WorkBuddy\workbuddy
AGNES_PROXY_PORT=8799 python -u agnes_proxy.py > 8799_t18.log 2>&1 &
# 另开终端跑验证脚本
python t18_verify_8799.py
# 结束杀掉隔离实例
taskkill /F /PID <8799的PID>
```

---

## 四、提测说明（测试怎么接）

- **测试入口**：隔离实例启动后，跑 `C:\Users\67972\WorkBuddy\workbuddy\t18_verify_8799.py`（urllib 全量校验）；或人工浏览器访问 `http://<外网隧道>/batch` 确认图不裂 + 每写法号见「两张图生成参数对比」行。
- **待测范围（对应 AC）**：
  - AC-1.1 新路由返回 PNG / 穿越 403 → 已由 8799 脚本 ①②③④ 覆盖。
  - AC-1.2 54 候选 + 2 参考走 ASCII；中文目录在 src 计数 0 → self_check + 3.2 复核覆盖。
  - AC-1.3 lightbox 候选/参考大图走 ASCII → 内联 `rel_path` 与 ref img src 均改 ASCII（3.2 已验证 URL 形态）。
  - AC-1.4 每写法号 wp-cmp=27 → self_check 覆盖。
  - AC-1.5 铁律 9 项不变 → self_check 覆盖。
  - AC-1.6 新增块无 `<img`/base64/「同一个齐肩黑发」→ 已核验（wp-cmp 纯文本 div；3.2 计数佐证）。
  - AC-1.7 隔离 8799 全量 + 线上 8787 复验 → 开发侧 8799 已全绿；**线上 8787 复验由测试/主理人独立执行**（开发未动 8787）。
  - AC-1.8 代理改前 `git commit before:` → 已执行（commit 见 3.1）。
- **已知限制 / 非阻塞**：
  - 外网隧道层具体拒载现象需在真实隧道环境由 QA 复验（本地 127.0.0.1 无法复现隧道编码问题，但 ASCII 路由已从根因上规避）。
  - 上线切换由主理人操作（重启/重载 8787 代理），开发只交付代码与待验证状态。

---

## 五、文档回写

- [x] `design.md` 已填（本文件）
- [x] 任务卡 AC 进度由主理人更新到 `current_state.md`（开发无 done 权）
- [ ] 其他四文档更新：PRD/test/acceptance 由测试/主理人补（开发止步「待验证」）
