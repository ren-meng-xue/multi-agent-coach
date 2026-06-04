# Trace v4 Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Prepare 和 Interview trace 前端渲染升级到 v4 原型：Prepare 节点使用结构化内容区，Interview 下一题以 Hero 卡片独立置顶展示，trace 默认折叠，并补齐后端 SSE 结构化字段。

**Architecture:** 后端只在 `stream_prepare_events` 的 `node_done` 分支补充结构化 payload，不改 LangGraph 图结构；前端扩展 trace 类型与 SSE 映射，将 `TraceNode` 内容区按节点 id 分发渲染，同时把 TurnTraceCard 内的出题展示上移到 AI 消息层的 `HeroQuestionCard`。

**Tech Stack:** Python 3.12 / FastAPI / LangGraph SSE；Next.js / React / TypeScript / Tailwind CSS / Vitest / Testing Library

**Spec 文档:** `docs/superpowers/specs/2026-06-03-trace-v4-refactor-design.md`

**参考原型:** `html/trace-design-v4.html`

---

## File Map

| 文件 | 职责 | 改动类型 |
| --- | --- | --- |
| `backend/app/agents/prepare/graph.py` | Prepare SSE `node_done` payload 补结构化字段 | 修改 |
| `frontend/lib/prepare-types.ts` | `TraceNodeData` / `PrepareSSEEvent["data"]` 增加可选字段 | 修改 |
| `frontend/app/interview/_components/trace-node.tsx` | 内容 zone 按节点类型分发渲染 | 修改 |
| `frontend/app/interview/_components/preparation-card.tsx` | 新增 `summary` prop 和 SummaryBlock | 修改 |
| `frontend/app/interview/_components/turn-trace-card.tsx` | 默认折叠，移除 designedQuestion header 分支 | 修改 |
| `frontend/app/interview/_components/interview-chat.tsx` | 独立渲染 HeroQuestionCard，保存并传递 prepare summary | 修改 |
| `frontend/app/interview/_components/trace-node.test.tsx` | 补 Prepare 节点结构化内容测试 | 修改 |
| `frontend/app/interview/_components/preparation-card.test.tsx` | 补 summary 有/无测试 | 修改 |
| `frontend/app/interview/_components/turn-trace-card.test.tsx` | 补默认折叠与展开测试 | 修改 |
| `frontend/app/interview/_components/interview-chat.test.tsx` | 补 HeroQuestionCard 集成测试；若不存在则新建 | 修改/新建 |

---

## Phase 1 — 后端 SSE 结构化字段

### Task 1: `stream_prepare_events` 的 Prepare `node_done` 分支补字段

**Files:**

- Modify: `backend/app/agents/prepare/graph.py`

- [ ] 找到 `stream_prepare_events` 中生成 `node_done` payload 的分支，确认当前已能拿到 `ev_node`、`node_state` / `state` 等上下文。
- [ ] 在 `memory_search` 的 `node_done` payload 中追加：
  ```python
  weak_areas = state.get("weak_areas") or []
  payload["weak_areas"] = weak_areas
  payload["record_count"] = len(weak_areas)
  ```
- [ ] 在 `research_agent` 的 `node_done` payload 中，从 `job_intel` 读取：
  ```python
  trace = (job_intel or {}).get("_trace") or {}
  payload["react_iterations"] = trace.get("iterations") or 0
  payload["react_tool_count"] = len(trace.get("tools_used") or [])
  ```
- [ ] 同一分支补充 `company_name`：优先 `job_intel["company_profile"]["name"]`，无值时用可用 summary 截取前 20 字兜底。
- [ ] 同一分支补充 `gaps`：读取 `job_intel["resume_match"]["gaps"][:3]`，缺失时给空数组。
- [ ] 在 `jd_analysis` 的 `node_done` payload 中，从 `node_state["jd_context"]` 读取：
  ```python
  payload["jd_company"] = jd_context.get("company")
  payload["jd_role"] = jd_context.get("role")
  payload["jd_difficulty"] = jd_context.get("difficulty")
  payload["jd_key_skills"] = (jd_context.get("key_skills") or [])[:6]
  ```
- [ ] 在 `question_gen` 的 `node_done` payload 中统计 `node_state["prepared_questions"]`：
  ```python
  payload["question_stats"] = {
      "technical": ...,
      "behavioral": ...,
      "system_design": ...,
  }
  payload["question_total"] = len(prepared_questions)
  ```
  只保留存在且计数大于 0 的分类，避免前端展示零项。
- [ ] 字段命名保持 snake_case，交由现有前端 SSE 映射转 camelCase。

### Task 2: 后端验证

- [ ] 运行 Ruff：
  ```bash
  cd backend
  uv run ruff check app/agents/prepare/graph.py
  ```
- [ ] 运行 Prepare 相关测试：
  ```bash
  uv run pytest tests/unit/test_research_agent.py -v
  ```
- [ ] 如已有 `graph.py` 或 prepare SSE 单测，补充/运行覆盖 `node_done` payload 的测试；没有合适测试时，在最终交付说明测试缺口。

---

## Phase 2 — 前端类型与 SSE 映射

### Task 3: 扩展 Prepare trace 类型

**Files:**

- Modify: `frontend/lib/prepare-types.ts`

- [ ] 在 `TraceNodeData` 增加可选字段：
  ```typescript
  weakAreas?: string[];
  recordCount?: number;
  reactIterations?: number;
  reactToolCount?: number;
  companyName?: string;
  gaps?: string[];
  jdCompany?: string;
  jdRole?: string;
  jdDifficulty?: string;
  jdKeySkills?: string[];
  questionStats?: Record<string, number>;
  questionTotal?: number;
  ```
- [ ] 在 `PrepareSSEEvent["data"]` 增加同名可选字段对应后端 snake_case payload。
- [ ] 保持全部字段可选，不改变现有调用方的必填 contract。

### Task 4: SSE handler 写入 `TraceNodeData`

**Files:**

- Modify: `frontend/app/interview/_components/interview-chat.tsx`

- [ ] 找到 Prepare `node_done` 事件映射，将后端字段写入 trace node：
  ```typescript
  weakAreas: data.weak_areas,
  recordCount: data.record_count,
  reactIterations: data.react_iterations,
  reactToolCount: data.react_tool_count,
  companyName: data.company_name,
  gaps: data.gaps,
  jdCompany: data.jd_company,
  jdRole: data.jd_role,
  jdDifficulty: data.jd_difficulty,
  jdKeySkills: data.jd_key_skills,
  questionStats: data.question_stats,
  questionTotal: data.question_total,
  ```
- [ ] 在 Prepare `done` event 中保存已有 `summary` 字段到 prepare 状态。
- [ ] 向 `PreparationCard` 传递 `summary`。

### Task 5: 前端类型验证

- [ ] 运行：
  ```bash
  cd frontend
  pnpm typecheck
  ```

---

## Phase 3 — `TraceNode` 内容 zone 重构

### Task 6: 提取 `renderContent()` 分发结构

**Files:**

- Modify: `frontend/app/interview/_components/trace-node.tsx`

- [ ] 保留 timeline 外框、dot、line、badge、时间戳等现有结构。
- [ ] 在文件内提取局部函数 `renderContent()`，按 `id` 分发：
  ```typescript
  switch (id) {
    case "memory_search":
      return <MemoryContent ... />;
    case "research_agent":
      return <ResearchContent ... />;
    case "jd_analysis":
      return <JdContent ... />;
    case "question_gen":
      return <QuestionContent ... />;
    case "evaluator":
      return <EvaluatorContent ... />;
    case "chief_think":
      return <ChiefThinkContent ... />;
    case "followup":
    case "ask_question":
      return <FollowupContent ... />;
    default:
      return <TokenContent ... />;
  }
  ```
- [ ] 不新增组件文件，所有 Content 函数作为文件内局部组件/函数。
- [ ] 将现有 `question_gen` / evaluator / chief / followup 条件块归并进对应函数。
- [ ] `TokenContent` 保留原有 tokens 文本渲染，作为所有异常数据的兜底。

### Task 7: Prepare 节点专属内容

**Files:**

- Modify: `frontend/app/interview/_components/trace-node.tsx`

- [ ] `MemoryContent`
  - running：显示 `正在读取历史表现...`
  - done：显示 `读取到 {recordCount} 条记录，薄弱点：`，`weakAreas.join("、")` 使用 `text-red-600 font-semibold` 内联显示。
  - 无 `weakAreas` 时显示 `暂无历史薄弱点记录`。
- [ ] `ResearchContent`
  - running：展示现有 `ReactToolTree`，保持实时展开。
  - done：展示 `{reactIterations} 轮 · {reactToolCount} 次工具调用` badge。
  - 有 `companyName` 时展示公司 badge。
  - 有 `gaps` 时展示红色 `Gap：{gaps.join(" · ")}` badge。
  - done 时 `ReactToolTree` 以 `isFinished=true` 折叠展示。
- [ ] `JdContent`
  - running：显示 `正在分析岗位需求...`
  - done：显示 `{jdCompany} · {jdRole} · 难度 {jdDifficulty}` 和 `jdKeySkills` badge 列表。
- [ ] `QuestionContent`
  - running：显示 `正在为你定制专属题目...`
  - done：显示 `已定制 {questionTotal} 道，面试中逐题呈现`，并追加存在的分类统计。
  - 分类文案映射：`technical` → `技术`，`behavioral` → `行为`，`system_design` → `系统设计`。
  - 样式使用 `text-xs text-slate-600`。

### Task 8: Interview 节点内容迁移

**Files:**

- Modify: `frontend/app/interview/_components/trace-node.tsx`

- [ ] `EvaluatorContent`：迁移现有评分大字、等级 badge、`latentSignals` / `missingDimensions` badge、结论一行，行为不变。
- [ ] `ChiefThinkContent`：将 `chiefToolCalls` 映射为中文 badge：
  ```typescript
  evaluate_answer -> 评估回答
  design_question -> 设计新题
  query_profile -> 读取画像
  ```
  running 或无数据时退回 `TokenContent`。
- [ ] `FollowupContent`：done 时显示 `追问方向：` + `missingDimensions.join(" · ")` 或 `followupFocus`，重点内容使用 `font-semibold text-slate-700`。
- [ ] `followup` / `ask_question` 数据均无时退回 `TokenContent`。

---

## Phase 4 — Interview 轮次 UI 重构

### Task 9: 新增文件内 `HeroQuestionCard`

**Files:**

- Modify: `frontend/app/interview/_components/interview-chat.tsx`

- [ ] 在文件内新增局部组件 `HeroQuestionCard`，不新增组件文件。
- [ ] 从 `TurnTraceCard` 数据提取 `designedQuestion`，在 AI 消息渲染层、`TurnTraceCard` 外部渲染。
- [ ] 渲染条件：
  ```typescript
  designedQuestion && status === "done" && !isOpening
  ```
- [ ] followup 判断：turn 内任一 node 有 `followupFocus` 则视为追问。
- [ ] badge 文案：followup 显示 `追问`；否则按 `designedCategory` 映射 `技术` / `行为` / `系统设计`。
- [ ] 样式对齐 spec：
  ```text
  bg-gradient-to-br from-[#f0fdf4] to-[#f0f9ff]
  border-[1.5px] border-[#6ee7b7] rounded-xl p-3.5 mb-4
  ```
- [ ] 题目正文使用 `text-sm font-semibold text-[#064e3b] leading-relaxed`。

### Task 10: `TurnTraceCard` 默认折叠并移除出题 header

**Files:**

- Modify: `frontend/app/interview/_components/turn-trace-card.tsx`

- [ ] 将 `internalExpanded` 初始值改为 `false`。
- [ ] toggle 文案改为：
  - 折叠态：`查看 AI 思考过程`
  - 展开态：`收起思考过程`
- [ ] 移除 header 内 `designedQuestion` 分支逻辑。
- [ ] opening 轮 header 文案保持不变。

---

## Phase 5 — Preparation Summary

### Task 11: `PreparationCard` 支持 summary

**Files:**

- Modify: `frontend/app/interview/_components/preparation-card.tsx`

- [ ] 新增 prop：
  ```typescript
  summary?: string;
  ```
- [ ] 在 `AgentTrace` 节点列表下方，当 `summary` 有值时渲染虚线分隔线：
  ```text
  border-t border-dashed border-slate-200 my-4
  ```
- [ ] 新增文件内 `SummaryBlock`：
  - 容器：`bg-[#fafaf9] border border-[#e7e5e4] rounded-xl p-3 mt-0`
  - 标题行：黑圆点 `w-4 h-4 rounded-full bg-[#1e293b]` + `准备完成 · AI 综合判断`
  - 正文：`text-xs text-[#57534e] leading-relaxed`

### Task 12: `interview-chat.tsx` 传递 summary

**Files:**

- Modify: `frontend/app/interview/_components/interview-chat.tsx`

- [ ] 在 Prepare `done` event 中读取 `data.summary`。
- [ ] 将 summary 存入当前 prepare trace 状态。
- [ ] 渲染 `PreparationCard` 时传入 `summary={...}`。
- [ ] 确认 `need_direction=true` 或未完成时不会误显示空 SummaryBlock。

---

## Phase 6 — 测试补充

### Task 13: `trace-node.test.tsx`

**Files:**

- Modify: `frontend/app/interview/_components/trace-node.test.tsx`

- [ ] 覆盖 `memory_search` done：展示记录数和红色薄弱点文本。
- [ ] 覆盖 `memory_search` done 但无 `weakAreas`：展示暂无历史薄弱点记录。
- [ ] 覆盖 `research_agent` done：展示 ReAct 轮次、工具调用次数、公司、Gap badge。
- [ ] 覆盖 `jd_analysis` done：展示公司、岗位、难度、技能 badge。
- [ ] 覆盖 `question_gen` done：展示总题数和非零分类统计。
- [ ] 覆盖 `chief_think` done：展示中文工具 badge。
- [ ] 覆盖 `followup` / `ask_question` done：展示追问方向。

### Task 14: `preparation-card.test.tsx`

**Files:**

- Modify: `frontend/app/interview/_components/preparation-card.test.tsx`

- [ ] summary 有值时渲染 `准备完成 · AI 综合判断` 和 summary 正文。
- [ ] summary 无值时不渲染 SummaryBlock。

### Task 15: `turn-trace-card.test.tsx`

**Files:**

- Modify: `frontend/app/interview/_components/turn-trace-card.test.tsx`

- [ ] 默认不展开 trace 节点，按钮显示 `查看 AI 思考过程`。
- [ ] 点击后展开 trace 节点，按钮显示 `收起思考过程`。
- [ ] header 不再渲染 designedQuestion。

### Task 16: `interview-chat` 集成测试

**Files:**

- Modify/Create: `frontend/app/interview/_components/interview-chat.test.tsx`

- [ ] turn done 且 `designedQuestion` 有值时，`HeroQuestionCard` 在 `TurnTraceCard` 外部渲染。
- [ ] `TurnTraceCard` 内部不再渲染 `designedQuestion`。
- [ ] `isOpening=true` 时不渲染 `HeroQuestionCard`。
- [ ] 有 `followupFocus` 时 badge 显示 `追问`。
- [ ] 无 `followupFocus` 时按 `designedCategory` 显示题型。

---

## Phase 7 — 验证与手测

### Task 17: 自动化验证

- [ ] 后端：
  ```bash
  cd backend
  uv run ruff check app/agents/prepare/graph.py
  ```
- [ ] 前端：
  ```bash
  cd frontend
  pnpm test trace-node.test.tsx preparation-card.test.tsx turn-trace-card.test.tsx
  pnpm typecheck
  ```
- [ ] 如新增/存在 `interview-chat.test.tsx`：
  ```bash
  pnpm test interview-chat.test.tsx
  ```

### Task 18: 浏览器手测

- [ ] 启动全栈：
  ```bash
  ./dev.sh
  ```
- [ ] 进入面试页，走一次 Prepare → Interview 流程。
- [ ] 验证 Prepare trace：
  - memory / research / jd / question_gen 节点 done 后均展示结构化内容。
  - research running 时 ReAct 工具树实时展开，done 后折叠。
  - Prepare summary 出现在节点列表下方。
- [ ] 验证 Interview trace：
  - 下一题 Hero 卡片在 AI 消息中置顶展示。
  - 思考过程默认折叠。
  - 点击后 trace 展开，文案切换正确。
  - opening 轮不展示 HeroQuestionCard。
- [ ] 检查浏览器 console 无新增错误。

---

## 设计决策

- **后端只补 payload，不改图结构**：本次目标是前端展示升级和结构化字段补齐，避免扩大 LangGraph 行为面。
- **全部新增字段可选**：确保旧 SSE、测试 mock、局部流程不会因字段缺失破坏渲染。
- **TraceNode 不拆新文件**：遵循 spec，避免把一次局部内容区重构扩成组件目录重组。
- **HeroQuestionCard 上移到消息层**：题目是用户下一步要回答的主内容，不应隐藏在折叠 trace 中。
- **TokenContent 兜底**：结构化字段缺失时继续显示原 tokens，减少线上空白节点风险。

## 不在范围内

- 不新增 UI 依赖。
- 不改 LangGraph 图结构。
- 不改 `research_agent.py` 的 ReAct 逻辑。
- 不调整后端数据模型或数据库迁移。
- 不重写 trace panel 外层布局。
- 不改变 opening 轮的 header 语义。
