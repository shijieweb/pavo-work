# 02 · API 清单（54 端点全量）

> 前端真实调用 39 个已全部匹配（无真空转）；标注 REAL 的端点 REAL=0 时返回 dry-run 预览。
> 铁律：新增端点必须同步 `agnes_proxy.py` STUDIO_PREFIXES。

## 项目管理
| 端点 | 方法 | 参数 | 返回 | 状态 |
|---|---|---|---|---|
| `/api/projects` | GET | — | `{active, projects[]}` | ✅ |
| `/api/project/new` | POST | name | `{ok, project_id}` | ✅ |
| `/api/project/switch` | POST | project | 切 ACTIVE | ✅ |
| `/api/project/archive` / `restore` | POST | project | 归档/恢复 | ✅ |
| `/api/project/delete` | POST | project | 删除（备份先行） | ✅ |
| `/api/project/reconcile` | POST | — | 修复分镜↔参考图关联 | ✅ |

## 数据读写
| 端点 | 方法 | 参数 | 返回 | 状态 |
|---|---|---|---|---|
| `/api/spec` | GET | ?project= | `{ok, project, real, spec, meta}` | ✅ |
| `/api/spec` | PUT | spec 全量 | 防清零拦截 | ✅ |
| `/api/meta` | GET/PUT | 任意字段 | 浅合并落盘 | ✅ |
| `/api/log` | POST | level/msg/url | 前端上报落日志 | ✅ |
| `/api/logs` | GET | ?date=&lines= | 日志内容（WARNING 模式 403） | ✅ |

## 生成（异步：提交 accepted + GET status 轮询）
| 端点 | 方法 | 参数 | 返回 | 状态 |
|---|---|---|---|---|
| `/api/agent` | POST | prompt/prev_plan | task_id | ✅ |
| `/api/agent?task_id=` | GET | — | task 状态/plan | ✅ |
| `/api/generate/storyboard` | POST | novel+req | 分镜 JSON（thinking，重试 3） | ✅ |
| `/api/generate/shot` | POST | id/force/shot | accepted | ✅ |
| `/api/generate/status?shot=` | GET | — | running/done/failed/unknown | ✅ |
| `/api/generate/keyframes/shot` | POST | id/force | accepted | ✅ |
| `/api/generate/keyframes/status?shot=` | GET | — | 同上 | ✅ |
| `/api/generate/audio/shot` | POST | id | MiniMax 单镜配音 | ✅ |
| `/api/generate/audio` | POST | — | 全片配音 | ✅ REAL |
| `/api/generate/references` | POST | — | 全部角色锚点 | ✅ REAL |
| `/api/generate/scenes` / `scene` / `props` / `prop` | POST | — | 资产图 | ✅ REAL |
| `/api/generate/topic` / `script` | POST | — | 选题/剧本 | ✅ REAL |

## 资产/提示词
| 端点 | 方法 | 参数 | 返回 | 状态 |
|---|---|---|---|---|
| `/api/asset/prompt` | POST | type/cn_prompt | 英文 img_prompt | ✅ |
| `/api/asset/extract` | POST | — | AI 提取 cn_prompt | ✅ |
| `/api/prompt/optimize` | POST | type/text | AI 优化提示词 | ✅ |
| `/api/prompt/test` | POST | — | 提示词测试面板 | ✅ |
| `/api/prompt/library` | GET/PUT | — | 提示词库读写 | ✅ |
| `/api/style/keywords` | POST | — | 风格英文关键词 | ✅ |
| `/api/novel/generate` | POST | theme | AI 写小说 | ✅ |
| `/api/outline/generate` | POST | — | 大纲（thinking） | ✅ |

## 视频/合成/质检
| 端点 | 方法 | 参数 | 返回 | 状态 |
|---|---|---|---|---|
| `/api/shot/rework` | POST | id/note | 返工重生成 | ✅ |
| `/api/finalize` | POST | transition/subtitle/ai_watermark/bgm | 合成 final.mp4 | ✅ |
| `/api/assemble` | POST | 同 finalize | 同（旧端点） | ✅ |
| `/api/quality` | POST | id/video 可选 | `{ok, video, report:{technical,content,quality}}` | ✅ |
| `/api/diagnose` | POST | id | AGNES 4 维评分写回 shot.diagnosis | ✅ |
| `/api/faceqc` | POST | project | `{ok, per_shot[], overall, issues, thresholds}` | ✅ 0811 补白名单 |
| `/api/facefix` | POST | project | 低分镜纠偏重渲 | ✅ 0811 补白名单 |
| `/api/export` | GET | ?zip=1 | final.mp4 或项目 ZIP | ✅ |
| `/api/key-pool` | GET | — | 密钥池健康 | ✅ |

## 流水线/队列
| 端点 | 方法 | 参数 | 返回 | 状态 |
|---|---|---|---|---|
| `/api/pipeline/run` | POST | — | 一键全流程（后台） | ✅ |
| `/api/pipeline/progress` | GET | — | 阶段/百分比 | ✅ |
| `/api/pipeline/stream` | GET | — | SSE 流式进度 | ✅ |
| `/api/pipeline/stop` | POST | — | 停止 | ✅ |
| `/api/pipeline/batch` | POST | — | 批量流水线（夜间队列） | ✅ |
| `/api/queue/enqueue/list/cancel/stop` | POST | — | 队列调度器（BATCH_QUEUE） | ✅ |
| `/api/series/` | GET | series_id | 跨集锚点库（前端暂无入口） | ✅ |

## 依赖脚本（/api/* 背后）
`assemble.py`（ffmpeg 合成）/ `quality_check.py`（黑场/静音/静帧/编码）/ `face_identity.py`（SFace+YuNet）/ `diagnosis.py`（AGNES 多模态）/ `batch_queue.py`（cron 队列）——均在 `scripts/edit/`，缺失任一相关端点即崩。

## 契约要点
- 提交+轮询：POST 立即返回 `{ok, accepted}`；GET status 返回 `running/done/failed/unknown`（unknown=服务重启状态丢失，前端提示重试）。
- 幂等：关键帧/视频已生成且非 force → `{skipped:true}`（不烧额度）。
- 429 限流：视频 RPM=5；后端自动 15/30/45s 退避重试 3 次。
- REAL=0：生成类端点返回 dry-run 预览（本地开发不烧额度）。
