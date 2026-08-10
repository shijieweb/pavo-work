# 短剧动画自动化制作方案 · HTML 原型验证 + AGNES 贯通

> 目标：构建一套**可全自动化运行、同时支持人工介入修改预览**的短剧动画制作系统。
> 核心命题：前期用 HTML 把全流程原型跑通，后期用 AGNES-AI 生成真实动画，二者通过**同一份数据契约（SceneSpec）**打通。
> 适用：你已建好的 `short_drama_workflow/`（agnes_client、assemble、quality_check、ep01_storyboard.json）。本方案是**接在现有骨架上**，不是另起炉灶。

---

## 0. 设计核心：一个契约贯穿始终（串联机制的真相）

先想清楚一件事：为什么多数"AI 短剧工具"做着做着就散了？因为**剧本、分镜、生成、合成各用各的数据格式**，中间靠人手拷贝粘贴，一改就错位。

本方案的解法——**SceneSpec（场景规格）是唯一的真相源（Single Source of Truth）**：

- 它就是你已有的 `storyboard.json` 的 `shots` 数组 + 全局配置（`global_style` / `resolution` / `voice_roles` / `references` / `post`）。
- **浏览器（HTML 原型）读它、改它、预览它。**
- **AGNES 后端（Python）读它、按它生成、把产出 URL 写回它。**
- 任何一端的修改，另一端立刻可见 → 这就是"预览 → 修改 → 再预览 → 生成真实动画"的闭环。

```
        ┌─────────────── 浏览器 Storyboard Studio (HTML) ───────────────┐
        │  分镜时间线 │ 画面预览 │ 单镜参数编辑器 │ 质检报告 │ 分发面板   │
        └───────────────────────────┬───────────────────────────────────┘
                                     │  读写同一个 SceneSpec (JSON)
                                     ▼
        ┌─────────────── 后端 Orchestrator (Python) ───────────────────┐
        │  /api/spec  /api/generate/shot  /api/generate/voice           │
        │  /api/assemble  /api/quality                                    │
        │   调用: agnes_client.py · tts_*.py · assemble.py · qc.py        │
        └───────────────────────────┬───────────────────────────────────┘
                                     │
                 AGNES-AI 网关 · TTS · ffmpeg · SoundsFree
```

**一句话**：HTML 原型 = SceneSpec 的可视化编辑器 + 播放器；AGNES = SceneSpec 的执行器。二者只通过 JSON 对话。

---

## 1. 各阶段流程拆解（从剧本到最终动画）

| # | 阶段 | 输入 | 产出 | 用的工具 | HTML 原型里的角色 |
|---|---|---|---|---|---|
| 0 | **剧本** | 选题 brief | `script.json`（集纲/角色/爽点节奏） | agnes-2.0-flash | 剧本编辑面板（可改 beats） |
| 1 | **分镜 / SceneSpec** | script.json | `storyboard.json`（shots 数组） | 解析脚本 + 人工精修 | **Storyboard Studio 主场**：逐镜编辑、整集播放预览 |
| 2 | **参考图** | `references[].img_prompt` | 角色/场景参考 PNG + 可访问 URL | agnes-image-2.1-flash（固定 seed） | 参考图作为每镜"角色头像"，生成前为占位色块，生成后为真实图 |
| 3 | **AGNES 视频** | `shots[].video_prompt` + 参考图 URL | 每镜 5–18s 视频片段 | agnes-video-v2.0（图生视频/关键帧） | 每镜"生成真实画面"按钮 → 预览框换成真视频 |
| 4 | **配音** | `shots[].subtitle` + `voice` | 每镜音频 mp3 | gTTS/Edge（开发）→ MiniMax/Fish（量产） | 可先"听广播剧"（静帧+配音），后再混入真视频 |
| 5 | **合成** | 视频+配音+字幕+BGM+AI标 | `epNN.mp4` | ffmpeg（assemble.py）+ simhei.ttf | "合成成片"按钮 → 预览框播放最终 MP4 |
| 6 | **质检** | `epNN.mp4` | 质检报告 | quality_check.py | 每镜 pass/fail 徽章 + 报告面板 |
| 7 | **分发** | `epNN.mp4` | 三平台成片 | 开放 API / RPA（M3） | 分发面板（平台勾选 + 状态） |

> 阶段 1（分镜）是**省钱省时的核心**——在 HTML 里把叙事、节奏、景别、剪辑逻辑全部验证完，确认无误才花 AGNES token 出真画面。这正好对应你定的"30 秒样片迭代验证法"。

---

## 2. 阶段之间的衔接方式与数据流转

数据流的"脊柱"就是 SceneSpec。每个阶段只做两件事之一：**读它来决定自己要做什么**，**或写它来交还成果**。

```
brief ──▶ [0 剧本] ──▶ script.json
                       │
                       ▼
                 [1 分镜] ──▶ storyboard.json  ◀────────┐（人工在 Studio 改）
                       │                                │
          ┌────────────┼───────────────┐               │
          ▼            ▼               ▼                │
   [2 参考图]      [3 AGNES视频]    [4 配音]            │
   写回           写回 assets/video  写回 assets/audio   │
   references      /shotN.mp4        /shotN.mp3         │
          └────────────┼───────────────┘               │
                       ▼                                │
                 [5 合成] ──▶ epNN.mp4 ──▶ [6 质检] ──▶ [7 分发]
                       ▲                                │
                       └──────── Studio 拉取最新资产 URL 重渲染 ┘
```

**关键衔接规则（务必固化）：**

1. **资产 URL 写回 SceneSpec**：阶段 2/3/4 完成后，把 `asset_url` 写回对应 shot（`shot.asset_image` / `shot.asset_video` / `shot.asset_audio`）。Studio 检测到有 URL 就显示真素材，没有就显示占位。
2. **差异生成（diff）**：改了一镜，只重生成那一镜，不重跑全集 → 省钱、快迭代。后端按 `shot.id` 比对"是否已有有效资产 + 参数是否变化"决定跳过/重生成。
3. **时长权威在分镜**：沿用你已有的 `audio_gateway.core_rule = storyboard_shot_duration_unchangeable`——分镜时长不可被配音改变，配音只调自身（变速/拆句/补静音）。保证 HTML 预览时长 = 真实成片时长。
4. **字符一致性**：阶段 2 固定 seed 生成参考图；阶段 3 图生视频传参考图 URL + 关键帧绑定；`face_stability_rule` 自动追加到每个含人镜头。这条链在 HTML 里用"参考图占位→真图"可视化呈现。

---

## 3. 推荐开源组件、技术栈及工具

### 3.1 前端（HTML 原型 / 可视化界面）
| 需求 | 选型 | 理由 |
|---|---|---|
| 原型框架 | **原生 HTML/CSS/JS（零构建）** | 你明确要求"用 HTML 方式搭原型"；双击即开、零依赖、最稳 |
| 响应式状态 | 可选 Alpine.js（单文件 CDN）或自写极小响应式层 | 原型阶段不需要 React；后期可升 Vite+React |
| 时间线/播放器 | 自写 `requestAnimationFrame` 时间线 + 可选 Plyr/Video.js 播 MP4 | 自写可控、无依赖；最终成片用 Plyr 体验好 |
| 字体 | `simhei.ttf`（你已验证 CJK 方案） | 解决 ffmpeg drawtext 中文乱码 |

### 3.2 后端（Orchestrator）
| 需求 | 选型 | 理由 |
|---|---|---|
| Web 框架 | **FastAPI（量产）/ 标准库 http.server（原型，零依赖）** | 原型用 stdlib 即跑；量产用 FastAPI 异步契合 AGNES 轮询 |
| AGNES 调用 | **现有 `agnes_client.py`**（已实测跑通） | 含 5 RPM 限流 + 429/5xx 退避，直接复用 |
| 配音 | gTTS（开发，已装）/ tts_minimax / tts_fish（待接） | 沿用现有 voice 脚本 |
| 合成 | **ffmpeg + assemble.py**（现有） | 已含字幕/转场/AI 标 |
| 质检 | **quality_check.py**（现有） | 黑场/静音/静帧/画质/内容全覆盖 |
| 音效/BGM | **SoundsFree（现有 skill）** 程序化 SFX + 商用授权 BGM 库 | 零版权风险 |

### 3.3 状态与编排
| 需求 | 选型 | 理由 |
|---|---|---|
| 数据契约 | `storyboard.json`（SceneSpec）+ `manifest.json` | 你已有；新增 `asset_*` 字段即可 |
| 批量排产 | asyncio + 内置限流（复用 agnes_client 的 5 RPM） | AGNES 视频约 5 RPM、500s/天，必须批次 |
| 任务可见性 | TaskList / 前端进度条 + 日志面板 | 对应你"前台跑+进度可见"纪律 |
| 定时/自动化 | 本机 `automation_update` 或 cron | 支持"每天自动出 N 集" |

---

## 4. 全流程自动化方案设计

### 4.1 两种运行模式（核心：自动化 + 人工介入并存）

**模式 A · 全自动（一键出片）**
```
Studio 点「生成整集」→ 后端遍历 shots：
  对每镜 → (若无参考图) AGNES 出图 → (若无视频) AGNES 出视频 → TTS 配音
  → 全部完成 → assemble 合成 → quality_check → 返回 epNN.mp4
全程限流 5 RPM，进度实时回传 Studio 进度条。
```

**模式 B · 人工介入（预览→改→再预览→局部生成）**
```
Studio 改某镜 subtitle/prompt/时长 → 实时预览（零成本）
→ 只点该镜「生成真实画面」→ 后端差异生成这一镜 → 写回 asset_video
→ Studio 该镜预览框换成真视频 → 满意后点「合成成片」
```

### 4.2 自动化触发方式
- **手动按钮**：Studio 内"生成整集 / 生成此镜"。
- **文件监听**：`watchdog` 监听 storyboard.json 变更 → 自动差异重生成（改完即出片）。
- **定时任务**：`automation_update` 设"每日 09:00 自动出 EP+N"（M3 后配合分发）。

### 4.3 失败与重试
- AGNES 429 → 退避降并发（agnes_client 已内置）。
- 某镜生成失败 → 标记 `shot.status=failed` + 错误，Studio 红标，可单独重跑，不影响其他镜。
- 质检 fail（黑场/静音）→ 自动触发该镜重生成，最多 N 次。

### 4.4 商用合规（沿用你已有的清单，嵌入流程）
- 角色形象/音色/剧本/BGM 原创或授权 → 在阶段 2/4 入口校验。
- 成片自动叠 `post.ai_label`「AI 生成」标识（assemble 阶段）。
- 平台规则预检（9:16/时长/敏感词）→ 阶段 6/7。

---

## 5. 可视化界面要求（Storyboard Studio）

> 这是"支持预览、修改、再预览，每次修改看到实时效果并最终生成真实动画"的承载面。原型已落地在 `short_drama_workflow/html_prototype/studio.html`，双击即开。

### 5.1 界面布局（四区）
```
┌────────────┬────────────────────────────┬──────────────────┐
│ 分镜时间线  │      画面预览 Stage          │  单镜参数编辑器   │
│ (shot 列表) │  (参考图/真视频 + 字幕 +     │  subtitle/prompt  │
│ 点击选中    │   旁白 + 情绪徽章 + 转场)    │  duration/voice/  │
│            │  [▶ 播放整集] [合成成片]     │  emotion/transition│
├────────────┴────────────────────────────┴──────────────────┤
│ 控制台 / SceneSpec JSON（契约可视化）+ 生成按钮 + 进度条 + 质检报告 │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 交互要求（逐条对应你的需求）
| 需求 | 实现 |
|---|---|
| **预览** | 选中镜头即时渲染；「播放整集」按 `duration` 顺序播放带转场，模拟成片节奏 |
| **修改** | 右侧编辑器改任意字段 → 预览**实时**更新（无保存即所见） |
| **再预览** | 改完直接看效果，零成本循环，直到满意 |
| **生成真实动画** | 每镜「AGNES 生成真实画面」+ 整集「生成整集」；真视频写回后预览框自动切换 |
| **前后对比** | 每镜 toggle：占位原型 ↔ 真实 AGNES 画面，一眼看出差异 |
| **进度可见** | 生成时进度条 + 日志面板 + 每镜状态徽章（待生成/生成中/完成/失败） |
| **根因归因** | 失败镜标红 + 错误原因，对应你"出问题先定位哪层"纪律 |

### 5.3 与后端的打通（seam）
- Studio 通过 `fetch` 把当前 SceneSpec POST 给后端 `/api/generate/shot`。
- 后端（原型用零依赖 `server.py`，默认 dry-run 不花 token；设 `REAL=1` 才真调 AGNES）返回资产 URL，Studio 写回并刷新。
- 双击 `studio.html`（file://）时自动降级为"本地 stub 模式"：生成按钮展示**将要发给 AGNES 的确切 payload**，证明数据流对的；跑 `server.py` 即真正打通。

---

## 6. 实施路线（接你现有 M1–M4）

| 步 | 动作 | 交付 |
|---|---|---|
| 1 | 把现有 `ep01_storyboard.json` 接进 Studio（已完成原型） | 可在浏览器预览/改 EP01 |
| 2 | `server.py` dry-run 跑通 seam，确认 payload 正确 | 数据流验证无问题 |
| 3 | 设 `REAL=1` 实跑 1 镜 AGNES，验证"占位→真视频"切换 | 端到端单镜闭环 |
| 4 | 加差异生成 + 进度条 + 质检报告面板 | 人工介入模式完整 |
| 5 | 「生成整集」+ 限流批次 + 合成 | 全自动模式完整 |
| 6 | 文件监听 / 定时任务 + 分发面板 | 全自动化 + 可变现 |

---

## 7. 关键结论（给老板的）

1. **不用造新管道**——SceneSpec（你已有的 storyboard.json）就是前后期共用契约，浏览器和 AGNES 只通过它对话。
2. **前期 HTML 原型不是"玩具"**——它是 SceneSpec 的可视化编辑器+播放器，验证叙事/节奏/剪辑**零成本**，确认后才花 token。
3. **贯通点极简**——一个 `/api/generate/shot` 端点 + 资产 URL 写回，就把"预览"和"真实动画"连起来了。
4. **自动化与人工介入不矛盾**——模式 A 全自动、模式 B 局部改局部生成，同一套界面两套用法。
5. **今天就能跑**——`html_prototype/studio.html` 双击即开，`server.py` 零依赖起服务，dry-run 不花一分钱先验证逻辑。

> 下一步建议：先双击 `studio.html` 看 EP01 的 HTML 原型效果，确认"前期流程跑通"；再跑 `server.py` 用 dry-run 看 seam 数据；都满意后设 `REAL=1` 实出 1 镜真视频，闭环就通了。
