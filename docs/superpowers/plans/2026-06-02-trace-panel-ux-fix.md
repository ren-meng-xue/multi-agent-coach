# Trace 面板 UX 修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复两个 trace 面板 UX 问题：(1) 隐藏子 agent 内部节点名，(2) 准备面板不一次性曝光所有题目。

**Architecture:** 后端在 graph.py `_HIDDEN_NODES` 中阻断子图事件冒泡，同时在 `chief_think` node_done 中补上 designer 出题结果；前端删除 question_gen 的题目卡片渲染逻辑，改为固定文案。

**Tech Stack:** Python 3.12 / FastAPI / LangGraph（后端），TypeScript / React / Next.js（前端）

---

## 文件结构

| 文件                                                    | 职责                                             | 改动类型                             |
| ------------------------------------------------------- | ------------------------------------------------ | ------------------------------------ |
| `backend/app/agents/interviewer/graph.py`               | SSE 事件生成 + 节点过滤 + node_done payload      | 修改                                 |
| `frontend/lib/prepare-types.ts`                         | TraceNodeData / InterviewTraceNodeEvent 类型定义 | 修改                                 |
| `frontend/lib/interview-chat.ts`                        | SSE 事件数据处理                                 | 修改（移除 question_gen 格式化逻辑） |
| `frontend/app/interview/_components/trace-node.tsx`     | 单节点时间线渲染                                 | 修改                                 |
| `frontend/app/interview/_components/interview-chat.tsx` | SSE 事件接收 + trace state 更新                  | 修改                                 |

---

### Task 1: 后端隐藏子 agent 内部节点 + 补上 designer 出题结果

**Files:**

- Modify: `backend/app/agents/interviewer/graph.py:130`

- [ ] **Step 1: 扩展 `_HIDDEN_NODES`**

将 `_HIDDEN_NODES` 从：

```python
_HIDDEN_NODES = {"load_context", "report", "chief_execute"}
```

改为：

```python
# 不发 node_* 事件的内部节点（用户无需可见）
# designer/evaluator 子图内部节点也在此隐藏——其结果通过 chief_think node_done 向上传递
_HIDDEN_NODES = {
    "load_context", "report", "chief_execute",
    # designer 子图内部节点
    "design", "validate", "respond_to_chief",
    # evaluator 子图内部节点
    "analyze_answer", "update_profile",
    # designer_dual 子图内部节点
    "design_dual",
}
```

`on_chain_start`（第 184-195 行）和 `on_chain_end`（第 228 行）两处过滤都共用 `_HIDDEN_NODES`，一次改动同时生效。

- [ ] **Step 2: `chief_think` node_done 补上 designer 出题结果**

在 `graph.py` 第 247-252 行 `chief_think` node_done 构造处，增加 designer 输出提取：

```python
if ev_node == "chief_think" and isinstance(node_dict, dict):
    msgs = node_dict.get("chief_messages") or []
    last = msgs[-1] if msgs else None
    tool_calls = [tc["name"] for tc in (getattr(last, "tool_calls", None) or [])]
    payload["chief_tool_calls"] = tool_calls
    payload["chief_thoughts"] = node_dict.get("chief_thoughts", [])
    # 补上 designer 出题结果，供前端展示
    designer = node_dict.get("designer_output") or {}
    if designer.get("question_text"):
        payload["designed_question"] = designer.get("question_text", "")
```

- [ ] **Step 3: 验证后端改动**

```bash
cd backend && uv run ruff check app/agents/interviewer/graph.py
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents/interviewer/graph.py
git commit -m "fix(backend): hide sub-agent internal nodes from trace, surface designer output in chief_think"
```

---

### Task 2: 前端类型定义更新

**Files:**

- Modify: `frontend/lib/prepare-types.ts:60-89`

- [ ] **Step 1: `TraceNodeData` 增加 `designedQuestion` 字段**

在第 71 行 `chiefToolCalls` 之后增加：

```typescript
export interface TraceNodeData {
  id: string;
  label: string;
  title?: string;
  status: TraceNodeStatus;
  tokens: string;
  elapsedMs?: number;
  candidateLevel?: "beginner" | "junior" | "mid" | "senior";
  latentSignals?: string[];
  missingDimensions?: string[];
  followupFocus?: string;
  chiefToolCalls?: string[];
  /** designer agent 出题结果，在 chief_think/chief_respond 节点展示 */
  designedQuestion?: string;
}
```

- [ ] **Step 2: `InterviewTraceNodeEvent` 增加对应字段**

在第 86 行 `chiefToolCalls` 之后增加：

```typescript
export interface InterviewTraceNodeEvent {
  phase: "start" | "token" | "done";
  node: string;
  label?: string;
  text?: string;
  elapsedMs?: number;
  chain?: string[];
  summaryScore?: number;
  candidateLevel?: "beginner" | "junior" | "mid" | "senior";
  latentSignals?: string[];
  missingDimensions?: string[];
  followupFocus?: string;
  chiefToolCalls?: string[];
  assistantMessage?: string;
  /** designer agent 出题结果 */
  designedQuestion?: string;
}
```

- [ ] **Step 3: 类型检查**

```bash
cd frontend && pnpm typecheck
```

期望：通过（仅有新增可选字段，不影响现有代码）。

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/prepare-types.ts
git commit -m "fix(frontend): add designedQuestion field to trace types"
```

---

### Task 3: 前端 SSE 事件传递 designedQuestion

**Files:**

- Modify: `frontend/app/interview/_components/interview-chat.tsx:599-610`
- Modify: `frontend/app/interview/_components/interview-chat.tsx:736-754`

- [ ] **Step 1: turn_node_done 事件映射增加 designedQuestion**

在 `handlePrepareEvent` 的 `turn_node_done` 处理处（第 599-610 行），`updateTurnTrace` 调用中增加：

```typescript
updateTurnTrace(turnId, {
  phase,
  node: data.node ?? "",
  label: data.label,
  text: data.text,
  elapsedMs: data.elapsed_ms,
  candidateLevel: data.candidate_level,
  latentSignals: data.latent_signals,
  missingDimensions: data.missing_dimensions,
  followupFocus: data.followup_focus,
  assistantMessage: data.assistant_message,
  summaryScore: data.summary_score, // 新增：传递评分
  chiefToolCalls: data.chief_tool_calls, // 新增：传递工具调用列表
  designedQuestion: data.designed_question, // 新增：传递出题结果
});
```

注意：此处原本就缺少 `summaryScore` 和 `chiefToolCalls` 的映射——前端 `TurnTraceCard` 的评分徽章和 `TraceNode` 的工具徽章因此无法正常显示。**这是一并修复的缺陷。**

- [ ] **Step 2: flushTraceBuffer done 分支传递新字段**

在 `flushTraceBuffer` 函数（第 736-754 行），`phase === "done"` 分支中增加：

```typescript
} else if (ev.phase === "done") {
  if (nIdx !== -1) {
    nodes[nIdx] = {
      ...nodes[nIdx],
      status: "done" as const,
      elapsedMs: ev.elapsedMs,
      candidateLevel: ev.candidateLevel,
      latentSignals: ev.latentSignals,
      missingDimensions: ev.missingDimensions,
      followupFocus: ev.followupFocus,
      chiefToolCalls: ev.chiefToolCalls,
      designedQuestion: ev.designedQuestion,  // 新增
      tokens:
        ev.assistantMessage && !nodes[nIdx].tokens
          ? ev.assistantMessage
          : nodes[nIdx].tokens,
    };
  }
}
```

- [ ] **Step 3: 验证**

```bash
cd frontend && pnpm typecheck
```

- [ ] **Step 4: Commit**

```bash
git add frontend/app/interview/_components/interview-chat.tsx
git commit -m "fix(frontend): pass designedQuestion, summaryScore, chiefToolCalls through SSE events"
```

---

### Task 4: 前端 trace-node.tsx 改造

**Files:**

- Modify: `frontend/app/interview/_components/trace-node.tsx:7-18`（Props 接口）
- Modify: `frontend/app/interview/_components/trace-node.tsx:129-187`（question_gen 渲染）
- Modify: `frontend/app/interview/_components/trace-node.tsx:115-126`（chief_think 渲染，增加 designedQuestion）

- [ ] **Step 1: Props 接口增加 `designedQuestion`**

在 `TraceNodeProps` 接口（第 7-18 行）增加：

```typescript
interface TraceNodeProps {
  id: string;
  label: string;
  title: string;
  status: TraceNodeStatus;
  tokens: string;
  elapsedMs?: number;
  isLast?: boolean;
  candidateLevel?: "beginner" | "junior" | "mid" | "senior";
  latentSignals?: string[];
  missingDimensions?: string[];
  chiefToolCalls?: string[];
  designedQuestion?: string; // 新增
}
```

并在组件解构中增加（第 21-33 行）：

```typescript
export function TraceNode({
  id, label, title, status, tokens, elapsedMs, isLast = false,
  candidateLevel, latentSignals, missingDimensions,
  chiefToolCalls, designedQuestion,  // 新增 designedQuestion
}: TraceNodeProps) {
```

- [ ] **Step 2: 删除 question_gen 的题目卡片渲染，改为固定文案**

将第 129-187 行（`id === "question_gen" && tokens` 分支）整个替换为：

```typescript
{/* 准备阶段出题节点：不渲染题目详情，仅显示完成提示 */}
{id === "question_gen" && tokens && (
  <div className="space-y-1.5 pl-2.5 border-l-[1.5px] border-[#534AB7]/10 dark:border-white/10 animate-in fade-in slide-in-from-top-1 duration-500">
    {status === "running" ? (
      <p className="text-[11px] text-[#534AB7]/60 animate-pulse dark:text-[#CECBF6]/60 font-medium">
        正在为你定制专属题目...
      </p>
    ) : (
      <p className="text-[11px] text-emerald-600/80 dark:text-emerald-400/80 font-semibold">
        已为你定制 5 道专属面试题，面试中将逐题呈现。
      </p>
    )}
  </div>
)}
```

- [ ] **Step 3: chief_think / chief_respond 节点增加出题信息展示**

在工具调用徽章区域之后（第 126 行之后），增加出题信息展示：

```typescript
{/* 出题信息展示：chief_think / chief_respond 节点显示 designer 输出的题目 */}
{(id === "chief_think" || id === "chief_respond") && status === "done" && designedQuestion && (
  <div className="mb-2.5 pl-2.5 border-l-[1.5px] border-sky-200/50 dark:border-sky-800/30 animate-in fade-in slide-in-from-top-1 duration-500">
    <div className="flex gap-2 items-start p-2 rounded-lg bg-sky-50/50 border border-sky-100/30 dark:bg-sky-950/20 dark:border-sky-900/20">
      <span className="flex-shrink-0 text-[10px] mt-[1px]">📝</span>
      <span className="text-[11px] leading-relaxed text-sky-800/80 dark:text-sky-300/80 font-medium">
        {designedQuestion}
      </span>
    </div>
  </div>
)}
```

- [ ] **Step 4: agent-trace.tsx 传递 designedQuestion**

在 `agent-trace.tsx` 第 25-38 行的 `<TraceNode>` 调用处，增加 prop：

```typescript
<TraceNode
  key={node.id}
  id={node.id}
  label={label}
  title={node.title || nodeTitles?.[node.id] || PREPARE_NODE_TITLES[node.id] || node.id}
  status={node.status}
  tokens={node.tokens}
  elapsedMs={node.elapsedMs}
  isLast={index === nodes.length - 1}
  candidateLevel={node.candidateLevel}
  latentSignals={node.latentSignals}
  missingDimensions={node.missingDimensions}
  chiefToolCalls={node.chiefToolCalls}
  designedQuestion={node.designedQuestion}  // 新增
/>
```

- [ ] **Step 5: 验证**

```bash
cd frontend && pnpm typecheck && pnpm build
```

- [ ] **Step 6: Commit**

```bash
git add frontend/app/interview/_components/trace-node.tsx \
        frontend/app/interview/_components/agent-trace.tsx
git commit -m "fix(frontend): hide question cards in prep panel, show designer output in trace"
```

---

### Task 5: 前端 interview-chat.ts 移除 question_gen 格式化逻辑

**Files:**

- Modify: `frontend/lib/interview-chat.ts:97-117`

- [ ] **Step 1: 删除 `formatTraceTokens` 中 question_gen 的特殊处理**

`formatTraceTokens` 函数（第 97-135 行）中第 100-117 行的 `question_gen` 特殊处理已无意义——准备面板不再渲染 question_gen 的题目详情。删除该分支：

删除：

```typescript
// 出题节点特殊处理：提取 JSON 中的 question 字段
if (id === "question_gen" || id === "ask_question") {
  const robustPattern = ...
  ...
  if (questions.length > 0) {
    return questions.map((q) => `→ ${q}`).join("\n    ");
  }
}
```

保留：

```typescript
/** 格式化 Trace 节点的 tokens，过滤 JSON 并美化输出。 */
export function formatTraceTokens(id: string, tokens: string): string {
  if (!tokens) return "(无详细信息)";

  // 其他节点：过滤 JSON 标记，保留普通文本
  return tokens
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => {
      return (
        line &&
        !line.startsWith("[") &&
        !line.startsWith("{") &&
        !line.includes('": "') &&
        !line.startsWith("}") &&
        !line.startsWith("]")
      );
    })
    .map((line) => line.replace(/^[•\-]\s*/, "→ "))
    .join("\n    ");
}
```

注意：`ask_question` 节点在当前架构中已不存在（被 `chief_think` + `designer` 替代），原特殊处理纯属死代码。

- [ ] **Step 2: 验证**

```bash
cd frontend && pnpm typecheck && pnpm test
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/interview-chat.ts
git commit -m "chore(frontend): remove dead question_gen format logic from formatTraceTokens"
```

---

## 验证清单

改动完成后进行端到端验证：

1. `cd backend && uv run ruff check .` — 后端 lint 通过
2. `cd frontend && pnpm typecheck` — 前端类型检查通过
3. `cd frontend && pnpm build` — 前端构建通过
4. 浏览器手动验证：
   - 启动面试 → 准备阶段面板不再显示 5 道题目卡片 → 仅显示"已为你定制 5 道专属面试题"
   - 面试官第一题 → 右侧 trace 面板只显示 `规划工具调用` 和 `组织面试回复` 两个节点
   - 不再出现 `design`/`validate`/`respond_to_chief` 等原始节点名
   - `chief_think` 节点显示工具徽章 + 评估结果徽章 + 出题信息
   - 回答后下一轮 → `chief_think` 显示评估回答 + 设计题目的工具调用
