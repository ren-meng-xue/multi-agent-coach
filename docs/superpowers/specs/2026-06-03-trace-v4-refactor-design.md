# Trace v4 重构设计

**日期：** 2026-06-03  
**分支：** feature/react-tool-trace-visualization  
**参考原型：** `html/trace-design-v4.html`

---

## 背景

现有 Prepare 阶段和面试轮次的 trace 可视化采用通用 `TraceNode` 组件，通过 `tokens` 文本流渲染节点内容。v4 原型引入了结构化展示：各 Prepare 节点有专属 badge/结论区，Interview 轮次的下一题以 Hero 卡片置顶，trace 默认折叠。本次重构目标是让前端渲染与原型一致，同时补充后端 SSE 所需结构化字段。

---

## 1. 数据契约（后端 SSE 变更）

改动文件：`backend/app/agents/prepare/graph.py`，仅在 `stream_prepare_events` 的 `node_done` 分支添加字段，不改图结构。

### 1.1 memory_search node_done

新增字段：

```python
"weak_areas": list[str]   # state["weak_areas"]，如 ["系统设计", "并发编程"]
"record_count": int        # len(state["weak_areas"])
```

### 1.2 research_agent node_done

新增字段（从 job_intel["_trace"] 和 job_intel 子字段读取）：

```python
"react_iterations": int      # job_intel["_trace"]["iterations"]
"react_tool_count": int      # len(job_intel["_trace"]["tools_used"])
"company_name": str          # job_intel["company_profile"]["name"] 或 summary 前 20 字
"gaps": list[str]            # job_intel["resume_match"]["gaps"][:3]
```

### 1.3 jd_analysis node_done

新增字段（从 node_state["jd_context"] 读取）：

```python
"jd_company": str
"jd_role": str
"jd_difficulty": str         # "easy"/"medium"/"hard"/"faang"
"jd_key_skills": list[str]   # key_skills[:6]
```

### 1.4 question_gen node_done

新增字段（从 node_state["prepared_questions"] 统计）：

```python
"question_stats": dict        # {"technical": 3, "behavioral": 1, "system_design": 1}
"question_total": int
```

---

## 2. 类型扩展

改动文件：`frontend/lib/prepare-types.ts`

### 2.1 TraceNodeData 新增可选字段

```typescript
// 记忆检索
weakAreas?: string[]
recordCount?: number

// 岗位调研
reactIterations?: number
reactToolCount?: number
companyName?: string
gaps?: string[]

// JD 分析
jdCompany?: string
jdRole?: string
jdDifficulty?: string
jdKeySkills?: string[]

// 出题
questionStats?: Record<string, number>
questionTotal?: number
```

### 2.2 PrepareSSEEvent["data"] 同步补充

同名可选字段对应后端新字段，前端 SSE 解析时写入 `TraceNodeData`。

全部为可选字段，无 breaking change，现有测试不受影响。

---

## 3. TraceNode 内容 zone 重构

改动文件：`frontend/app/interview/_components/trace-node.tsx`

### 3.1 结构

timeline 外框（dot + line + badge + 时间戳）保持不变。把现有散落的条件渲染块提取为文件内局部函数 `renderContent()`，按节点 id 分发：

```
TraceNode
  └─ timeline 外框（不变）
       └─ renderContent(id, props)
            ├─ "memory_search"   → MemoryContent
            ├─ "research_agent"  → ResearchContent
            ├─ "jd_analysis"     → JdContent
            ├─ "question_gen"    → QuestionContent
            ├─ "evaluator"       → EvaluatorContent（现有逻辑移入）
            └─ default           → TokenContent（现有 tokens 渲染，兜底）
```

不新增组件文件。现有 `id === "question_gen"` / `id !== "question_gen"` 等条件块归并进对应函数。

### 3.2 各 Content 函数行为

**MemoryContent**

- running：`"正在读取历史表现..."`
- done：`"读取到 {recordCount} 条记录，薄弱点："` + `weakAreas` 逐条以红色小 badge 展示；无 weakAreas 时显示 `"暂无历史薄弱点记录"`

**ResearchContent**

- running：展示 `ReactToolTree`（实时展开，现有行为）
- done：3 行 badge 组
  - `{reactIterations} 轮 · {reactToolCount} 次工具调用`
  - `{companyName}`（有值时）
  - `Gap：{gaps.join(" · ")}`（有值时，红色 badge）
  - `ReactToolTree` 折叠展示（isFinished=true，默认收起）

**JdContent**

- running：`"正在分析岗位需求..."`
- done：`"{jdCompany} · {jdRole} · 难度 {jdDifficulty}"` + `jdKeySkills` badge 列表

**QuestionContent**

- running：`"正在为你定制专属题目..."`（现有）
- done：`"已定制 {questionTotal} 道"` + 分类 badge：`技术 ×{n}` `行为 ×{n}` `系统设计 ×{n}`

**EvaluatorContent**（现有逻辑移入，行为不变）

- 评分大字 + 等级 badge + latentSignals/missingDimensions badges + 结论一行

**TokenContent**（兜底）

- 现有 tokens 文本渲染，原样保留

---

## 4. Interview 轮次重构

### 4.1 Hero Question 卡片

改动文件：`frontend/app/interview/_components/interview-chat.tsx`

从 `TurnTraceCard` 提取 `designedQuestion`，在消息渲染层独立渲染 `HeroQuestionCard`（文件内局部组件）：

```
AI 消息渲染
  └─ HeroQuestionCard（仅 designedQuestion 有值 && status==="done" && !isOpening）
       ├─ 📝 题型 badge（技术 / 行为 / 系统设计）
       └─ 问题正文（font-size 14px, font-weight 600）
  └─ TurnTraceCard（折叠，无 designedQuestion header）
```

**HeroQuestionCard** 样式参照原型：绿色渐变背景 + 绿色边框。

### 4.2 TurnTraceCard 改动

改动文件：`frontend/app/interview/_components/turn-trace-card.tsx`

- `internalExpanded` 初始值改为 `false`
- toggle 文案：`查看 AI 思考过程` / `收起思考过程`
- 去掉 header 里的 `designedQuestion` 分支逻辑
- opening 轮 header 文案保持不变

### 4.3 PreparationCard Summary 卡片

改动文件：`frontend/app/interview/_components/preparation-card.tsx`

新增 prop `summary?: string`，在 `AgentTrace` 节点列表下方渲染 `SummaryBlock`：

```
PrepareCard (TracePanelShell)
  ├─ AgentTrace（现有）
  └─ SummaryBlock（summary 有值时渲染）
       ├─ AI 黑圆点 + "准备完成 · AI 综合判断"
       └─ summary 正文
```

`summary` 来自后端 `done` event 已有的 `summary` 字段，在 `interview-chat.tsx` 里存入 prepare 状态并向下传递。

---

## 5. 改动范围汇总

| 文件                                                      | 改动类型                                   |
| --------------------------------------------------------- | ------------------------------------------ |
| `backend/app/agents/prepare/graph.py`                     | node_done 新增结构化字段                   |
| `frontend/lib/prepare-types.ts`                           | TraceNodeData + PrepareSSEEvent 加可选字段 |
| `frontend/app/interview/_components/trace-node.tsx`       | 内容 zone 按节点类型分发                   |
| `frontend/app/interview/_components/preparation-card.tsx` | 新增 summary prop + SummaryBlock           |
| `frontend/app/interview/_components/turn-trace-card.tsx`  | 默认折叠 + 文案改                          |
| `frontend/app/interview/_components/interview-chat.tsx`   | 独立渲染 HeroQuestionCard，传 summary      |

不新增文件，不改 LangGraph 图结构，不改 research_agent.py，不改测试文件（仅补测试）。

---

## 6. 测试补充

- `trace-node.test.tsx`：各 prepare 节点 Content 函数的 done 状态渲染
- `preparation-card.test.tsx`：summary 卡片渲染
- `turn-trace-card.test.tsx`（如需新建）：默认折叠 + hero question 提取
