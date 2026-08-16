# 多 Agent 跨机方案评审共识系统 · 调研 / 设计稿

> 来源：老板 2026-08-15 新需求（先于建设，先做调研）。
> 需求原话：多个 Agent 在不同机器、经 VPS 中转；老板说一句 → 2-3 个 Agent 都收到 → 各自追问 3 问题 → 老板答 → 各生成方案 → 互相评审 → 多轮交谈 → 出最终共识方案。
> 配套：B 角色已落成 `requirement-clarifier` skill（`~/.workbuddy/skills/requirement-clarifier/SKILL.md`），本需求的"追问"环节可直接复用。

## 一、结论（一句话）
这套系统的核心不是"多 agent 框架"而是"**跨机中继 + 一轮 facilitator 状态机**"：用现成轻量 relay hub 解决不同机器互通，用自研 facilitator 驱动"广播→追问→生成→互评→多轮→共识"五阶段，**不自研重框架、不锁 AutoGen**，最契合老板"全云 API、不锁死"底线。

## 二、框架格局（辩论 / 共识类，2026 实测）
| 框架 | 辩论/共识适配 | 状态 | 评价 |
|---|---|---|---|
| **AutoGen GroupChat** | ⭐⭐⭐⭐⭐ 天生为对话辩论/共识 | **维护模式**（微软转 Agent Framework；AG2 社区分支续更） | 模式最贴合但长期支持不确定，且单机取向 |
| **CrewAI** | ⭐⭐ 角色流水线快，但辩论=它的弱项 | 活跃、最快出 demo | 不适合自由辩论，强扭会 debug 噩梦 |
| **LangGraph** | ⭐⭐⭐ 状态机+checkpoint+HITL 强 | 活跃、生产级 | 适合拿来做 **facilitator 状态机**（阶段流转/断点续跑），不当 agent 通信层 |
| 自研 facilitator + 轻 relay | ⭐⭐⭐⭐ 完全可控 | — | **推荐**：辩论逻辑自己写，transport 用现成 hub |

> 关键教训（业界共识）：对话型 group chat 必须设 `max_round` + 明确终止条件，否则无限循环烧 token（AutoGen 的坑）。我们的 facilitator 必须封顶轮数。

## 三、跨机中继架构（VPS 中转，已有现成范式）
老板说的"VPS 给他们中转"= 业界标准 **Agent Relay Hub** 模式：各机 agent **主动拨出**连 VPS（WebSocket，NAT 无感、不需开入站端口），hub 做广播/按名路由 + 心跳保活 + shared secret 鉴权。

| 现成项目 | 机制 | 契合度 |
|---|---|---|
| **ai-comms** | Agent Hub on VPS；WS 持久连接+心跳(25-30s)；**`!agents all` 广播任务给所有 agent**；按 agent name 路由；HUB_SECRET 鉴权；支持混合不同 IDE/agent 实例 | ⭐⭐⭐⭐⭐ 几乎现成："一句话他们都收到"= broadcast |
| **perkos-a2a** | Relay Hub on VPS；WSS 拨出；Broker+Registry+RateLimiter；shared API key；离线消息队列 | ⭐⭐⭐⭐⭐ NAT 友好、轻量 |
| cmdop | 中继 hub；agent 拨出无入站端口；gRPC+REST/WS；含 server 端协调 agent | ⭐⭐⭐⭐ 偏运维 fleet，可借鉴 |
| AgentLayer | 协议无关 relay（REST/gRPC/WS 互转）；<15ms；商业 $299/月 | ⭐⭐⭐ 商业、可不用 |

> 推荐：**直接复用 ai-comms 或 perkos-a2a 的 relay hub**（npm/tsx 一行起），把精力放在 facilitator 与 agent 节点逻辑上，不重复造传输层。

## 四、推荐架构（草案）
```
                 ┌─────────────────────────────────────┐
   老板一句 ──────►│  VPS: Relay Hub (ai-comms/perkos-a2a) │
                 │  - 广播/按名路由 · 心跳 · secret 鉴权   │
                 └──────────────┬──────────────────────┘
            ┌──────────────────┼──────────────────┐
        WS 拨出             WS 拨出             WS 拨出
      ┌─────▼─────┐      ┌─────▼─────┐      ┌─────▼─────┐
      │ Agent A   │      │ Agent B   │      │ Agent C   │  (不同机器/不同模型)
      │ (机1)     │      │ (机2)     │      │ (机3)     │
      │ LLM调用   │      │ LLM调用   │      │ LLM调用   │
      └───────────┘      └───────────┘      └───────────┘
            ▲ 各节点只做：收任务→调云LLM→回结果（薄节点）
            │
      Facilitator（状态机，跑在 VPS 或老板机）：驱动五阶段、收集、合并
```
- **Agent 节点（薄）**：每机一个进程，连 hub，收到消息→调云 LLM（可每机不同模型制造多样性）→回传。不直接互连。
- **Facilitator（厚）**：实现阶段状态机，是系统大脑；可独立进程或 hub 内的协调 agent。
- **LLM 后端**：各节点调老板已有云 API（DeepSeek/MiniMax 等），零本地部署。

## 五、执行流程 → 阶段状态机（映射老板原话）
```
PHASE 0 BROADCAST   老板一句 → hub 广播 → 所有 agent 收到
   ↓
PHASE 1 CLARIFY     每 agent 追问 ≤3 问题（可复用 requirement-clarifier 的"一次一问+assumption"）→ 老板作答 → 广播答案
   ↓
PHASE 2 GENERATE    每 agent 独立生成方案
   ↓
PHASE 3 REVIEW      两两/全配对互评（每 agent 评他人方案，给 rubric 分+异议点）
   ↓
PHASE 4 DELIBERATE  多轮交谈（≤3 轮封顶）：针对异议点辩论/修订
   ↓
PHASE 5 SYNTHESIZE  共识合并：提取共同点→ facilitator 合成一份"他们都认可"的最终方案
   ↓
DONE  交付（含各 agent 对最终方案的签署/打分）
```
> 每一步设超时与轮数上限，防挂死/烧 token。

## 六、与 B 角色（requirement-clarifier）的协同
- PHASE 1 的"每 agent 追问 3 问题" = 把 B 的澄清机制下沉到每个 agent 节点（或 facilitator 统一代问后分发）。
- 一致点：一次一问、assumption 标注、挑战假设、边界封顶——直接复用，不必重造。
- 即：本系统内部各 agent 也用 B 的方式追问老板，保证"问清"在前。

## 七、待澄清（B 角色 8 维度找出的模糊点 · 最关键 3 问）
> 老板原话要"追问3个问题"，以下即套 B 后最该先问的 3 个（决定架构走向）：

1. **"都认可"的判定标准是什么？（验收标准·核心）**
   - 选项：A 每 agent 对最终方案打分≥阈值（如≥4/5）即视为认可；B 多数投票过半；C facilitator 只合并"所有 agent 均同意的点"，分歧点单独列出交老板定；D 一轮辩论后直接由 facilitator 出综合版、不要求逐人签署。
   - 这决定 SYNTHESIZE 阶段怎么写。

2. **几个 agent、各自什么模型？（范围+约束）**
   - 2 还是 3 固定？还是可配置？
   - 同模型（保一致、易收敛）vs 异模型（保多样、辩论更有价值，如 DeepSeek+MiniMax+另一家）？
   - 每 agent 人设/专长是否不同（如"保守派/激进派/技术派"）？

3. **中继与 LLM 后端怎么落地？（系统关系+硬约束）**
   - relay hub 直接复用 ai-comms/perkos-a2a，还是自研轻量 WS relay？
   - LLM 用老板哪个云 API（DeepSeek / MiniMax / 其他）？token 预算/单需求成本上限？
   - 与现有看板/dispatch 是否打通，还是独立新系统？

## 八、下一步建议（待老板答完 3 问再建）
1. 老板回答第七节 3 问 → B 出需求简报（ready 门过）。
2. 立 T 卡（PRD/design/test/acceptance），进 `software-team-dispatch` 前置门。
3. 实施：先起 relay hub（复用现成）→ 写薄 agent 节点 → 写 facilitator 状态机 → 真测一轮（拿本需求本身跑通"多 agent 给我出方案"）。

> 注：本调研仅为"先调研"，未写任何代码；skill 与 relay 均待老板拍板后动手。
