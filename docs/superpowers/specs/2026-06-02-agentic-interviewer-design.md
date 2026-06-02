# Chief + 专家子 Agent 多智能体面试系统 设计文档

- 日期：2026-06-02
- 分支：feat/agentic-interviewer
- 范围：interviewer graph 重构 + Evaluator Agent + Question Designer Agent + eval 对比

---

## 一、背景与问题

### 1.1 当前状态

项目名为 multi-agent-coach，但实际的"multi-agent"名不副实：

- `prepare`、`interviewer`、`coach` 三个 LangGraph graph 互不调用，由 FastAPI 路由层拼接
- `interviewer` 内部是 state machine + LLM 路由：master_node 输出 chain 列表 → 节点依次执行 → END，没有 agentic loop
- `candidate_profile` 只是 evaluator_node 写入的 TypedDict，不是独立 agent
- 三者之间没有消息交互

### 1.2 为什么这不是 multi-agent

严格定义下的 multi-agent 系统需要：

1. 多个独立的 LLM 角色，各有自己的 prompt / 目标 / 上下文
2. 角色之间通过**消息交互**（不是共享 state、不是函数调用链）
3. 每个角色内部有 agentic loop：think → act → observe → think

当前 interviewer 只满足条件 1（多个 prompt 的角色），不满足 2 和 3。

### 1.3 本期目标

把 interviewer 从 state machine 改造为**主面试官 + 2 个专家子 agent** 的层次化多 agent 系统：

- **Chief Interviewer**：ReAct-loop agent，调度子 agent、控制对话节奏
- **Evaluator Agent**：独立的评估 + 候选人画像 agent，回答 Chief 的分析查询
- **Question Designer Agent**：独立的出题 agent，回答 Chief 的设计查询

用 eval 定量对比 agentic vs state machine 的行为差异。

---

## 二、设计原则

1. **真 agent 化**：子 agent 是独立 compiled graph + 独立 LLM + 独立 state，不是 passive 节点
2. **工具内部分析化**：Chief 的工具是"委托给专家"，不是"面向用户的对话行为"
3. **向后兼容**：现有 API 接口不变、前端不变、CandidateMemory 表结构不变
4. **回退安全**：ReAct loop 超限时降级到最简单的 ask_question；废弃代码标记但不删除
5. **不做的事**：跨 session agent 持续运行、reflexion、agent-as-service 常驻——留给后续

---

## 三、架构

### 3.1 整体结构

```
FastAPI /interview/turn
        │
        ▼
┌─────────────────────────────────────────────────┐
│              Chief Interviewer Agent              │
│              (ReAct Loop, max 4 iter)            │
│                                                  │
│  load_context → chief_think ──→ chief_respond    │
│                      │         (自然语言输出)      │
│                      │ tool_call                  │
│                      ▼                            │
│               chief_execute ──────────────┐       │
│                      │                    │       │
│                      │ evaluate_answer ───┤       │
│                      │ design_question ───┤       │
│                      │ query_profile ─────┤       │
│                      └──→ chief_think ◄───┘       │
└─────────────────────────────────────────────────┘
        │                      │
        │ evaluate_answer      │ design_question
        ▼                      ▼
┌───────────────┐    ┌───────────────────┐
│Evaluator Agent│    │Question Designer  │
│               │    │     Agent          │
│ analyze_answer│    │                   │
│ update_profile│    │ design → validate │
│ respond       │    │ respond           │
└───────────────┘    └───────────────────┘
```

### 3.2 Chief Agent（`backend/app/agents/interviewer/chief.py`）

**Graph**：`load_context → chief_think → [tool_call → chief_execute → chief_think]* → chief_respond → END`

**工具**:

| 工具                               | 委托目标               | 说明                       |
| ---------------------------------- | ---------------------- | -------------------------- |
| `evaluate_answer(answer, context)` | Evaluator Agent        | 分析回答质量，返回评估报告 |
| `design_question(focus, context)`  | Designer Agent         | 设计一个问题或追问         |
| `query_profile()`                  | Evaluator Agent (只读) | 快速获取候选人画像摘要     |

**System Prompt 要点**:

- 收到回答必须先 evaluate_answer
- 基于评估决定：答得好出新题 / 有缺口追问 / 题满或要求结束则收尾
- 一次只说一件事
- 不万金油追问、不赞美

**防死循环**：`chief_iteration` 上限 4，超限降级到 ask_question

### 3.3 Evaluator Agent（`backend/app/agents/evaluator/`）

现有 `evaluator_node` 已实现了 Phase 4+ 的打分 / 信号提取 / 画像累积。改造为独立 agent：

**Graph**：`analyze_answer → update_profile → respond_to_chief → END`

**State**：

```python
class EvaluatorState(TypedDict, total=False):
    session_id: str
    user_id: str
    target_role: str
    latest_answer: str
    conversation_context: str
    existing_profile: CandidateProfile | None
    scoring: TurnEvaluation
    updated_profile: CandidateProfile
    report_text: str              # 新增：给 Chief 的自然语言决策建议
```

**与现状的关系**：

- 核心逻辑迁移自 `nodes.py:evaluator_node`
- 保留 `_EvaluatorScoring` Pydantic model
- 保留 `upsert_candidate_memory` 持久化
- 新增 `report_text`：自然语言总结，帮 Chief 决策"该追问还是出题"

### 3.4 Question Designer Agent（`backend/app/agents/designer/`）

**Graph**：`design → validate → respond_to_chief → END`

- `design`: LLM 生成题目/追问文本
- `validate`: 规则检查（非 LLM）——不万金油、不重复已问题、不越界
- `respond_to_chief`: 返回标准化结构

**State**：

```python
class DesignerState(TypedDict, total=False):
    focus: str
    target_role: str
    candidate_profile: CandidateProfile
    jd_context: dict | None
    previous_questions: list[str]
    evaluator_report: dict | None
    question_text: str
    question_category: str
    focus_area: str
```

**与现状的关系**：

- prepared_questions 优先级保留（准备阶段题目 > LLM 设计）
- 追问 prompt 保留现有 FOLLOWUP_SYSTEM_PROMPT 的反万金油准则
- 新增 candidate_profile 感知：beginner 避免追问分布式/benchmark

### 3.5 消息协议

```
Chief                              Evaluator
  │                                   │
  │ evaluate_answer({                 │
  │   latest_answer,                  │
  │   conversation_context,           │
  │   existing_profile                │
  │ })                                │
  │ ─────────────────────────────────→│
  │                                   │ analyze + score + persist
  │ ←─────────────────────────────────│
  │ {                                 │
  │   scoring: TurnEvaluation,        │
  │   updated_profile,                │
  │   report_text: "回答涵盖了CAP理论  │
  │   但没有给出量化指标,建议追问QPS"   │
  │ }                                 │
  │                                   │
  │                    Designer        │
  │  design_question({                │
  │    focus: "量化追问",              │
  │    candidate_profile,             │
  │    evaluator_report               │
  │  })                               │
  │ ─────────────────────────────────→│
  │                                   │ design + validate
  │ ←─────────────────────────────────│
  │ {                                 │
  │   question_text: "你提到延迟降低   │
  │  但没有给具体数据,优化前后的       │
  │  QPS 对比是多少？",                │
  │   category: "technical",          │
  │   focus_area: "性能优化"           │
  │ }                                 │
```

实现方式：函数调用传参 + 返回值（不引入独立 thread/checkpointer 跨 agent 通信）

---

## 四、State 变更（`backend/app/agents/interviewer/state.py`）

```python
class InterviewState(TypedDict, total=False):
    # === 现有字段（全部保留）===
    session_id: str
    user_id: str
    is_first_time: bool
    target_role: str
    target_company: str
    user_background: str
    messages: list[BaseMessage]
    stage: InterviewStage
    question_count: int
    total_questions: int
    followup_count: int
    max_followups: int
    assistant_message: str
    jd_context: dict[str, Any] | None
    prepared_questions: list[dict[str, Any]]
    current_question_index: int
    chain: list[str]
    master_reason: str
    turn_evaluations: list[TurnEvaluation]
    candidate_profile: CandidateProfile
    followup_focus: str
    qa_bank_items: list[dict[str, Any]] | None
    resume_text: str | None
    report: dict[str, Any]

    # === 新增 Chief ReAct 相关 ===
    chief_iteration: int            # 当前 loop 迭代计数，max=4
    chief_thoughts: list[str]       # 每步推理记录（供 SSE 透传）
    chief_tool_results: list[dict]  # 本轮工具调用结果缓存
    evaluator_report: dict | None   # 最新一次 evaluate_answer 的返回
    designer_output: dict | None    # 最新一次 design_question 的返回
```

`TurnEvaluation` 和 `CandidateProfile` 不变（Phase 4+ 已定义）。

---

## 五、SSE 事件透传

### 5.1 新增节点

| 节点            | label  | 事件                                                  |
| --------------- | ------ | ----------------------------------------------------- |
| `chief_think`   | "思考" | node_start / node_token / node_done                   |
| `chief_execute` | —      | 不发送给前端（内部工具调用，用户无需看到）            |
| `chief_respond` | "回复" | node_start / token / node_done（复用现有 token 通道） |

### 5.2 兼容性

- 现有 `node_start` / `node_token` / `node_done` 事件格式不变
- `evaluator` / `master` 节点不再出现在 SSE 流中，前端调度台显示改为 `chief_think` / `chief_respond`
- `token` 事件（面试官回复文本）仍走现有 delta 通道

---

## 六、文件改动物理清单

### 新增

| 文件                                              | 内容                                                        |
| ------------------------------------------------- | ----------------------------------------------------------- |
| `backend/app/agents/evaluator/__init__.py`        | Evaluator agent 导出                                        |
| `backend/app/agents/evaluator/state.py`           | EvaluatorState                                              |
| `backend/app/agents/evaluator/prompts.py`         | Evaluator system prompts                                    |
| `backend/app/agents/evaluator/nodes.py`           | analyze_answer / update_profile / respond_to_chief          |
| `backend/app/agents/evaluator/graph.py`           | 编译 + 导出 build function                                  |
| `backend/app/agents/designer/__init__.py`         | Designer agent 导出                                         |
| `backend/app/agents/designer/state.py`            | DesignerState                                               |
| `backend/app/agents/designer/prompts.py`          | Designer system prompts                                     |
| `backend/app/agents/designer/nodes.py`            | design / validate / respond_to_chief                        |
| `backend/app/agents/designer/graph.py`            | 编译 + 导出 build function                                  |
| `backend/app/agents/interviewer/chief.py`         | chief_think / chief_execute / chief_respond 节点 + 工具定义 |
| `backend/app/agents/interviewer/chief_prompts.py` | CHIEF_SYSTEM_PROMPT                                         |

### 修改

| 文件                                        | 改动                                                           |
| ------------------------------------------- | -------------------------------------------------------------- |
| `backend/app/agents/interviewer/state.py`   | 新增 5 个 chief 相关字段                                       |
| `backend/app/agents/interviewer/graph.py`   | 重构图结构；保留 SSE 流层；废弃 route*after*\*                 |
| `backend/app/agents/interviewer/nodes.py`   | 标记 deprecated 的代码块；保留 load_context / report / closing |
| `backend/app/agents/interviewer/prompts.py` | 标记废弃 MASTER\_\* / FOLLOWUP_SYSTEM_PROMPT 迁移至 designer   |

### 不动的

- `backend/app/api/v1/prepare.py`
- `backend/app/api/v1/interview.py`
- `backend/app/services/interview_turn.py`（入口签名不变）
- `backend/app/services/candidate_memory.py`
- `backend/app/agents/prepare/`
- `backend/app/agents/coach/`
- `backend/app/models/core.py`
- 所有前端文件

---

## 七、风险与回退

| 风险                     | 触发                                                | 缓解                                                      |
| ------------------------ | --------------------------------------------------- | --------------------------------------------------------- |
| ReAct loop 增加延迟      | 每轮多 1 次 LLM 调用（Chief think）                 | Chief think 用 fast model；上限 4 轮                      |
| 追问质量退化             | Agent 决策不如 state machine                        | Eval 定量对比；退化则调 prompt                            |
| Evaluator 独立后信息丢失 | Chief→Evaluator 传参不完整                          | report_text 字段做自然语言兜底                            |
| 前端调度台节点变化       | chief_think / chief_respond 替代 master / evaluator | 兼容 node_start/node_done 格式，label 变化不影响渲染      |
| 1 周超期                 | —                                                   | Day 1-4 agentic core 为硬截止；eval 数据集可减至 10 cases |
| 废弃代码未清理           | —                                                   | 标记 # deprecated 保留，eval 通过后再清理                 |

---

## 八、测试策略

### 后端单测

- `tests/unit/test_evaluator_agent.py`：独立调用 Evaluator，验证 scoring + report_text 正确
- `tests/unit/test_designer_agent.py`：独立调用 Designer，验证 validate 规则 + focus 感知
- `tests/unit/test_chief_reasoning.py`：mock Evaluator/Designer 返回，验证 Chief 决策链（evaluate→design→respond）
- `tests/unit/test_chief_safety.py`：ReAct 超限降级、终止词识别、首轮 skip evaluate

### 集成验证

- 完整面试对话 3-5 轮，确认不崩、调度台显示、报告产出
- 刷新页面恢复会话

### 不写

- e2e Playwright — 不走

---

## 九、明确不做

1. 跨 session agent 持续运行 / 常驻
2. Reflexion 反思 / self-correction
3. Checkpointer thread 跨 agent 通信（当前用函数调传参）
4. Candidate model 作为独立 HTTP 端点
5. 修改前端 / Coach / Prepare
6. 修改数据库 schema

---

## 十、交付检查表

- [ ] Evaluator Agent 独立可调用，返回正确结构
- [ ] Designer Agent 独立可调用，返回正确结构
- [ ] Chief ReAct loop 正常收敛（不超限）
- [ ] SSE 事件前端不报错
- [ ] 完整面试流程 3-5 轮无崩溃
- [ ] 现有 pytest 套无回归
- [ ] ruff / mypy 通过
- [ ] eval baseline vs experiment 指标对比可跑
- [ ] 设计文档（本文）完成
