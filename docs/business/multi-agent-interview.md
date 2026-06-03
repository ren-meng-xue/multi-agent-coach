# 多 Agent 面试系统（Chief + 子 Agent）

依赖：[overview.md](overview.md)

接口：`POST /interview/turn` → Chief Interviewer Agent → SSE 流式响应

---

## 1. 背景

传统"单 LLM + 状态机"设计中，面试官只是 prompt 切换，没有 agentic loop。本系统将面试官重构为**层次化多 Agent 架构**：

- Chief Interviewer 是主控 ReAct Agent，掌握对话节奏
- Evaluator / Designer 是专家子 Agent，接受 Chief 委托并独立执行

---

## 2. 整体架构

```
POST /interview/turn
        │
        ▼
┌─────────────────────────────────────────────────────┐
│                Chief Interviewer Agent               │
│                   (ReAct Loop, max 4 iter)           │
│                                                      │
│   load_context                                       │
│        │                                             │
│        ▼                                             │
│   chief_think ──────────────────── chief_respond     │
│        │ tool_call                      ▲            │
│        ▼                                │            │
│   chief_execute                     (no tools)       │
│        │                                             │
│        ├─ evaluate_answer ──────────────┐            │
│        ├─ design_question ──────────────┤            │
│        └─ query_profile  ──────────────┘            │
│                                    │                 │
│                               chief_think ◄──────────┘
└─────────────────────────────────────────────────────┘
         │                        │
         │ evaluate_answer        │ design_question
         ▼                        ▼
┌─────────────────┐    ┌──────────────────────┐
│  Evaluator Agent │    │  Question Designer    │
│                  │    │       Agent           │
│  analyze_answer  │    │                      │
│  update_profile  │    │  design → validate   │
│  respond         │    │  respond             │
└─────────────────┘    └──────────────────────┘
         │                        │
         ▼                        ▼
  candidate_memory (DB)     question_text (返回 Chief)
```

---

## 3. Chief Interviewer Agent

**文件**：`backend/app/agents/interviewer/chief.py`

**Graph**：`load_context → chief_think → [chief_execute → chief_think]* → chief_respond → END`

### 3.1 可用工具

| 工具                               | 委托目标                | 说明                           |
| ---------------------------------- | ----------------------- | ------------------------------ |
| `evaluate_answer(answer, context)` | Evaluator Agent         | 分析本轮回答质量，返回评估报告 |
| `design_question(focus, context)`  | Designer Agent          | 设计一道题目或追问             |
| `query_profile()`                  | Evaluator Agent（只读） | 获取候选人当前画像摘要         |

### 3.2 行为规则（System Prompt 要点）

```
收到用户回答 → 必须先调用 evaluate_answer
                │
                ▼
         读取 report_text
                │
        ┌───────┴────────┐
        │                │
   答得好 / 覆盖全       有明显缺口
        │                │
        ▼                ▼
  design_question    design_question
  (新话题题目)        (追问型)
        │
        └──── 若题满 or 用户要求结束 → chief_respond (收尾)
```

**硬约束**：

- 一次只说一件事（只问一个问题）
- 不万金油追问（"能展开说说吗"类）
- 不无脑赞美
- loop 超过 4 次 → 降级直接出题

### 3.3 防死循环

`chief_iteration` 计数器随 state 传递，超过 `MAX_ITER = 4` 时 `chief_execute` 跳过工具直接进入 `chief_respond`。

---

## 4. Evaluator Agent

**文件**：`backend/app/agents/evaluator/`

**Graph**：`analyze_answer → update_profile → respond_to_chief → END`

```
Chief 调用 evaluate_answer(answer, context)
        │
        ▼
  analyze_answer
    ├─ LLM 打分（TurnEvaluation Pydantic model）
    ├─ 提取行为信号（signal extraction）
    └─ 输出 scoring
        │
        ▼
  update_profile
    ├─ 读取 candidate_memory（DB，user 维度）
    ├─ 合并新 signals / 更新 weakness_tags
    └─ 写回 candidate_memory
        │
        ▼
  respond_to_chief
    └─ 生成 report_text（自然语言，帮 Chief 决策追问或出新题）
```

**State 字段**：

| 字段                   | 类型                     | 说明                    |
| ---------------------- | ------------------------ | ----------------------- |
| `session_id`           | str                      | 当前 session            |
| `latest_answer`        | str                      | 用户本轮回答            |
| `conversation_context` | str                      | 历史对话摘要            |
| `existing_profile`     | CandidateProfile \| None | DB 中已有画像           |
| `scoring`              | TurnEvaluation           | 本轮打分结果            |
| `updated_profile`      | CandidateProfile         | 合并后画像              |
| `report_text`          | str                      | 返回给 Chief 的决策建议 |

---

## 5. Question Designer Agent

**文件**：`backend/app/agents/designer/`

**Graph**：`design → validate → respond_to_chief → END`

```
Chief 调用 design_question(focus, context)
        │
        ▼
  design
    └─ LLM 生成题目/追问文本
        │
        ▼
  validate（规则校验，非 LLM）
    ├─ 不万金油？（拒绝"能展开说说吗"）
    ├─ 不重复已问过的题目？
    └─ 在目标岗位范围内？
        │
        ▼
  respond_to_chief
    └─ 返回 {question_text, question_category, focus_area}
```

**State 字段**：

| 字段                 | 类型             | 说明                             |
| -------------------- | ---------------- | -------------------------------- |
| `focus`              | str              | Chief 指定的出题方向             |
| `target_role`        | str              | 目标岗位                         |
| `candidate_profile`  | CandidateProfile | 当前候选人画像（影响难度）       |
| `previous_questions` | list[str]        | 已问题目列表（去重用）           |
| `evaluator_report`   | dict \| None     | Evaluator 的建议（影响追问方向） |
| `question_text`      | str              | 生成的题目文本                   |

---

## 6. SSE 输出格式

Chief `chief_respond` 节点通过 SSE 流式推送：

```
data: {"type": "token", "content": "..."}
data: {"type": "designed_question", "question": "..."}
data: {"type": "summary_score", "score": {...}}
data: {"type": "chief_tool_calls", "calls": [...]}
data: {"type": "done"}
```

前端在 Trace Panel 中展示 `chief_tool_calls` 和 `summary_score`，在对话气泡中展示 `content`。

---

## 7. 关键文件索引

| 文件                                      | 说明                     |
| ----------------------------------------- | ------------------------ |
| `backend/app/agents/interviewer/graph.py` | Chief graph 定义         |
| `backend/app/agents/interviewer/chief.py` | Chief ReAct loop 逻辑    |
| `backend/app/agents/evaluator/`           | Evaluator Agent          |
| `backend/app/agents/designer/`            | Designer Agent           |
| `backend/app/services/interview_turn.py`  | turn 服务层，调度 Chief  |
| `frontend/lib/interview-chat.ts`          | SSE 客户端，解析推送事件 |
