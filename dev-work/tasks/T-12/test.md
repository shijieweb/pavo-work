# test · T-12 8787 门户补齐两个缺失入口（音效台 + 看板 API 说明）

> 模板来源：`dev-work/templates/TEMPLATE_TEST.md`。**测试填写**，推「已验证」时一并交付。
> 铁律：独立验证亲自跑（非研发自报）；无 P0/P1；每条结论附证据。测试**不修 bug**。
> 本文件所有命令均为 QA 于 2026-08-14 独立实跑，原始 stdout 直贴，未采信研发 design.md 结论。

---

## 一、测试用例 + 覆盖矩阵

| 用例ID | 对应 AC | 输入/动作 | 预期 | 实际 | 结果 | 证据 |
|---|---|---|---|---|---|---|
| TC-1 | AC-1.1 | curl `/soundsfree`、`/soundsfree.html`；校验 body 含 SoundsFree、`<title>` 含 SoundsFree、字节数=磁盘 | 均 200；真页面非兜底 | 200/200；title=SoundsFree…；bytes 34986=磁盘 | PASS | §三 3.1 |
| TC-2 | AC-1.2 | curl 8787/ 校验 `href="/soundsfree"` + 音效文案 + 卡片总数=7 | 卡片可点、总数 7 | href 存在；音效×4；cards=7 | PASS | §三 3.2 |
| TC-3 | AC-1.3 | curl 8787/ 校验 `href="/board/docs"` + `/board/docs` 200 + 看板 API 说明页 | 卡片可点、页可达 | href 存在；200；看板 API 说明页×2 | PASS | §三 3.3 |
| TC-4 | AC-1.4 | 6 入口全 200；`/board/api/projects/19/milestones` 7 阶段；`/api/spec` 非 5xx；portal/direct docs 对比 | 全活、board/studio 反代完好、docs 未被篡改 | 全 200；7 阶段 JSON；/api/spec=200；docs diff=0 | PASS | §三 3.4 |
| TC-5 | AC-1.5 | git diff d1a4b99 边界：仅 2 文件、禁改区空、无生成链路 | 仅 agnes_proxy.py+hub.html | name-only=2 文件；禁改区空；gen_video 等=0 | PASS | §三 3.5 |
| TC-6 | AC-1.6 | netstat 8787/8788/8777 监听唯一性 | 各仅 1 监听 | 8787=24436(1)；8788=32924(1)；8777=29296(1) | PASS | §三 3.6 |
| TC-7 | AC-1.7 | 本文件每条 TC 均附可重跑命令+原始 stdout | 无输出=未测=不通过 不成立 | 全 TC 有命令+stdout | PASS | 全文 |
| TC-8 | AC-1.2 补强 | hub.html JS 无新卡片探活依赖；node --check 语法 | 无 `$("cardSoundsfree"/"cardDocs")`；语法 OK | 仅 cardStudio/cardBoard；SYNTAX_OK | PASS | §三 3.7 |

> 覆盖矩阵：PRD AC-1.1~1.7 全部覆盖（TC-1~TC-7）；另加前端体检 TC-8。无遗漏 AC。

---

## 二、L1 真·管线冒烟（触及生成逻辑必做，用免费 KEY）

- **是否触发 L1**：否。
- 说明：本任务仅新增静态路由 + 门户卡片（F1~F4），不触及 `gen_video`/`build_variants`/关键帧/`data_uri`/`negative`/`seed` 等生成逻辑（AC-1.5 已证零生成链路改动）。依据主理人守则 G0-4 + PRD §3「L0 层即可、无需 L1 真测」，且禁调任何 AGNES 接口（零额度 L0 层）。无需 L1 真测，禁烧 VIP。

---

## 三、重跑研发回归（不盲信研发输出）

以下均为 QA 独立实跑，命令 + 原始 stdout 直贴。

### 3.1 TC-1 / AC-1.1 音效台路由通（真页面核验）
```
$ curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8787/soundsfree
200
$ curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8787/soundsfree.html
200
$ curl -s http://127.0.0.1:8787/soundsfree | grep -c SoundsFree
1
$ curl -s http://127.0.0.1:8787/soundsfree | grep -o '<title>[^<]*</title>'
<title>SoundsFree - 免费程序化音效生成器 | AI音效制作工具</title>
$ curl -s http://127.0.0.1:8787/soundsfree | wc -c
34986
$ wc -c soundsfree_home.html
34986 soundsfree_home.html
```
**断言**：`/soundsfree` 与 `/soundsfree.html` 均 200；body 含 `SoundsFree`；`<title>` 含「SoundsFree」；返回字节数 **34986 与磁盘 `soundsfree_home.html` 完全一致** → 命中真页面，非兜底页。**PASS**。

### 3.2 TC-2 / AC-1.2 音效台卡片可点
```
$ curl -s http://127.0.0.1:8787/ | grep -o 'href="/soundsfree"'
href="/soundsfree"
$ curl -s http://127.0.0.1:8787/ | grep -c "音效"
4
$ curl -s http://127.0.0.1:8787/ | grep -o 'class="card' | wc -l
7
```
**断言**：首页含 `href="/soundsfree"` 卡片、文案含「音效」；卡片总数 = **7**（基线 5 + 新增 2）。**PASS**。

### 3.3 TC-3 / AC-1.3 看板 API 说明卡片可点
```
$ curl -s http://127.0.0.1:8787/ | grep -o 'href="/board/docs"'
href="/board/docs"
$ curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8787/board/docs
200
$ curl -s http://127.0.0.1:8787/board/docs | grep -c "看板 API 说明页"
2
```
**断言**：首页含 `href="/board/docs"` 卡片；`/board/docs` 返回 200 且 body 含「看板 API 说明页」。**PASS**。

### 3.4 TC-4 / AC-1.4 零回归（含深度回归）
```
$ for p in / /console /studio /board /logs /training; do
>   echo "$p -> $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8787$p)"; done
/ -> 200
/console -> 200
/studio -> 200
/board -> 200
/logs -> 200
/training -> 200

$ curl -s http://127.0.0.1:8787/board/api/projects/19/milestones | head -c 1500
{"project_id": 19, "stages": [{"id": 1, "stage_key": "topic", "stage_name": "选题", "stage_order": 1, ...}, {"id": 2, "stage_key": "script", "stage_name": "剧本", ...}, {"id": 3, "stage_key": "storyboard", "stage_name": "分镜", ...}, {"id": 4, "stage_key": "generate", "stage_name": "生成", ...}, {"id": 5, "stage_key": "dubbing", "stage_name": "配音", ...}, {"id": 6, "stage_key": "edit", "stage_name": "剪辑", ...}, {"id": 7, "stage_key": "publish", "stage_name": "发布", ...}], "overall": {"total": 12, "done": 10, "rate": 83}}

$ curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8787/api/spec
200

$ curl -s http://127.0.0.1:8787/board/docs > /tmp/portal_docs.html
$ curl -s http://127.0.0.1:8788/docs > /tmp/direct_docs.html
$ echo "portal=$(wc -c < /tmp/portal_docs.html) direct=$(wc -c < /tmp/direct_docs.html)"
portal=9051 direct=9051
$ echo "portal /board/api/=$(grep -c '/board/api/' /tmp/portal_docs.html) direct=$(grep -c '/board/api/' /tmp/direct_docs.html)"
portal /board/api/=9 direct=9
$ echo "portal /api/=$(grep -c '/api/' /tmp/portal_docs.html) direct=$(grep -c '/api/' /tmp/direct_docs.html)"
portal /api/=19 direct=19
$ diff /tmp/portal_docs.html /tmp/direct_docs.html | wc -l
0
```
**断言**：
- 6 入口全 200 → 零回归 **PASS**。
- `/board` 反代完好：`/board/api/projects/19/milestones` 返回 **7 阶段里程碑 JSON**（选题/剧本/分镜/生成/配音/剪辑/发布），证明 board 反代及其 `/api/`→`/board/api/` 重写逻辑未破坏（T-11 功能可用）。
- `/studio` 反代完好：`/api/spec` → 200（非 5xx）。
- **PRD §3 风险点核验**：对比 `8787/board/docs` 与 `8788/docs`，字节数相同（9051）、`/board/api/` 与 `/api/` 计数完全一致、`diff` 行数 = **0** → 门户版 docs 页面文本与直连版**逐字节一致**，**未被 board 反代的 `/api/`→`/board/api/` 重写篡改**，老板阅读无碍。此项为 **OBS 观察**（非 FAIL）。

### 3.5 TC-5 / AC-1.5 边界零越界
```
$ git --no-pager diff d1a4b99^ d1a4b99 --name-only
agnes_proxy.py
hub.html
$ git --no-pager show --stat --oneline d1a4b99
d1a4b99 feat(T-12): 8787门户新增 /soundsfree 路由与 音效台/看板API说明 两入口卡片
 agnes_proxy.py |  5 +++++
 hub.html       | 20 ++++++++++++++++++++
 2 files changed, 25 insertions(+)
$ git --no-pager diff d1a4b99^ d1a4b99 -- route_registry.json shared_board short_drama_workflow
(空输出，exit=0)
$ git --no-pager diff d1a4b99^ d1a4b99 | grep -Ec "gen_video|build_variants|关键帧|data_uri"
0
```
**断言**：源变更仅 `agnes_proxy.py` + `hub.html`（commit `d1a4b99`）；`route_registry.json` / `shared_board/**` / `short_drama_workflow/**` 零改动；无 `gen_video`/`build_variants`/关键帧/`data_uri` 相关改动。**PASS**。

### 3.6 TC-6 / AC-1.6 服务存活与唯一性
```
$ netstat -ano | grep -i ":8787" | grep LISTENING
  TCP    0.0.0.0:8787           0.0.0.0:0              LISTENING       24436
$ netstat -ano | grep -i ":8788" | grep LISTENING
  TCP    0.0.0.0:8788           0.0.0.0:0              LISTENING       32924
$ netstat -ano | grep -i ":8777" | grep LISTENING
  TCP    127.0.0.1:8777         0.0.0.0:0              LISTENING       29296
```
**断言**：8787 仅 **1 个**监听（PID 24436），无遗留旧进程（对比 design.md 所述曾出现的 31328/29144 双监听已清理干净）；8788（32924）、8777（29296）仍在监听、未被误杀。**PASS**。
> 注：本任务环境铁律「禁止杀任何进程、仅只读验证」，故 QA 不重复重启，仅对现网存活态做只读核验。现网已达「单监听 + 8788/8777 存活」的合规终态。

### 3.7 TC-8 / 前端体检（AC-1.2 补强）
```
$ grep -n "cardSoundsfree\|cardDocs" hub.html
214:  <a class="card" id="cardSoundsfree" href="/soundsfree"
224:  <a class="card" id="cardDocs" href="/board/docs"
$ grep -n '\$("card' hub.html
341:  const c = $("cardStudio");
357:  const c = $("cardBoard");
479:$("cardBoard").addEventListener("click", (e) => {
$ grep -c '<script' hub.html
1
$ python -c "import re; h=open('hub.html',encoding='utf-8').read(); b=re.findall(r'<script[^>]*>(.*?)</script>', h, re.S); open('/tmp/hub_script.js','w',encoding='utf-8').write('\n;\n'.join(b)); print(len(b), sum(len(x) for x in b))"
1 7756
$ "/c/Users/67972/.workbuddy/binaries/node/versions/22.22.2/node.exe" --check /tmp/hub_script.js && echo SYNTAX_OK
SYNTAX_OK
```
**断言**：新卡片 `cardSoundsfree` / `cardDocs` 仅以 HTML 元素 id 形式存在；JS 中**无任何** `$("cardSoundsfree")` / `$("cardDocs")` 取值（仅既有 `cardStudio`/`cardBoard` 有 JS 探活），故新卡片不引入 JS 探活依赖、不会因取不到元素报错；内联 script 经 `node --check` 语法通过。**PASS**。

---

## 四、缺陷清单（[BUG] 格式，仅报告不改）

无。TC-1~TC-8 全部 PASS，未触发 L1，无生成链路改动，无回归，无越界。当前未发现任何缺陷，故不提单（依 TEMPLATE_BUG 规则，有缺陷才提单）。

---

## 五、整体结论

- [x] 建议阿编放行（QA 已验证，无阻塞项；**最终放行权归主理人**）
- 覆盖矩阵：AC-1.1~1.7 全部 PASS（TC-1~TC-7）；另加前端体检 TC-8 PASS。
- P0/P1：无。
- 观察项（OBS，非阻塞）：
  1. PRD §3 警示的「`/board/docs` 文本被 `/api/`→`/board/api/` 重写篡改」风险经实测**未出现**：门户版与直连版 docs 逐字节一致（diff=0）。属如实观察，不影响放行。
- 证据存档：本文件 §三 全量命令 + 原始 stdout；源 commit `d1a4b99`；网络监听态 `netstat`（§3.6）。
