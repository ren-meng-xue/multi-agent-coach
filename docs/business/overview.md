# Multi-Agent Coach 业务全景

依赖：[multi-agent-interview.md](multi-agent-interview.md) | [prepare-flow.md](prepare-flow.md) | [coach-flow.md](coach-flow.md)

AI 模拟面试教练系统，帮助候选人针对目标岗位进行全流程面试练习，并通过跨 session 的候选人画像积累持续提供个性化反馈。

---

## 1. 五阶段产品流程

```
用户选岗位 / 上传 JD
        │
        ▼
┌───────────────────┐
│  1. Prepare 阶段   │  ← /coach 页面
│  生成面试题库       │
│  解析 JD + 出题    │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  2. Interview 阶段 │  ← /interview 页面
│  Chief Interviewer │
│  多 Agent 对话面试  │
└────────┬──────────┘
         │ (每轮同步)
         ▼
┌───────────────────┐
│  3. Evaluate 阶段  │  ← 嵌在 Interview 内部
│  评分 + 候选人画像  │
│  Evaluator Agent   │
└────────┬──────────┘
         │ (面试结束后)
         ▼
┌───────────────────┐
│  4. Coach 阶段     │  ← /coach 页面
│  复盘 + 训练计划   │
│  Coach Agent       │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  5. Report 阶段    │  ← /reports 页面
│  历史报告 + 趋势   │
└───────────────────┘
```

---

## 2. 系统架构层次

```
前端 (Next.js App Router)
  ├── /coach            → 选岗、上传 JD、查看复盘
  ├── /interview/[id]   → 实时对话面试（SSE 流式输出）
  └── /reports          → 历史报告与长期趋势

API 层 (FastAPI)
  ├── POST /prepare/start         → 启动 prepare agent
  ├── POST /interview/start       → 创建 interview session
  ├── POST /interview/turn        → 提交一轮对话（触发 Chief Agent）
  ├── POST /coach/review          → 主动触发 Coach Agent 复盘
  └── GET  /reports/{session_id}  → 获取复盘报告

Agent 层 (LangGraph)
  ├── Prepare Graph        → JD 解析 + 题库生成
  ├── Chief Interviewer    → ReAct Loop，调度子 Agent
  │   ├── Evaluator Agent  → 分析回答质量 + 更新候选人画像
  │   └── Designer Agent   → 设计题目或追问
  └── Coach Agent          → 基于 candidate_memory 生成复盘

持久化层 (PostgreSQL + Redis)
  ├── interview_sessions   → session 基本信息
  ├── interview_turns      → 每轮对话记录
  ├── candidate_memory     → 跨 session 候选人画像（user 维度）
  └── user_qa_bank         → 用户上传的 Q&A 题库
```

---

## 3. 关键数据流

```
用户提交回答
    │
    ▼ POST /interview/turn
    │
    ▼ Chief Interviewer (ReAct Loop, max 4 iter)
    │   ├─ evaluate_answer() → Evaluator Agent
    │   │       ├─ 打分 (TurnEvaluation)
    │   │       ├─ 更新 candidate_memory (DB)
    │   │       └─ 返回 report_text 给 Chief
    │   │
    │   └─ design_question() → Designer Agent
    │           ├─ LLM 生成题目
    │           ├─ 规则校验（去重、不万金油）
    │           └─ 返回 question_text 给 Chief
    │
    ▼ Chief 生成最终回复文本
    │
    ▼ SSE 流式推送至前端
```

---

## 4. 核心实体

| 实体         | 表名                 | 说明                                           |
| ------------ | -------------------- | ---------------------------------------------- |
| 用户         | `users`              | Clerk 认证，user_id 是 Clerk sub               |
| 面试 session | `interview_sessions` | 一次完整面试，关联 target_role + jd            |
| 对话轮次     | `interview_turns`    | 每轮用户回答 + AI 问题 + 评估结果              |
| 候选人画像   | `candidate_memory`   | 跨 session 累积，user 维度，JSONB 信号存储     |
| 题库         | `user_qa_bank`       | 用户上传的 Q&A，三类：technical / hr / project |

---

## 5. 文档索引

| 文档                                                 | 说明                                                |
| ---------------------------------------------------- | --------------------------------------------------- |
| [multi-agent-interview.md](multi-agent-interview.md) | Chief + Evaluator + Designer 三层 Agent 架构详解    |
| [prepare-flow.md](prepare-flow.md)                   | 备考准备阶段：JD 解析、题库生成、QA Bank            |
| [coach-flow.md](coach-flow.md)                       | 面试后复盘：Coach Agent、candidate_memory、训练计划 |
