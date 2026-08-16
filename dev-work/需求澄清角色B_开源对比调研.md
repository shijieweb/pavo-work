# 需求澄清角色 B · 开源项目对比调研

> 来源：老板 2026-08-15 指示"去 GitHub 看有没有专门做追问分析的，拿出来和我们自己的对比，看哪些适合直接拿开源改造"
> 配套：`需求澄清角色B_设计稿.md`（我们自己的 B 定义）

## 一、结论（一句话）
GitHub 上**有一类专门做"追问 / 澄清"的轻量开源项目**，其中 **`idea-harness`（MIT·零依赖·专精澄清）几乎就是 B 角色的现成实现**，可直接克隆改造为 B 底座；**不必从零造**。我们自研的 B 设计稿缺的"问到什么程度算清楚（ready 判定）"正好被它补上。

## 二、候选分类

### A 类：专精"追问 / 澄清"（最贴合 B 角色）
| 项目 | 核心机制 | 许可 / 依赖 | 与 B 适配度 |
|---|---|---|---|
| **idea-harness** (jasper0507) | 7 个澄清门槛（决策树，非线性） + 4 项精确度检查 + 硬状态机 `gathering→needs-precision→blocked→ready` + **默认每次只问一个最关键问题** + Ready 才输出需求简报 | **MIT** / skill-only·零运行时依赖 | ⭐⭐⭐⭐⭐ 直接改造底座 |
| **dev-deep-interview** (evo-nexus) | 五维打分（1-5：领域/范围/成功标准/约束/干系人），平均 ≥4 跳过、<4 进入访谈；**模糊度 <20% 才放行**；苏格拉底式 | Claude skill | ⭐⭐⭐⭐ 借鉴"量化放行门槛" |
| **Socratic Requirements** (kaneorca) | intake 路由器：意图分类→选方法论→澄清→输出可派发规格；问题上限 7 | skill | ⭐⭐⭐⭐ 借鉴"意图路由" |
| **Elucidate** (gchartier) | 四阶段迭代提问 Orient/Frame/Investigate/Synthesize；含提问研究论文 | **GPL-3.0（传染性）** | ⭐⭐ 慎用（许可不友好·偏认知探索） |

### B 类：含 clarify 的 Spec-Driven 大框架（过重，不推荐直接拿）
| 项目 | 说明 | 评价 |
|---|---|---|
| **GitHub Spec Kit** (github/spec-kit, 121K★, MIT) | Constitution→Specify→**Clarify**→Plan→Tasks→Implement 全流水线 | clarify 只是其中一环，整体太重；只可借鉴"一次一问收敛"思想 |
| **BMAD Method** | 21 个 AI 角色 + 50+ 工作流 | 对 3 人小团队严重过度 |
| **OpenSpec** | 增量改动专用 diff 式 | 场景不匹配（我们常是全新需求） |

### C 类：通用 Agent 框架（澄清只是附带，不直接对口）
Youtu-Agent / Qwen-Agent / Trae Agent / Hermes Agent —— 通用运行时，澄清非其专攻。

## 三、与我们 B 设计稿的差距（关键洞察）
我们 `需求澄清角色B_设计稿.md` 定义了 **8 维度框架 + 工作法**，但**缺两样开源已解决的东西**：

1. **ready 判定（问到什么程度算"清楚"）** → idea-harness 的"4 精确度检查 + 状态机 ready"直接补。
2. **量化放行门槛** → dev-deep-interview 的"五维打分、模糊度 <20% 才放行"可借鉴。

> 一句话：我们定义了"**问哪些维度**"，开源补了"**怎么算问完了**"。两者合起来才是完整闭环。

## 四、改造建议（推荐路线）
1. **底座 = idea-harness**：克隆到 `~/.workbuddy/skills/`，改名 `requirement-clarifier`；把其"7 门槛"适配为"我们的 8 维度"，**原样保留状态机 + 精确度门 + 一次一问**。
2. **借鉴 dev-deep-interview**：给 B 加量化放行门槛（五维打分，模糊度 < 阈值才 ready）。
3. **借鉴 Socratic Requirements**：加意图路由（创意 / 工程 / 产品 → 选澄清方法论）。
4. **不引入**：Spec Kit / BMAD（太重）、Elucidate（GPL-3.0 传染性 + 偏认知探索非执行）。
5. **微调提示词**：idea-harness 原面向"非程序员小应用想法"，改为"**老板用业务语言描述短剧项目需求**"——契合度本就高（老板非专业 PM，要的是"被问清楚"而非"被写代码"）。

## 五、闭环 + 有效判断（供老板拍板）
- **闭环**：B 从"口头维度清单"升级为"有状态机 + 精确度门 + 量化门槛的可执行 skill"，真正闭合"问清→一遍过"。
- **有效**：MIT 零依赖、克隆即用、不锁 SaaS、契合我们既有 skill 体系；改造成本极低、风险最低。
- **推荐**：采纳 **idea-harness 改造为 B 角色底座 + 借鉴 dev-deep-interview 量化门槛** 的路线。
- **待拍板（修订）**：是否同意我按"idea-harness 骨架 + Tier1 机制合成"路线，构建 `requirement-clarifier` skill 并固化进 `software-team-dispatch` 前置门？

---

## 六、老板补充候选（别人推荐，3 个）

| 项目 | 核心机制 | 形态/许可 | 对 B 的价值 |
|---|---|---|---|
| **prd-maker** | 检测技术水平→自适应追问；**8 要素覆盖检查清单**；一次一问最多 10 问；已答跳过；**不重要填默认值标 (assumption)**；纯 md PRD 7 段结构；**结构 linter 验证** | Claude Code/Codex 插件，即装即用 | ⭐⭐⭐⭐⭐ assumption 标注 + linter 验证是缺的关键机制 |
| **requirements-agent** | **多代理流水线** Clarify→Draft→Critique→Revise→Final；Clarify 追 2-4 问（≤8/≤2 轮）；**Critique 用 5 维 rubric 逐条检查**；可交互 PRD | 独立 web 应用 | ⭐⭐⭐⭐ 借"边界封顶+5维rubric量化门"；流水线/Web 太重不引入 |
| **interview-agent** | 10 阶段结构化访谈；一次一问；**follow_up_depth 追问深度**；**挑战假设问"为什么"**；产出=需求文档+**决策日志+风险登记+待确认问题** | Python CLI 可自定义 | ⭐⭐⭐⭐⭐ 挑战假设+决策/风险/待确认产出物最对口 |

## 七、综合机制选型（7 候选全纳入 · 最值得参考的机制）

**Tier 1 — 必借（直接决定 B 是不是真阀门）**
1. 一次一问 + 已答跳过（prd-maker / idea-harness / interview-agent 三方印证）→ 降老板认知负担。
2. 不重要维度填默认 + 标 (assumption)（prd-maker）→ 补"8 维度只追缺失"的漏洞：不重要的别卡，填默认并显式亮给老板"我替你定了什么"。
3. 挑战假设问"为什么" + follow_up_depth（interview-agent）→ B 不是记录员，要戳破隐含假设；深度可调。
4. 结构 linter / 输出校验（prd-maker）→ B 产出的简报过一道结构闸（8 维是否齐、assumption 是否标），不过不进 PRD。这是"一遍过"的质量锁。
5. 边界封顶 ≤N 问 / ≤M 轮（prd-maker 10 问 / requirements-agent 8 问 2 轮）→ 防无限追问拖死主线。
6. 量化 ready 门槛（requirements-agent 5 维 rubric / dev-deep-interview 模糊度<20%）→ 定义"怎么算问完了"。

**Tier 2 — 选借**
7. 自适应追问（检测技术水平）（prd-maker）→ 老板非技术，用业务语言问、技术维降权。
8. 产出物 = 需求简报 + 决策日志 + 风险登记 + 待确认问题（interview-agent）→ 正是我们 8 维里 ⑥风险 ⑦决策 的落地载体，不只出 PRD。
9. 意图路由→选澄清方法论（Socratic Requirements）→ 创意/工程/产品三类走不同追问模板。

**Tier 3 — 不引入（仅借鉴思想）**
- 多代理流水线 / 独立 web 应用（requirements-agent）：我们是 skill 非 web app；Critique 改成 B 内部"自检步"。
- 10 阶段结构化访谈（interview-agent）：阶段太死，弱化为"维度遍历"。
- Elucidate（GPL-3.0 传染性）：许可排除。
- Claude Code/Codex 插件形态：借鉴"即装即用/自包含"，但落 WorkBuddy skill。

## 八、修订后的推荐路线（博采众长合成，而非单克隆）

- **骨架** = idea-harness 状态机（gathering→needs-precision→blocked→ready）+ 一次一问 + Ready 出简报（MIT 零依赖，克隆即用）。
- **叠加 Tier1 机制**：把"7 门槛"映射为"我们的 8 维度"；加 assumption 标注（prd-maker）、挑战假设+follow_up_depth（interview-agent）、结构 linter 校验（prd-maker）、边界封顶（≤10 问/≤3 轮）、5 维 rubric ready 门（requirements-agent/dev-deep-interview）。
- **产出物** = 需求简报 + 决策日志 + 风险登记 + 待确认问题（interview-agent），纯 md 7 段 + linter 验证（prd-maker）。
- **自适应**：检测老板技术水平→业务语言提问（prd-maker）。
- 结论：**单克隆 idea-harness 已不够，最佳是"以它为骨架、融合众长合成"**——改造成本仍极低（零依赖、本地 skill），但阀门更完整。
