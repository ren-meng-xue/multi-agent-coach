# 阶段 3+：Inline Trace · 面试期多 Agent 协作可视化 · 设计文档

**日期**：2026-05-26
**状态**：待实施
**前置 spec**：[2026-05-25-phase3-jd-agent-design.md](./2026-05-25-phase3-jd-agent-design.md)
**范围**：在已落地的 Phase 3 准备流水线基础上，将原 Phase 4「评估 Agent」提前，统一 Coach + 准备 + 面试三段体验的「多 Agent 协作面板」视觉，并把面板从「页面顶部固定卡」迁移为「聊天流内 inline 卡 + 每轮可见」。

---

## 1. 背景

Phase 3 已交付：
- 后端 `prepare` graph 完整跑通（MASTER + memory_search + jd_analysis + question_gen 共 4 个 agent）
- `POST /api/v1/prepare/start` SSE 事件（`node_start / node_token / node_done / done / error`）
- 前端 `PreparationCard / AgentTrace / TraceNode / QuestionListModal` 完整组件
- Coach 页 JD 输入入口（文本 / URL）+ sessionStorage 契约 → `/interview` 顶部固定 PreparationCard

参考原型 `html/interview.html` 暴露了两个 Phase 3 没覆盖到的体验诉求：
1. **每次用户输入都触发一张 inline trace 面板**（首句进入准备阶段如此；后续每轮答题也如此）
2. **面试期每轮都看得见多 Agent 协作**（面试官 + 评估两个子 agent 的 bullet 流式打字、并排出现）

第二点在原 Phase 3 spec 里被显式划入了 Phase 4：
> 阶段4 加入评估 Agent（并行打分）。Trace Timeline 底部分割线下方已预留「面试官 待命」「评估 后台静默打分」两个节点的展示位。

经决策，将 Phase 4 评估 agent 提前到本阶段，与 Phase 3 视觉迁移合并交付，统称 **Phase 3+**。

---

## 2. 产品目标

| 目标 | 衡量标准 |
|------|----------|
| 准备阶段 trace 视觉与聊天流统一 | PreparationCard 作为一条聊天消息出现在 messages 流，准备完成后可折叠保留 |
| 面试期每轮都看得见 Agent 协作 | 用户每发一条消息，下一条 assistant 内容前先出现一张 trace 卡，含 MASTER 决策 + 评估 + 面试官三个节点 |
| 每个 Agent 的输出都是 LLM 动态生成 | trace 上没有任何硬编码 bullet 文案 |
| 兼容 Coach 页与现有 PreparationCard 行为 | Coach 页 sessionStorage 契约不变；从 Coach 进入 /interview 仍能拿到 target_role/JD 触发准备 |
| 不引入"白屏等待" | 用户发消息到第一个可见 token 之间 ≤ 500ms（trace 卡占位 + master bullet 流式开篇） |
| 总耗时不显著上升 | 单轮评估 LLM 调用与面试官 LLM 调用并行执行；evaluator 在 closing 时复用，report_node 不重复评估 |

---

## 3. 不变项 vs 推翻项

**绝不动**：
| 模块 | 现状 | 不变原因 |
|------|------|----------|
| Coach 页 `coach-dashboard.tsx` 全部 UI 与状态机 | `initial / follow / switch / switch-target / new-role / custom-reply` | 入口体验已完整，已通过测试 |
| sessionStorage `interview_context` 契约 | `{ target_role, user_background, jd_text, jd_url }` | /interview 启动入口契约 |
| `prepare` graph 节点、路由、SSE 事件、prompts | 4 个节点 + 动态 chain | 已经是真·MASTER 动态调度，无需重做 |
| `/api/v1/prepare/start` 与 `/api/v1/prepare/resume` | multipart/form-data + SSE | 前端已对接 |
| JD 提取服务 `jd_extractor.py` | 支持 text / file (PDF/DOCX) / url | 已实现 |
| TurnRequest 契约 | `{ message, prepared_questions?, jd_context? }` | 已支持本阶段所需字段 |
| `report_node` 输出 schema | overall_score + 4 维 + highlights/improvements/key_concepts/common_mistakes | 历史卡 + Coach 页消费此 schema |
| `ChatInput / MessageBubble / ReportCard` 等前端基础组件 | — | 通用渲染 |

**本次推翻**（移除冗余节点 + 重做 interviewer graph）：
| 节点 | 移除原因 |
|------|----------|
| `opening_node` | 收集 target_role 的职责已由 Coach 页 + sessionStorage 完成 |
| `briefing_node` | briefing「确认开始」的语义已由 Coach 页「好，今天就练这个」承担 |
| `decide_next_node` | 「下一步该跑哪个 agent」的职责完全归 master_node，无独立存在必要 |
| `extract_opening_info / detect_briefing_intent` 等结构化输出 | 配套移除 |
| `route_after_briefing` 路由 | 配套移除 |

移除这些节点后，`interviewer` graph 节点池清爽且全部由 MASTER 动态调度。

---

## 4. UX 流程

### 4.1 完整链路

```
Coach 页（不变）
  └─ 老用户：好，今天就练这个 → [我有 JD] 可选 → 开始面试
  └─ 新用户：选岗位 chip → 填项目 → 我直接试一场吧
        ↓
  写 sessionStorage interview_context + reset_interview_session
        ↓
/interview 页加载
  ├─ messages[0] = trace 卡（准备阶段）   ← 新：从顶部固定卡迁移至聊天流
  │     状态机：running → done
  │     done 后默认折叠，保留 chain 节点摘要，可点开重看
  │     底部按钮："开始第1题"  "先看题目列表"
  │     按"开始第1题" → 调 /turn 出题
  └─ messages[1..] = 正常聊天 + 每轮 trace 卡
        每轮顺序：
          user 消息
          ↓
          trace 卡（面试期）   ← 新：每轮都插入
            节点：MASTER 决策 → 评估 → 面试官
            状态机：running → done，done 后默认折叠
          ↓
          assistant 消息（面试官追问文本）
```

### 4.2 准备阶段 trace 卡（inline 化）

| 状态 | UI |
|------|----|
| running | 顶部 live 点闪烁 + 标题"专家组正在工作"，节点逐个出现，bullet 流式打字 |
| done | 顶部 live 点变灰，标题"准备完成"，默认**折叠**节点详情，仅留摘要 + 两个按钮 |
| 折叠态展开 | 点击顶栏 chevron 重新展开看完整节点 |
| 准备完成且用户已点开始 | 卡片保留在聊天流上方，再次滚动可见 |

### 4.3 面试期每轮 trace 卡

| 状态 | UI |
|------|----|
| running | 同准备卡视觉，标题"本轮分析中"。节点出现顺序：先 MASTER 流式输出推理 bullet 与 chain → 前端按 chain 渲染后续节点 pending 占位 → 子 agent 逐个 running → done |
| done | 标题"本轮分析完成"，自动折叠，保留耗时摘要 + 本轮评分（若 chain 含 evaluator） |
| chain 只含 closing | trace 卡完成后紧随其后渲染 ReportCard，不再有"下一轮" |

**chain 不同时 trace 卡形态举例**：
- chain = `["evaluator", "followup"]`：3 个节点（master / evaluator / followup）
- chain = `["followup"]`：2 个节点（master / followup），缺评估节点
- chain = `["evaluator", "ask_question"]`：3 个节点（master / evaluator / ask_question）
- chain = `["closing"]`：2 个节点（master / closing）

### 4.4 进度指示

`InterviewProgressState`（已有）继续驱动顶栏题号 pill，不变。

---

## 5. Agent 拓扑（真·MASTER 动态调度）

两个阶段都采用「MASTER 用 LLM 决定 chain，子 agent 按 chain 串行执行」的统一模式（沿用 `prepare/master_node` 的双相调用范式）。

```
准备阶段（首句输入触发，已实现，仅视觉迁移）：
  MASTER → chain ∈ subset(memory_search, jd_analysis, question_gen)
  [4 个子 agent，chain 由 MASTER 动态决定]

面试阶段（每轮答题触发，本次新做）：
  MASTER → chain ∈ subset(evaluator, followup, ask_question, closing)
  [4 个候选子 agent，chain 由 MASTER 动态决定]
  
  典型 chain 示例（全部由 LLM 决策）：
    回答合格但可深挖：["evaluator", "followup"]
    回答跑题，拉回主题：["followup"]                    ← 跳过评估
    回答到位，进入下一题：["evaluator", "ask_question"]
    达到题目上限，收尾：["closing"]                      ← 跳过评估
    用户主动喊停：["closing"]
  
  约束：chain 末尾必须是 followup / ask_question / closing 之一
       （保证每轮一定有一条 assistant 回复给用户）

收尾（不变）：
  closing_node → report_node 聚合 turn_evaluations 出总报告
  （report_node 兼容 turn_evaluations 稀疏的情况）
```

**Phase 3+ 总计 8 个 agent 节点对用户可见**（准备 4 + 面试 4），全部 LLM 动态生成内容，全部由 MASTER 真·动态调度。

---

## 6. 后端架构变更

### 6.1 interviewer graph 重设计（真·MASTER 动态调度）

**新拓扑**：

```python
graph = StateGraph(InterviewState)
graph.add_node("load_context", nodes.load_context_node)   # utility 节点，无 LLM
graph.add_node("master",      nodes.master_node)           # 新，LLM 动态调度
graph.add_node("evaluator",   nodes.evaluator_node)        # 新，评估子 agent
graph.add_node("ask_question", nodes.ask_question_node)    # 保留
graph.add_node("followup",    nodes.followup_node)         # 改：自己生成追问文案
graph.add_node("closing",     nodes.closing_node)          # 保留
graph.add_node("report",      nodes.report_node)           # 改：聚合 turn_evaluations

graph.set_entry_point("load_context")
graph.add_edge("load_context", "master")

# master 输出 chain，按 chain 串行
graph.add_conditional_edges("master", route_after_master, {
    "evaluator": "evaluator",
    "ask_question": "ask_question",
    "followup": "followup",
    "closing": "closing",
})

# evaluator 之后看 chain 里下一个是谁
graph.add_conditional_edges("evaluator", _route_next_in_chain("evaluator"), {
    "followup": "followup",
    "ask_question": "ask_question",
    "closing": "closing",
    END: END,
})

# 终态节点
graph.add_edge("ask_question", END)
graph.add_edge("followup", END)
graph.add_edge("closing", "report")
graph.add_edge("report", END)
```

`route_after_master / _route_next_in_chain` 完全复用 `prepare/graph.py` 同名函数的实现思路（按 `state["chain"]` 顺序路由）。

### 6.2 master_node 设计

**职责**：每轮答题进入时，由 LLM 决定本轮调用哪些子 agent。

**输入**：
- 当前 `messages`（最后一条是用户最新输入）
- `stage / question_count / total_questions / followup_count / max_followups`
- `prepared_questions / current_question_index`（用于判断是否还有下一题）

**双相调用**（沿用 `prepare/master_node` 范式）：
- Phase 1：流式输出 1-2 句中文推理（打 tag `master_token_stream`）。例："这位候选人讲了一致性哈希但没给量化指标，先打分再追问 QPS"
- Phase 2：`with_structured_output(_InterviewMasterDecision)`：

```python
class _InterviewMasterDecision(BaseModel):
    chain: list[str]              # 子集：evaluator / followup / ask_question / closing
    reason: str = ""              # 给 log 用，不展示
```

**Chain 合法性约束**（在 master_node 末尾后置校验，必要时修正，校验顺序自上而下）：
1. 若 `question_count == 0`（用户还没答过第一题，刚进入面试）：强制 chain = `["ask_question"]`
2. 若 `question_count >= total_questions` 且 `followup_count >= max_followups`：强制 chain = `["closing"]`
3. chain 不能为空：fallback 到 `["evaluator", "followup"]`
4. 若 chain 含 `closing`，移除 closing 之后的所有节点
5. chain 末尾必须是 `followup / ask_question / closing` 之一（保证用户有回复）；末尾非法时追加 `"followup"`

合法性校验触发修正时 `log.warning("master_chain_invalid", ...)`。

**LLM 模型选择**：master_node 用快速模型（Haiku 4.5 或同级 fast 模型），因为它每轮都要跑，延迟敏感；evaluator_node / followup_node / ask_question_node 用默认 chat 模型（质量优先）。模型 ID 通过 settings 注入，不在节点代码内硬编码。

### 6.3 evaluator_node 设计

**触发条件**：被 master 加入 chain 才执行；不再硬编码 `if stage == interview` 判断（master 已经判断过了）。

**输入**：
- `messages`（用户最新答案在倒数第一条）
- 当前题目（从 `prepared_questions[current_question_index - 1]` 取，或 messages 中倒数第二条 assistant 内容）
- `jd_context`（可选）

**输出**：往 state 追加一项 `TurnEvaluation`：

```python
class TurnEvaluation(TypedDict):
    question_index: int           # 第几题
    followup_index: int           # 当题内第几次追问后的评估（0 = 主回答）
    bullets: list[str]            # 用户可见的评估要点（≤3 条）
    technical_depth: float        # 0-10
    quantified_results: float     # 0-10
    failure_tradeoffs: float      # 0-10
    structure: float              # 0-10
    summary_score: float          # 0-10，本轮综合
```

**state 字段追加**：

```python
class InterviewState(TypedDict, total=False):
    ...
    turn_evaluations: list[TurnEvaluation]   # 累积所有轮次评估（可稀疏）
    chain: list[str]                          # master 输出的本轮 chain
```

**LLM 实现**：双相调用：
- Phase 1：流式输出 bullets（打 tag `evaluator_token_stream`）
- Phase 2：`with_structured_output(TurnEvaluation)` 落 4 维分
- 复用 `prepare/nodes.py::_retry_llm` 装饰器

### 6.4 followup_node 重做

原 followup_node 依赖 `decide_next_node` 输出的 `followup_question` 字段。decide_next 被移除后，`followup_node` 自己生成追问文案。

```python
async def followup_node(state):
    # 流式生成追问文案，打 tag interviewer_answer_stream（沿用现有 delta 通道）
    text = await _generate_text(FOLLOWUP_SYSTEM_PROMPT, state)
    return {
        "stage": "interview",
        "followup_count": state.get("followup_count", 0) + 1,
        "assistant_message": text,
    }
```

新增 `FOLLOWUP_SYSTEM_PROMPT`（在 `prompts.py`），prompt 指导 LLM：基于最近一轮用户回答，提出**一个**深挖追问，语气克制。

### 6.5 report_node 聚合 turn_evaluations

closing 触发 report 时：
- 读取 `state["turn_evaluations"]`，按 4 个维度取平均（稀疏的轮次跳过，按实际有评估的轮次数为分母）
- 把每轮 bullets 合并 + 整场 messages → 喂给 LLM 让其生成 `highlights / improvements / key_concepts / common_mistakes`
- LLM 调用 1 次（只做归纳和文字组织，不做评分）

**降级路径**：若 `turn_evaluations` 完全为空（异常场景，例如 master 从未让 evaluator 跑过），退化为旧 `REPORT_SYSTEM_PROMPT` 整场评估。降级时 `log.warning("report_fallback_no_turn_evals", ...)`。

### 6.6 移除的节点和函数

为避免遗漏，明确移除清单：
- `opening_node / generate_opening_reply / OPENING_SYSTEM_PROMPT / OPENING_INFO_SYSTEM_PROMPT / extract_opening_info / OpeningInfoOutput`
- `briefing_node / generate_briefing_reply / BRIEFING_SYSTEM_PROMPT / BRIEFING_INTENT_SYSTEM_PROMPT / detect_briefing_intent / BriefingIntentOutput / generate_not_ready_reply / NOT_READY_SYSTEM_PROMPT / route_after_briefing`
- `decide_next_node / decide_next_action / DecideNextOutput / DECIDE_SYSTEM_PROMPT / route_after_decide`
- `InterviewState` 中 `opening_complete / briefing_intent / decision_action / decision_reason / followup_question` 字段

`InterviewSession.stage` 数据库字段保留 `opening/interview/closing` 三个枚举，但 `opening` 实质上不再出现（新 session 一上来 master 就决定 `ask_question`）。stage 字段由 `stream_interview_turn` 根据本轮 chain 推断设置（chain 含 closing → "closing"，其他情况 → "interview"）。

### 6.7 stream_interviewer_turn_events 改造

当前实现只过滤 `interviewer_answer_stream` tag 的 token。改造为：

- 复用 `astream_events(version="v2")`
- 节点边界事件：`on_chain_start`（带 `langgraph_node` metadata）→ 发 `node_start`；`on_chain_end` → 发 `node_done`（含 `elapsed_ms`，master 节点的 node_done 额外携带 `chain`）
- Token 事件：tag 命中以下三者之一时发 `node_token`：
  - `master_token_stream` → node=master
  - `evaluator_token_stream` → node=evaluator
  - `interviewer_answer_stream` → 沿用现有 `delta` 事件（**不改名**，保持前端 onDelta 不破）
- 全图结束（`on_chain_end` name=LangGraph）→ 发 `state` + 可选 `report` + `done`（沿用现有事件）

最终事件清单（向后兼容现有事件）：

```
新增：node_start / node_token / node_done
保留：state / delta / report / done / error
```

**节点 label 中文映射**（前端展示用）：

```python
INTERVIEW_NODE_LABELS = {
    "master": "MASTER",
    "evaluator": "评估",
    "followup": "面试官 · 追问",
    "ask_question": "面试官 · 出题",
    "closing": "收尾",
}
```

`load_context / report` 节点**不发 node_* 事件**（前者无 LLM，后者由专门的 `report` 事件承载），实现时在 SSE 流里过滤掉。

### 6.6 turn_evaluations 持久化

- 当前 `InterviewSession.report_json` 是 JSONB 字段，最终报告写入此处即可
- `turn_evaluations` 作为 report_json 内一个新字段 `turn_evaluations: list[...]` 嵌入存储，无需新建表
- 历史接口 `/api/v1/interview/history` 不需要改

---

## 7. 前端架构变更

### 7.1 PreparationCard 迁移到 messages 流

**改动**：在 `InterviewChat` 组件里：
- 删除当前在 JSX 顶部的 `<PreparationCard ... />`
- 在 messages 数组里新增一种特殊消息类型：

```ts
type InterviewChatMessage =
  | { role: "user" | "assistant"; content: string }
  | { role: "trace"; kind: "prepare"; payload: PrepTracePayload }   // 新增
  | { role: "trace"; kind: "turn"; payload: TurnTracePayload };     // 新增
```

`PrepTracePayload` 结构沿用现有 PreparationCard props（status / nodes / questions / summary / direction / onStart）。

**渲染分发**：在现有 message map 里加一个 `else if (m.role === "trace")` 分支，分别渲染 `PreparationCard` 或新增的 `TurnTraceCard`。

**TypeScript 收敛策略**：把 `InterviewChatMessage` 改成 discriminated union 后，所有现有访问 `m.content` 的地方需要用 `m.role === "user" || m.role === "assistant"` 做 type guard 才能拿到 content。受影响点（已识别）：
- `handleCopyChat`：复制时跳过 trace 消息
- 进度 pill 计算：基于 progress state 而非 messages，不受影响
- `MessageBubble` 渲染分支：trace 类型走新分支
其他位置由 TypeScript 编译报错驱动定位，逐处加 guard。

**生命周期**：
- 准备阶段 trace 消息在 `runPrepare` 启动时插入 messages[0]，根据 SSE 事件就地更新 payload
- 用户点击"开始第1题"后保留这条消息（不删除），后续答题继续 append

### 7.2 新增 TurnTraceCard 组件

**职责**：渲染面试期每轮的 trace 卡，与 PreparationCard 视觉一致，只换标题与节点集合。

**props**：

```ts
interface TurnTraceCardProps {
  status: "running" | "done";
  nodes: TraceNodeData[];      // 复用现有类型
  turnIndex: number;            // 第几轮（用于折叠后的摘要文本）
  summaryScore?: number;        // 评估完成后的本轮综合分
}
```

复用 `AgentTrace / TraceNode`，0 新增基础组件。

### 7.3 `streamInterviewChat` 扩展

`frontend/lib/interview-chat.ts` 的 `StreamInterviewChatOptions` 加：

```ts
onTraceNode?: (event: "start" | "token" | "done", data: {
  node: string;
  label?: string;
  text?: string;
  elapsed_ms?: number;
}) => void;
```

`handleSseEvent` 增加对 `node_start / node_token / node_done` 的处理，调用 `onTraceNode`。

### 7.4 InterviewChat 消息发送流程改造

`handleSendMessage`（或对应函数）改造为：

```
1. 把 user message append 到 messages
2. 立即 append 一条 { role: "trace", kind: "turn", payload: { status: "running", nodes: [] } }
3. 立即 append 一条 { role: "assistant", content: "" } 占位
4. 调 streamInterviewChat：
     onTraceNode → 更新最近一条 turn trace 消息的 payload
     onDelta → 追加到最近一条 assistant 消息的 content
     onState / onReport → 不变
5. 流结束 → 把 trace 消息的 status 设为 "done"，写入 summaryScore
```

### 7.5 复用 prepare-types.ts

为避免类型重复，把 trace 节点数据类型从 `agent-trace.tsx` 抽出到 `prepare-types.ts`，供准备和面试两端共用。改名后保持原导出，不破现有引用。

---

## 8. SSE 事件契约（完整版）

### 8.1 准备阶段（不变）

```
event: node_start    data: { node, label }
event: node_token    data: { node, text }
event: node_done     data: { node, elapsed_ms, chain?, need_direction? }
event: done          data: { jd_context, prepared_questions, summary, direction }
event: error         data: { message, code }
```

### 8.2 面试阶段（新增 node_*，其他保留）

```
# 一轮答题的典型事件序列（chain = ["evaluator", "followup"]）
event: node_start    data: { node: "master", label: "MASTER" }
event: node_token    data: { node: "master", text: "..." }              # master Phase 1 推理 bullet
event: node_done     data: { node: "master", elapsed_ms: 280, chain: ["evaluator", "followup"] }
event: node_start    data: { node: "evaluator", label: "评估" }
event: node_token    data: { node: "evaluator", text: "..." }
event: node_done     data: { node: "evaluator", elapsed_ms: 580, summary_score: 7.4 }
event: node_start    data: { node: "followup", label: "面试官 · 追问" }
event: delta         data: { text: "..." }                              # 追问文本（现有事件，保留）
event: delta         data: { text: "..." }
event: node_done     data: { node: "followup", elapsed_ms: 1240 }
event: state         data: { stage, question_count, total_questions }
event: report?       data: { ... }                                       # 仅 chain 含 closing 时
event: done          data: {}
```

前端通过 `node_done` 携带的 `chain` 字段在 master 完成后立刻知道后续会有哪些节点，可以提前在 trace UI 上渲染 pending 占位（和 prepare 阶段一致）。

---

## 9. 错误处理

| 场景 | 处理 |
|------|------|
| master Phase 1 流式失败 | 跳过 Phase 1，直接走 Phase 2 结构化决策；SSE 上 master 节点的 node_token 为空，但 node_done 仍正常发出 chain |
| master Phase 2 结构化决策失败 | fallback chain = `["evaluator", "followup"]`（若 question_count 已达上限则 `["closing"]`）；记 `log.error("master_decision_failed", ...)` |
| master 输出 chain 非法（空 / 含非法节点 / 末节点不合法） | 按 §6.2 合法性约束修正，记 `log.warning("master_chain_invalid", ...)` |
| evaluator LLM 调用失败 | 节点 passthrough，state 不追加 turn_evaluations 这条；SSE 仍发 node_done（额外字段 `error: true`），前端 trace 节点显示降级文案"评估暂未生成"；后续 chain 节点继续执行 |
| followup / ask_question 节点失败 | 沿用现有 error 事件路径，前端整轮失败提示 |
| closing 节点失败 | report 不生成；用户看到「面试已结束」简短提示；记 error 日志 |
| report_node 聚合时 turn_evaluations 完全为空 | 降级走旧路径：LLM 整场评估（保留 `REPORT_SYSTEM_PROMPT` 作为 fallback prompt） |
| 准备阶段错误 | 沿用 Phase 3 现有降级路径，不变 |

所有 fallback 必须 `log.warning` 或 `log.error`，符合项目「fallback 必须记录日志」规范。

---

## 10. 测试要求

### 10.1 后端

| 测试 | 类型 |
|------|------|
| `master_node` 首轮（question_count==0）chain 强制为 `["ask_question"]` | 单元 |
| `master_node` 题目耗尽且追问耗尽时 chain 强制为 `["closing"]` | 单元 |
| `master_node` 正常路径 chain 包含 evaluator 和 followup/ask_question | 单元 |
| `master_node` Phase 1 流式 bullet 生成 | 单元 |
| `master_node` Phase 2 结构化决策失败时 fallback chain | 单元 |
| `master_node` 非法 chain 修正逻辑（空 / 末节点非法 / 含非法节点） | 单元 |
| `evaluator_node` 正常路径写入 turn_evaluations | 单元 |
| `evaluator_node` LLM 失败时 passthrough 且记日志 | 单元 |
| `followup_node` 流式生成追问文案 | 单元 |
| `report_node` 用 turn_evaluations 聚合的平均分计算（含稀疏轮次） | 单元 |
| `report_node` turn_evaluations 完全为空时降级 | 单元 |
| `interviewer/graph.py` chain 路由（evaluator → followup / evaluator → ask_question / 仅 closing） | 单元 |
| `stream_interviewer_turn_events` 发出完整 node_*/delta/state/done 序列 | 集成 |
| `/api/v1/interview/turn` SSE 字节流端到端 | 集成 |
| 移除节点后的 InterviewState 字段瘦身（删除字段对其他代码无影响） | 集成 |

### 10.2 前端

| 测试 | 类型 |
|------|------|
| TurnTraceCard running/done 状态渲染 | 单元 |
| InterviewChat 消息流中 trace + assistant 占位顺序正确 | 单元 |
| streamInterviewChat onTraceNode 回调被各事件触发 | 单元 |
| PreparationCard 从 messages 流渲染（顶部固定 DOM 节点已移除） | 单元 |
| 一条 user → trace → assistant 的整体 e2e（用 mock SSE） | 集成 |

---

## 11. 风险与缓解

| 风险 | 缓解 |
|------|------|
| master + evaluator 新增 2 次 LLM 调用 / 轮，总延迟显著上升 | 两者都流式输出，第一个可见 token 在 200-300ms 内；master 用快速模型（haiku 4.5）；总延迟若仍超 6s 启动 evaluator/interviewer 真并行化（Phase 5）|
| master Phase 1 偶发输出 JSON 或结构化标记，污染 trace bullet | Phase 1 prompt 显式约束「只输出 1-2 句中文，不能输出 JSON / 不能用 markdown」；解析检测到异常格式时丢弃 bullet 文案，仍按 Phase 2 决策继续 |
| master chain 误判导致 evaluator 漏跑过多 → report 聚合分母过小 | §6.2 合法性约束 + monitoring：若整场 evaluator 跑数 < 总轮数 50%，report 降级到旧 LLM 整场评估路径 |
| 移除 opening/briefing 节点后历史 session 的 stage 字段语义变化 | DB CheckConstraint 仍允许 opening/interview/closing 三值；新逻辑只写 interview/closing；旧记录展示时由前端兼容显示 |
| messages 数组里掺入 trace 类型可能破坏现有渲染逻辑（如复制聊天记录） | `handleCopyChat` 与 progress pill 计算等位置增加 `m.role === "trace"` 过滤 |
| 准备卡迁移后 sessionStorage 契约未变，但 UI 顺序变了 | PreparationCard 组件接口不变，只换插入位置；test 同步更新 |
| turn_evaluations 聚合算法（平均分）对短回答不公平 | 算法明确写成"按维度取均值，按实际有评估的轮次为分母"；不做加权；后续如需调整在 Phase 5 单独迭代 |
| 接口契约虽然没变（TurnRequest / SSE 事件名），但 stage 字段语义改变可能影响前端 progress | 前端 progress pill 改为只依赖 question_count / total_questions，不依赖 stage 字段判断 |

---

## 12. 实施分批建议（供后续 plan 拆分参考）

| 批次 | 内容 |
|------|------|
| Batch A · 后端清理 | 移除 opening/briefing/decide_next 节点 + 配套 prompts/路由/state 字段 + 删除对应测试 |
| Batch B · 后端核心 | 新增 master_node + evaluator_node + chain 路由 + followup_node 重做 + report_node 聚合改造 + 单元测试 |
| Batch C · 后端 SSE | stream_interviewer_turn_events 改造发 node_* 事件 + 集成测试 + /api/v1/interview/turn 端到端 |
| Batch D · 前端契约 | streamInterviewChat onTraceNode 扩展 + prepare-types.ts 抽取 + 测试 |
| Batch E · 前端 UI | PreparationCard 迁移到 messages 流 + 新增 TurnTraceCard + InterviewChat 消息流改造 + handleCopyChat 等过滤 |
| Batch F · 端到端联调 | 完整一轮答题 e2e + 5 题全流程 + chain 多分支路径验证 + report 聚合验证 |

后续 plan 文档会按以上批次展开为 task list。

---

## 13. 阶段 5+ 预留

- evaluator 与 interviewer 真正并行（asyncio.gather 或 LangGraph parallel branches）—— 若总延迟成为瓶颈
- 长短期记忆 / 偏好 agent 接入（原 Phase 3 spec 预留）
- 真题库 MCP server（原 Phase 3 spec 预留）
- turn_evaluations 历史对比（Coach 页展示"上次同类题对比 +0.8"）
