# test · T-11 看板里程碑阶段门禁体系

> 模板来源：`dev-work/templates/TEMPLATE_TEST.md`。**QA（Edward / software-qa-engineer-4）独立填写**，推「已验证」时一并交付。
> 铁律：独立验证亲自跑（非研发自报）；无 P0/P1；每条结论附证据。测试**不修 bug**。
> 验证时间：2026-08-14。验证方式：脱离工程师文字，全程实跑接口 / 迁移 / 聚合 / UI；双入口 + 隔离端口 8801 + 隔离旧库 8802 均独立拉起验证。

---

## 一、测试用例 + 覆盖矩阵

| 用例ID | 对应 AC | 输入/动作 | 预期 | 实际 | 结果 | 证据 |
|---|---|---|---|---|---|---|
| TC-1 | AC-1.1 | 隔离 8801 + 隔离 DB 创建项目 → GET milestones 两次 | 自动插入 7 阶段；二次不重复 | 7 阶段全 pending；两次 ids 一致 [1..7] | PASS | §三.1 |
| TC-2 | AC-1.2 | GET /api/projects/19/milestones（8788 直连 + 8787 网关） | 7 阶段含 total/done/rate | 7 阶段 + overall 字段齐全 | PASS | §三.2 / §三.3 |
| TC-3 | AC-1.3 | POST/PUT 任务带 milestone_id；前端抽屉下拉 + 卡片徽章 | 可挂接；7+无；卡片显徽章 | 后端接受+改挂 OK；前端代码含 d_milestone/stage-badge | PASS | §三.1 / §三.4 |
| TC-4 | AC-1.4 | 阶段内有部分完成任务 | 阶段显 完成数/总数 + 整体率 | topic 2/1/50；overall 3/1/33 | PASS | §三.1 |
| TC-5 | AC-1.5 | 从 8788 GET / 拉 index.html 并 grep | 含里程碑面板代码 | 9/9 面板标记命中 | PASS | §三.4 |
| TC-6 | AC-1.6 | 旧库（无 milestone_id 列 + 无 milestones 表）启动服务，再重启 | 迁移幂等不报错；旧任务不丢 | 列加回、表建、20 任务完好；重启无报错 | PASS | §三.5 |

> 覆盖矩阵 100% 覆盖 PRD 的 AC-1.1~1.7。AC-1.7（证据铁律）本身由本文件每条 TC 的「实跑命令 + 原始输出」满足。

---

## 二、L1 真·管线冒烟（触及生成逻辑必做，用免费KEY）

- **是否触发 L1**：**否**（本任务纯看板后端/前端改动，不触及 `gen_video`/关键帧/`data_uri` 等生成逻辑；见 §六 红线扫描）。

---

## 三、重跑研发回归（不盲信研发输出，独立实跑命令 + 原始输出）

### 三.1 AC-1.1 自动初始化幂等 + AC-1.3 任务挂接 + AC-1.4 聚合（隔离端口 8801 + 隔离 DB）

**启动隔离实例（绝不碰线上 board.db）：**
```
cd /c/Users/67972/WorkBuddy/workbuddy/shared_board
BOARD_DB="C:/Users/67972/AppData/Local/Temp/t11qa/t11_qa.db" \
BOARD_PORT=8801 BOARD_TOKEN=t11qa BOARD_INJECT_TOKEN=0 \
nohup python server.py > .../t11qa/qa.log 2>&1 & disown
# -> 启动日志：【board】BOARD_TOKEN=t11qa；连通性 GET /api/projects HTTP 200
```

**AC-1.1 创建项目（应自动初始化 7 阶段）：**
```
RAW POST /api/projects -> {"id": 1, "owner": "老板"}
```
**AC-1.1 首次 GET milestones（应 7 阶段全 pending, total/done=0）：**
```
RAW GET #1 -> {"project_id": 1, "stages": [
 {"id":1,"stage_key":"topic","stage_name":"选题","stage_order":1,"status":"pending","total":0,"done":0,"rate":0},
 {"id":2,"stage_key":"script","stage_name":"剧本","stage_order":2,"status":"pending","total":0,"done":0,"rate":0},
 {"id":3,"stage_key":"storyboard","stage_name":"分镜","stage_order":3,"status":"pending","total":0,"done":0,"rate":0},
 {"id":4,"stage_key":"generate","stage_name":"生成","stage_order":4,"status":"pending","total":0,"done":0,"rate":0},
 {"id":5,"stage_key":"dubbing","stage_name":"配音","stage_order":5,"status":"pending","total":0,"done":0,"rate":0},
 {"id":6,"stage_key":"edit","stage_name":"剪辑","stage_order":6,"status":"pending","total":0,"done":0,"rate":0},
 {"id":7,"stage_key":"publish","stage_name":"发布","stage_order":7,"status":"pending","total":0,"done":0,"rate":0}
], "overall": {"total": 0, "done": 0, "rate": 0}}
```
**AC-1.1 二次 GET milestones（幂等：ids 应一致）：**
```
RAW GET #2 -> 与 GET #1 字节相同（stages id 列表 [1,2,3,4,5,6,7]，仍是 7 条）
```

**AC-1.3 POST 任务（topic 阶段挂 2 个 + 1 个无阶段）：**
```
RAW taskA -> {"id": 1}    (milestone_id=1, status=完成)
RAW taskB -> {"id": 2}    (milestone_id=1, status=待办)
RAW taskC -> {"id": 3}    (milestone_id=null, status=进行中)
```
**AC-1.3 PUT 任务改挂阶段（C → generate=id4）：**
```
RAW PUT taskC milestone -> {"ok": true}
```
**AC-1.2 PUT 阶段 status + 非法 status 校验：**
```
RAW PUT /api/milestones/1 active -> {"ok": true}
RAW PUT illegal status -> HTTP 400  (期望 400)
```
**AC-1.4 最终 GET milestones（聚合校验）：**
```
RAW FINAL -> {"project_id": 1, "stages": [
 {"id":1,"stage_key":"topic","stage_name":"选题","stage_order":1,"status":"active","total":2,"done":1,"rate":50},
 {"id":2,"stage_key":"script","stage_name":"剧本","stage_order":2,"status":"pending","total":0,"done":0,"rate":0},
 {"id":3,"stage_key":"storyboard",...,"status":"pending","total":0,"done":0,"rate":0},
 {"id":4,"stage_key":"generate","stage_name":"生成","stage_order":4,"status":"pending","total":1,"done":0,"rate":0},
 {"id":5,"stage_key":"dubbing",...,"total":0,"done":0,"rate":0},
 {"id":6,"stage_key":"edit",...,"total":0,"done":0,"rate":0},
 {"id":7,"stage_key":"publish",...,"total":0,"done":0,"rate":0}
], "overall": {"total": 3, "done": 1, "rate": 33}}
```

**结构化断言结果（独立校验，不盲信）：**
```
AC-1.1 PASS ✅  7 阶段全 pending + 幂等(ids 一致): [1, 2, 3, 4, 5, 6, 7]
AC-1.2 PASS ✅  每阶段含 total/done/rate 字段
AC-1.4 PASS ✅  topic total=2/done=1/rate=50；generate total=1/done=0；overall total=3/done=1/rate=33
AC-1.2 PUT status PASS ✅  stage1 status=active 已生效
AC-1.2 非法 status PASS ✅  HTTP 400
ALL AC-1.1/1.2/1.3/1.4 断言通过 ✅
```

### 三.2 AC-1.2 / AC-1.7 双入口一致性（project 19：8788 直连 vs 8787 /board 网关）

```
curl -s http://127.0.0.1:8788/api/projects/19/milestones
curl -s http://127.0.0.1:8787/board/api/projects/19/milestones
```
**两端原始响应（节选，完全相同）：**
```
{"project_id": 19, "stages": [
 {"id":1,"stage_key":"topic","stage_name":"选题","stage_order":1,"status":"pending","total":0,"done":0,"rate":0},
 ...(7 阶段，stage_order 1..7，全部 pending)...
 {"id":7,"stage_key":"publish","stage_name":"发布","stage_order":7,"status":"pending","total":0,"done":0,"rate":0}
], "overall": {"total": 12, "done": 10, "rate": 83}}
```
**结构化比对：**
```
DIFF_RESULT: IDENTICAL ✅
stages_count_8788= 7   stages_count_8787= 7
```
> 结论：新接口在 8788 直连与 8787 `/board` 网关两入口返回**字节完全一致**（7 阶段 + overall {total:12, done:10, rate:83}）。AC-1.7 证据铁律满足：QA 独立实跑，非采信研发文字。

### 三.3 AC-1.2 里程碑数据接口字段完整性（另见 §三.1 PUT 校验）
- GET 每阶段含 `id/stage_key/stage_name/stage_order/status/total/done/rate` 全部字段（断言逐字段校验通过）。
- 顶层 `overall:{total,done,rate}` 正确。

### 三.4 AC-1.5 阶段视图 UI（从 8788 实时拉取 index.html 并 grep）

```
curl -s http://127.0.0.1:8788/ > .../t11qa/served_index.html   (字节数 48483)
```
**面板标记命中（9/9）：**
```
[✅] loadMilestones() 数据拉取
[✅] renderMilestones() 渲染
[✅] 里程碑面板容器 milestonePanel
[✅] 阶段面板开关 btnMilestone
[✅] 抽屉阶段下拉 d_milestone
[✅] 卡片阶段徽章 stage-badge
[✅] 整体流水线完成率
[✅] ms-stage 流水线卡片样式
[✅] ms-prog 进度条样式
AC-1.5 PASS ✅  8788 实时托管的 index.html 含完整里程碑面板代码
```
> 注：7 阶段文案（选题/剧本/分镜/生成/配音/剪辑/发布）为后端 `DEFAULT_STAGES` 常量，由 API 动态注入前端渲染，已在 AC-1.1/1.2 断言验证顺序与文案正确；故不在静态 HTML 中作字面 grep（属正常设计）。

### 三.5 AC-1.6 迁移安全幂等（旧库无 milestone_id 列 + 无 milestones 表）

**构造旧结构 DB（复制线上 board.db 后剥离，绝不改线上）：**
```
n_tasks=20  n_proj=3
tasks 列(剥离后，应无 milestone_id) = ['id','project_id','parent_id','title','detail','status','author','updated','priority','deadline','block_reason','progress']
表清单 = ['projects','sqlite_sequence','presence','audit','notes','tasks']   (无 milestones)
旧结构构造 OK（缺 milestone_id + 无 milestones 表）
```

**首次启动隔离服务（8802 → old.db）：**
```
BOARD_DB="C:/.../t11qa/old.db" BOARD_PORT=8802 BOARD_TOKEN=t11qa BOARD_INJECT_TOKEN=0 nohup python server.py ...
GET /api/projects/19/milestones -> HTTP 200
```
**迁移结果校验：**
```
迁移后表清单 = ['projects','sqlite_sequence','presence','audit','notes','tasks','milestones']   (milestones 已建)
tasks 列含 milestone_id = True -> [...,'milestone_id']   (列已加回)
tasks 总数(应=20, 未丢) = 20
milestones 表存在 = True  已初始化阶段数(ensure) = 7
milestone_id 为 NULL 的旧任务数 = 20   (旧任务不受影响)
GET /api/projects/19/milestones 返回阶段数 = 7
AC-1.6 首次迁移 PASS ✅  幂等 ALTER 安全执行 + 旧任务 0 丢失 + 表/列已建
```

**重复启动验证幂等（杀掉后再拉起，迁移二次执行不应报错）：**
```
二次启动后 milestones 阶段数 = 7
二次启动后 tasks 列含 milestone_id = True  任务总数 = 20  milestones 数 = 7
AC-1.6 重复启动幂等 PASS ✅  迁移二次执行无报错、旧数据完好、接口正常
```

---

## 四、缺陷清单（[BUG] 格式，仅报告不改）

> 本轮独立验证**未发现缺陷**。所有 AC 均 PASS，无阻断项。
> （如后续复验发现，按 `[BUG][S?|P?] 现象 (AC-x.y)` 格式追加，并附原始报错。）

---

## 五、整体结论

- [x] **建议阿编放行**（待主理人把关，QA 无「完成」权，仅推「已验证」）
- 覆盖矩阵：AC-1.1~1.7 **全部 PASS**（7/7）
- P0/P1：无
- 证据存档：本文件（每条 TC 含实跑命令 + 原始输出）+ 隔离日志 `C:/Users/67972/AppData/Local/Temp/t11qa/{qa.log, mig1.log, mig2.log, served_index.html, mig_m.json}`

---

## 六、代码边界核对（红线扫描，佐证 AC-1.6/PRD 边界）

```
git show --stat f321806:
  dev-work/tasks/T-11/design.md | 195 +++
  shared_board/index.html       |  76 +-
  shared_board/server.py        | 113 +-
  (仅 3 文件，无 agnes_proxy.py / route_registry.json)

grep agnes_proxy|route_registry  server.py index.html -> (无 ✅)
grep gen_video|build_variants|关键帧|data_uri  server.py index.html -> (无 ✅)
```
> 结论：本次改动仅 milestone 相关（milestones 表 / tasks.milestone_id / 里程碑接口 / 自动初始化 / 前端面板），未触碰生成链路红线。
