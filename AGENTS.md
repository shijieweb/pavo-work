# AGENTS.md · 短剧自动化创作项目

> Trae 每次对话自动读取本文件。项目级规则，仅本项目中生效。
> 配套规则见 `.trae/rules/short_drama_conventions.md`；跨会话交接见 `.trae/documents/context-handover/`。

## Project Overview
- **目标**：构建可发布到国内平台（抖音/快手/视频号）卖钱的 AI 短剧产品，不是玩具/MVP。验收以「可发布、可变现」为准。
- **内容形态**：AI 角色剧情剧，角色视觉一致性是技术核心。
- **形态规格**：竖屏 9:16，单集 1–3 分钟。
- **变现路径**：IAA + IAP 混合（红果/河马/麦芽/点众/九州/端原生小程序）；前 3 集免费须最精彩，付费卡点放悬念最紧时。
- **合规底线**：角色形象/音色/剧本/BGM 须原创或授权；成片含平台要求的 AI 生成标识（依《微短剧创作生产及内容审核技术规范》团体标准）。

## 部署架构（全云 API）
- **视频/图像生成**：AGNES-AI 统一网关（老板已购 VIP）。
  - 图像：`agnes-image-2.1-flash` 出角色/场景参考图
  - 视频：`agnes-video-v2.0` 图生视频 + 关键帧绑定保角色一致
  - 剧本：`agnes-2.0-flash`（同网关）
  - 关键坑：视频轮询地址 `https://apihub.agnes-ai.cn/agnesapi?video_id=`（不在 /v1 下）；完成态取 `url`。
- **配音（当前 = gTTS 开发验证层，量产商用引擎待定）**：
  - 开发验证：gTTS 免费中文女声单音色（⚠️ 单声无法区分旁白/独白/角色，商用需换多音色 TTS）
  - 量产候选优先级：MiniMax（短视频首选自然度）> Fish Audio（声音克隆快）> 火山（便宜抖音同源）
  - AGNES 有音频引擎 Agnes-Audio-2.0 但无公开 TTS API，不可自动化调用。
- **编排与剪辑**：开源脚本（ffmpeg 等），不走单一商业 SaaS。

## 核心数据契约：SceneSpec
- `scripts/storyboard/ep01_storyboard.json` 的 `shots` 数组 = 浏览器(HTML 原型)与 AGNES 后端共用的唯一数据源。
- 前期预览/修改读它写它；后期生成按它执行、把资产 URL 写回它。
- 已验证：server.py 起服务后 GET /api/spec 加载分镜、POST /api/generate/shot 回正确 AGNES payload、资产 URL 写回、studio.html 正常服务。
- Studio 四区：分镜时间线 / 画面预览 Stage / 单镜参数编辑器 / 控制台(SceneSpec JSON + 日志 + AGNES Payload)。

## Build & Commands（常用）
- 起预览服务（dry-run 不花 token）：`python short_drama_workflow/html_prototype/server.py`
- 真实模式（花 token）：`REAL=1 python short_drama_workflow/html_prototype/server.py`
- 出片后必跑：`python short_drama_workflow/scripts/.../quality_check.py`（黑场/静音/静帧/画质/内容覆盖全检）
- 字体坑（已固化）：Windows 绝对路径含 `C:` 冒号会被 ffmpeg filter 解析器当选项分隔符 → 必须拷贝字体到项目目录用相对路径。当前用 `simhei.ttf`（黑体）放 `output/ep01/` 和项目根目录。

## Code Style / 约定
- 输出必须含表格 + 详细摘要；分步确认（常回"好的"），关键步骤后需截图/视觉反馈验证。
- 路径用相对路径，不写死绝对路径。
- 一切以商用标准为准，不用占位符糊弄最终成片。

## 用户偏好
- 称呼「老板」，坐标南京。
- 偏好 GitHub 开源自建能力，规避单一商业 SaaS 锁定。
- 老板明确不愿本地部署（嫌装 ComfyUI/GPT-SoVITS 整合包麻烦），回归「全云 API」初心。

## 执行纪律（老板 2026-08-14 定 · 机制化）
- **接任何任务，第一步先读 `dev-work/执行流程.md`，按其中流程走**；不靠记忆、不临场自创 Agent 节奏。
- 所有可复用动作已下沉为 skill（`~/.workbuddy/skills/`）与脚本（`short_drama_workflow/scripts/`），优先调已固化资产，不重复造。
- 只读核查用 `bash short_drama_workflow/scripts/health_check.sh` 一键出真数据。
