# T-18 design.md（开发填）

> 按 `dev-work/templates/TEMPLATE_DESIGN.md` 填。开发推「待验证」即停，无 done 权。

## 改动点（预期方案，开发核实后补全 git diff）

### A. agnes_proxy.py（新增 __asset__ 静态资产路由）
- 在 `do_GET` 第 366 行 `if path.startswith("/batch"):` 分支内，先判 `path.startswith("/batch/__asset__/")` → 调 `_serve_batch_asset(path)`，否则走原 `_serve_batch(path)`。
- 新增方法 `_serve_batch_asset(self, path)`：
  - 解析 `rel = path[len("/batch/__asset__/"):]`，按首个 `/` 拆 `kind` + `name`。
  - `kind` 仅允许 `cand` / `ref`，否则 403。
  - `name` 取 `os.path.basename`（防穿越；拒绝含 `/` `..`）。
  - `cand` → `BATCH_PANEL_DIR / "01_配方训练" / "实验批次" / "batch-001" / "out" / name`
  - `ref`  → `BATCH_PANEL_DIR / "01_配方训练" / "角色参考图" / name`
  - 文件不存在 → 404；存在 → 200 image/png（`.png` 扩展名白名单）。
- 此路由路径全 ASCII，**绕过中文目录 URL 被外网隧道层拒载**的问题。

### B. build_training_panel.py（img src 改 ASCII + 加参数对比行）
- 新增辅助：`ASSET_BASE = "/batch/__asset__"`；`cand_url(file) = f"{ASSET_BASE}/cand/{file}"`；`ref_url(file) = f"{ASSET_BASE}/ref/{file}"`。
- `render_card`（第 1205 行附近）：`rel_path = cand_url(item["file"])`（覆盖原中文相对路径）。
- `ref_cards`（第 1363-1372 行）：`src="{ref_url(r['file'])}"`。
- `render_groups` writing-purpose 块（第 1304-1318 行）：在 `wp-merge` 之后追加：
  ```
  f'<div class="wp-cmp">两张图生成参数对比：无区别（prompt / 参考图 / size=2K / ratio=9:16 / 负向词 NEG 全部相同，仅模型随机种子不同，未显式传入）</div>'
  ```
- `HTML_HEAD` 的 `<style>` 内追加 `.wp-cmp` 样式（浅色卡片、与 wp-merge 区分）。
- `self_check` 末尾增量断言：`wp-cmp` 计数 == group_count（27）；并复验 HTML 中 img src 含中文目录 `01_配方训练` 字眼 == 0。

### C. 重生成
- 命令：`cd C:\Users\67972\projects\short-drama-training && python build_training_panel.py`
- 单源真理，禁手改 HTML。

## 自测证据（开发填）
（贴 self_check 输出 + 8799 隔离实例验证 stdout）

## git diff（开发填）
（agnes_proxy.py 在 WorkBuddy/workbuddy 仓；改前 `git commit before:`）
