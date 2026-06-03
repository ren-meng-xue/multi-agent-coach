# research_agent 工具级 ReAct Trace 可视化设计文档

- 日期：2026-06-03
- 分支：feature/react-tool-trace-viz（实现期创建，需先合 `feature/research-agent-mcp`）
- 范围：扩展 SSE 事件协议 + 前端 trace panel 支持节点内 ReAct 步骤树展示
- 前置依赖：`docs/superpowers/specs/2026-06-03-research-agent-mcp-design.md`（research_agent 节点已经存在并能跑通）

---

## 一、背景与问题

### 1.1 当前状态

research_agent + MCP 接入完成后，Prepare 阶段已经能在前端 trace panel 看到一个 `research_agent` 节点：

```
Prepare 流程
├─ ✅ 调度
├─ ✅ 记忆检索（memory_search）         ... 读取到历史薄弱点 2 项
├─ ✅ 岗位调研（research_agent）         ... 调研完成，3 轮、用了 3 次工具调用，耗时 23000 毫秒
│                                       公司画像：字节核心业务
│                                       针对此岗位的 Gap：缺分布式
├─ ✅ 出题（question_gen）
└─ 完成
```

**节点级 trace 是免费有的**（沿用现有 `node_start / node_done` SSE 事件），但用户**点不开**看具体哪 3 次工具、每次调用前 LLM 在想什么、工具返回了什么。

### 1.2 为什么这层缺失会削弱本期项目的展示价值

multi-agent-coach 本期接入 job-intel MCP 的核心动机不是"功能新增"，是**展示亮点**：

> 突出 multi 通过 MCP 协议接入外部 Agent 系统，并让这种接入发生在 LLM 自主"工具思考"的链路里——不是硬编码 RPC。

但如果用户只能看到"岗位调研节点跑了 23s 用了 3 个工具"——这跟"调了一次 RPC"在视觉上没有区别。要把"Agent 工具思考"的亮点呈现出来，**必须**让用户在前端能看到：

- 每一轮 LLM 的 think 内容（流式显示推理过程）
- 每一次具体的 tool_call（工具名 + 参数摘要）
- 每一次 observe 的结果（结果摘要 + 耗时）
- ReAct 多轮迭代的完整步骤树

这才是"工具思考接入 MCP"的视觉表达。

### 1.3 本期目标

让前端 trace panel 中 `research_agent` 节点**可展开**，展开后呈现一棵 ReAct 步骤树，包含：

- 多轮 iteration 的 think 内容（流式）
- 每个 tool_call 的工具名、入参摘要、耗时
- 每个 tool_call 对应的 observe 结果摘要
- 节点完成时的整体统计（总轮次、总耗时、用了哪些工具）

后端改动：扩展 SSE 事件协议（新增 3 类工具级事件），从 `research_agent_node` 内部按时序 emit。

前端改动：扩展 SSE 事件解析、引入 `ReactStepTree` 数据模型、扩展 `TraceNode` 组件支持嵌套展开、新增 `ToolStepCard` 子组件。

### 1.4 跟前一份 spec 的边界

| 维度           | 前一份 spec（research_agent + MCP）  | 本期 spec                   |
| -------------- | ------------------------------------ | --------------------------- |
| 业务能力       | 接入 job-intel，产出岗位情报         | **不动**业务能力            |
| 后端节点逻辑   | research_agent 写 job_intel 到 State | **不动**节点行为            |
| 后端 SSE 事件  | 沿用 node_start / node_done          | **扩展**新增 3 类工具级事件 |
| 前端节点级渲染 | TraceNode 自动渲染                   | **不动**节点级渲染          |
| 前端工具级渲染 | 不做                                 | **本期主要工作**            |

简言之：本期是**纯展示层增强**，业务流不变。

---

## 二、设计原则

1. **纯展示，不影响业务**：新增 SSE 事件**只用于展示**，节点的 State 流转、最终产物都不变。即使前端不订阅这些事件，后端业务流照常完成
2. **流式优先**：think 内容必须流式吐字（跟现有 question_gen 流式吐题一致的体感）；tool_call 完成时再 emit observe，不积压等到节点结束才一次给
3. **结构化优于自由文本**：tool_call 事件带工具名、参数摘要、耗时这些结构化字段，让前端可以按工具类型用不同 UI 风格；不依赖前端解析 markdown
4. **可降级**：后端 emit 工具级事件失败不阻断业务；前端解析失败时 fall back 到只显示节点级 trace
5. **复用现有协议**：在现有 `PrepareSSEEvent.event` 联合类型里追加新 enum 值，data 字段沿用扁平 dict，**不**新增子协议层
6. **从 research_agent 起步**：本期只让 research_agent 节点支持展开；Interviewer Chief 的 ReAct loop 虽然结构类似但**不在本期**（chief 已经有自己的 chiefToolCalls 字段，复用现有展示）
7. **不做的事**：
   - 不重写现有 TraceNode（只扩展，保持现有节点级渲染兼容）
   - 不做"折叠状态持久化"（用户刷新页面后默认折叠状态即可）
   - 不做"导出 trace 为图片/JSON"
   - 不做"在面试历史里重放 trace"

---

## 三、架构

### 3.1 整体数据流

```
后端 research_agent_node (ReAct loop)
   │
   │ 每一轮 iteration 内按时序 emit:
   │   1. tool_thinking_start  ── LLM 开始 think
   │   2. tool_thinking_token  ── LLM 流式吐 think 字符
   │   3. tool_thinking_done   ── think 结束
   │   4. tool_call_start      ── 开始调某工具
   │   5. tool_call_done       ── 工具返回（带结果摘要 + 耗时）
   │   （重复 1-5 直到 LLM 决定不再调工具）
   │
   ▼
LangGraph astream_events → 现有 SSE 通道（不新增 endpoint）
   │
   ▼
前端 SSE handler
   │
   │ 按 (node_id, iteration_index, step_kind) 聚合
   │
   ▼
ReactStepTree 数据模型
   │
   ▼
TraceNode（research_agent 节点）
   │
   │ children = ReactStepTree
   │
   ▼
点击展开 → 渲染 IterationGroup → ThinkCard / ToolCallCard
```

### 3.2 SSE 协议扩展

在现有 `PrepareSSEEvent.event` 联合里追加 5 个新值：

```typescript
event:
  // 现有
  | "node_start" | "node_token" | "node_done" | "done" | "error"
  ...
  // 本期新增（research_agent 节点内部 emit）
  | "tool_thinking_start"
  | "tool_thinking_token"
  | "tool_thinking_done"
  | "tool_call_start"
  | "tool_call_done"
```

每个新事件的 data schema（全部走现有 data 扁平字典风格）：

```typescript
// 新字段（追加到 PrepareSSEEvent.data）
interface ToolTraceEventData {
  node?: string; // 始终是 "research_agent"
  iteration?: number; // 第几轮 ReAct iteration（从 0 起）
  step_id?: string; // 本步唯一 id（用于流式聚合）
  // tool_thinking_token 用：
  text?: string;
  // tool_call_start 用：
  tool_name?: string;
  tool_args_summary?: string; // 入参摘要，前端直接显示（如 'query="字节 飞书"'）
  // tool_call_done 用：
  tool_result_summary?: string; // 出参摘要（如 '{6 模块完整报告}' 或 '[5 条结果]'）
  tool_elapsed_ms?: number;
  tool_error?: string; // 工具调用失败时填错误信息
}
```

### 3.3 前端数据模型

```typescript
// 一次 ReAct iteration 的步骤组
interface ReactIteration {
  index: number;
  thinkContent: string; // 流式累积的 think 文本
  thinkStatus: "running" | "done";
  toolCalls: ToolCallStep[];
}

interface ToolCallStep {
  stepId: string;
  toolName: string;
  argsSummary: string;
  resultSummary?: string;
  elapsedMs?: number;
  error?: string;
  status: "running" | "done" | "error";
}

// TraceNodeData 扩展（追加在原 interface 里）
interface TraceNodeData {
  // 现有所有字段...
  reactSteps?: ReactIteration[]; // ★ 仅 research_agent 节点有
  reactStatus?: "running" | "done"; // ★
}
```

### 3.4 UI 结构

```
┌─ TraceNode（research_agent）─────────────────────┐
│  [岗位调研] 调研目标岗位                  23000ms │
│  · 调研完成，3 轮、用了 3 次工具调用              │
│  · 公司画像：字节核心业务                         │
│  · 针对此岗位的 Gap：缺分布式                     │
│  ▼ 展开 ReAct 思考链                              │  ← 点击切换
├──────────────────────────────────────────────────┤
│  展开后：                                         │
│                                                   │
│  ╭─ 第 1 轮 ───────────────────────────────────╮ │
│  │ 💭 think                                      │ │
│  │    用户给了 JD 文本和简历摘要，先把 JD 嚼...   │ │
│  │                                                │ │
│  │ 🔧 extract_jd_text(text="字节后端 JD...")     │ │
│  │    ↳ {company: "字节", title: "国际化前端"}    │ │
│  │    1.2s                                        │ │
│  ╰────────────────────────────────────────────────╯│
│                                                    │
│  ╭─ 第 2 轮 ───────────────────────────────────╮ │
│  │ 💭 think                                      │ │
│  │    字节国际化团队我不熟，搜一下背景            │ │
│  │                                                │ │
│  │ 🔧 web_search(query="字节 飞书 国际化团队")    │ │
│  │    ↳ [5 条搜索结果]                            │ │
│  │    3.5s                                        │ │
│  ╰────────────────────────────────────────────────╯│
│                                                    │
│  ╭─ 第 3 轮 ───────────────────────────────────╮ │
│  │ 💭 think                                      │ │
│  │    信息够了，生成报告                          │ │
│  │                                                │ │
│  │ 🔧 generate_position_report(...)              │ │
│  │    ↳ {6 模块完整报告}                          │ │
│  │    18.1s                                       │ │
│  ╰────────────────────────────────────────────────╯│
└──────────────────────────────────────────────────┘
```

### 3.5 折叠/展开行为

- 节点未完成（running）时：**默认展开**（让用户实时看到思考过程）
- 节点完成（done）后：**自动折叠**（但保留点击展开能力，看历史）
- 用户手动展开/折叠：覆盖默认行为，**只在当前节点存在期间生效**（页面刷新后回到默认）
- 折叠状态用 `useState` 维护，不持久化

---

## 四、后端 SSE 事件 emit 设计

### 4.1 在 research_agent_node 里插入 emit 点

`research_agent_node` 已经有 ReAct loop（前一份 spec Task 14）。本期改造 loop 让它在每一步 emit 工具级事件。但 LangGraph 的 `astream_events` 机制是事件**自动**从 node 内部流出的——`node_token` 事件是通过 LLM stream chunk 自动产生的，不需要手动 emit。

工具级事件需要**手动 emit**，因为它们不是 LLM token，是节点内部状态变化。LangGraph 提供两种机制：

- **方案 A：用 `astream_writer`**（LangGraph 1.x 推荐）—— 在节点函数内部用 `get_stream_writer()` 写自定义事件
- **方案 B：用 callback handler** —— 注册 callback 在工具调用前后触发
- **方案 C：直接走 Redis Pub/Sub**（项目其他地方有这种模式）—— 不依赖 LangGraph，业务自己 publish

本期选 **方案 A**（`astream_writer`），理由：

- LangGraph 原生支持，能跟现有 `astream_events` 协议无缝集成
- 不需要新建独立的事件通道
- 类型清晰，事件结构由 Python 函数签名固定

### 4.2 改造 research_agent_node

在 `research_agent_node` 里：

```python
from langgraph.config import get_stream_writer

async def research_agent_node(state):
    writer = get_stream_writer()  # 拿到 LangGraph 自定义事件 writer
    # ... ReAct loop 中：

    for iteration in range(MAX_ITERATIONS):
        # think 开始
        writer({"kind": "tool_thinking_start", "iteration": iteration, "step_id": f"think-{iteration}"})

        # 调 LLM streaming（每个 token 一个事件）
        chunks = []
        async for chunk in model.astream(messages):
            chunks.append(chunk)
            writer({"kind": "tool_thinking_token", "iteration": iteration, "step_id": f"think-{iteration}", "text": chunk.content or ""})

        # think 结束
        writer({"kind": "tool_thinking_done", "iteration": iteration, "step_id": f"think-{iteration}"})

        # 检查 tool_calls
        for tc in tool_calls:
            step_id = f"tool-{iteration}-{tc['id']}"
            writer({
                "kind": "tool_call_start",
                "iteration": iteration,
                "step_id": step_id,
                "tool_name": tc["name"],
                "tool_args_summary": _summarize_args(tc["args"]),
            })

            t0 = time.time()
            try:
                result = await tool.ainvoke(tc["args"])
                writer({
                    "kind": "tool_call_done",
                    "iteration": iteration,
                    "step_id": step_id,
                    "tool_result_summary": _summarize_result(result),
                    "tool_elapsed_ms": int((time.time() - t0) * 1000),
                })
            except Exception as exc:
                writer({
                    "kind": "tool_call_done",
                    "iteration": iteration,
                    "step_id": step_id,
                    "tool_error": str(exc),
                    "tool_elapsed_ms": int((time.time() - t0) * 1000),
                })
```

### 4.3 摘要函数

两个辅助函数，控制摘要长度避免前端展示爆炸：

```python
def _summarize_args(args: dict) -> str:
    """工具入参摘要：截短长字符串，保留结构。"""
    parts = []
    for k, v in args.items():
        if isinstance(v, str):
            v_short = v[:60] + ("..." if len(v) > 60 else "")
            parts.append(f'{k}="{v_short}"')
        elif isinstance(v, (list, dict)):
            parts.append(f"{k}=<{type(v).__name__} len={len(v)}>")
        else:
            parts.append(f"{k}={v}")
    return ", ".join(parts)

def _summarize_result(result) -> str:
    """工具出参摘要：根据类型给不同表达。"""
    if isinstance(result, dict):
        keys = list(result.keys())[:6]
        return "{" + ", ".join(keys) + "}" + ("..." if len(result) > 6 else "")
    if isinstance(result, list):
        return f"[{len(result)} 条结果]"
    if isinstance(result, str):
        return result[:120] + ("..." if len(result) > 120 else "")
    return str(result)[:120]
```

### 4.4 SSE 适配层

LangGraph 的 `astream_writer` 写出来的事件在 `astream_events` 里以 `event="on_custom"` 或类似类型出现（具体看 LangGraph 1.x 版本）。Prepare 的 SSE 网关（`stream_prepare_events`）需要拦截这些自定义事件，转换为前端约定的 SSE event 名。

在 `agents/prepare/graph.py` 的 `stream_prepare_events` 函数里追加：

```python
async for event in get_prepare_graph().astream_events(state, version="v2"):
    ev_name = event.get("event", "")

    # 已有 node_start / node_token / node_done 分支保留...

    # 新增：自定义工具事件
    if ev_name == "on_custom" and event.get("data", {}).get("kind", "").startswith(("tool_thinking", "tool_call")):
        custom = event["data"]
        kind = custom.pop("kind")
        yield {
            "event": kind,             # tool_thinking_start / token / done / tool_call_start / done
            "data": {
                "node": event.get("metadata", {}).get("langgraph_node", "research_agent"),
                **custom,
            },
        }
```

---

## 五、前端实现设计

### 5.1 类型扩展

`lib/prepare-types.ts` 追加：

```typescript
export interface ToolCallStep {
  stepId: string;
  toolName: string;
  argsSummary: string;
  resultSummary?: string;
  elapsedMs?: number;
  error?: string;
  status: "running" | "done" | "error";
}

export interface ReactIteration {
  index: number;
  thinkContent: string;
  thinkStatus: "running" | "done";
  toolCalls: ToolCallStep[];
}

// PrepareSSEEvent.event 联合追加 5 个
// PrepareSSEEvent.data 追加可选字段：iteration / step_id / tool_name / tool_args_summary / tool_result_summary / tool_elapsed_ms / tool_error

// TraceNodeData 追加：
//   reactSteps?: ReactIteration[];
//   reactStatus?: "running" | "done";
```

### 5.2 SSE 解析层

`agent-trace.tsx`（或 `interview-chat.tsx` 里的事件处理 reducer）按事件类型分发：

| 事件                  | 处理                                                                                             |
| --------------------- | ------------------------------------------------------------------------------------------------ |
| `tool_thinking_start` | 在 `reactSteps[iteration]` 不存在则创建，`thinkStatus = "running"`                               |
| `tool_thinking_token` | `reactSteps[iteration].thinkContent += text`（流式累积）                                         |
| `tool_thinking_done`  | `reactSteps[iteration].thinkStatus = "done"`                                                     |
| `tool_call_start`     | 在 `reactSteps[iteration].toolCalls` 推入 `{ stepId, toolName, argsSummary, status: "running" }` |
| `tool_call_done`      | 找到 stepId 对应 toolCall，更新 `resultSummary / elapsedMs / error / status = "done" 或 "error"` |

事件处理是**幂等**的——根据 `step_id` 找到对应 step，存在就更新、不存在就创建，避免乱序事件破坏状态。

### 5.3 UI 组件拆分

| 组件                                                | 路径                                            | 职责                                                                                                                        |
| --------------------------------------------------- | ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `TraceNode`（修改）                                 | `app/interview/_components/trace-node.tsx`      | 已有；新增 `reactSteps` prop，渲染时若节点 id 为 `research_agent` 且 `reactSteps` 非空，渲染展开/折叠按钮 + `ReactStepTree` |
| `ReactStepTree`（新增）                             | `app/interview/_components/react-step-tree.tsx` | 接收 `reactSteps`，按 iteration 分组渲染 `IterationGroup`                                                                   |
| `IterationGroup`（新增，可与 ReactStepTree 同文件） | 同上                                            | 渲染一轮的卡片：think 文字块 + 多个 `ToolCallCard`                                                                          |
| `ToolCallCard`（新增）                              | `app/interview/_components/tool-call-card.tsx`  | 渲染单个工具调用：工具名 + 入参 + 结果摘要 + 耗时 + 状态图标                                                                |

### 5.4 折叠/展开逻辑

`TraceNode` 内：

```typescript
const [isExpanded, setIsExpanded] = useState(false);

// 默认行为：节点 running 时展开，done 后折叠（除非用户手动点过）
const [userToggled, setUserToggled] = useState(false);
const effectiveExpanded = userToggled ? isExpanded : status === "running";

// 用户点击时
function onToggle() {
  setUserToggled(true);
  setIsExpanded(!effectiveExpanded);
}
```

### 5.5 视觉风格

复用现有 `TraceNode` 的颜色系统（`#534AB7` 紫色 brand 色 + emerald 绿色完成态），不引入新颜色变量。

- `IterationGroup`：圆角 12px 卡片，背景 `bg-slate-50/50 dark:bg-zinc-900/40`，左边一道紫色竖线
- `ToolCallCard`：单行结构，工具名用 `font-mono`，结果摘要用 `text-slate-600`，耗时右对齐
- 状态图标：think 用 💭、tool 用 🔧、运行中加 pulse 动画、完成加绿色 checkmark
- 不引入新依赖（不上 `@radix-ui/collapsible`，用 CSS `max-height` transition 自己写折叠）

---

## 六、验收口径

### 6.1 后端

- [ ] research_agent 跑通时，SSE 流里能观察到 5 类新事件按 iteration 顺序出现
- [ ] tool_thinking_token 是真正流式（一个 chunk 一个事件，不是一次性大段）
- [ ] tool_call_done 的 elapsed_ms 准确反映工具调用真实耗时
- [ ] tool_call 异常时 emit `tool_error` 字段
- [ ] 节点完成时（node_done）所有 tool 事件已 emit 完毕

### 6.2 前端

- [ ] research_agent 节点 running 时**默认展开**，且能看到 think 文字流式吐出
- [ ] 每次 tool_call_start 在树里立即出现新卡片，状态为"运行中"
- [ ] tool_call_done 后卡片状态变"完成"，显示结果摘要 + 耗时
- [ ] 节点完成后默认折叠，但有展开按钮可手动看回
- [ ] 用户手动展开/折叠状态在节点期间持久，刷新后回到默认
- [ ] tool_call 失败时卡片显示红色边框 + 错误文字

### 6.3 降级

- [ ] 后端 `astream_writer` 调用失败时（兼容性原因），不抛出，节点正常完成
- [ ] 前端没收到 tool*thinking*_ / tool*call*_ 事件时（旧版本后端），节点仍能渲染（只是没有展开内容）
- [ ] 单个工具失败不影响后续工具调用 / 后续 iteration 的展示

### 6.4 不验收（本期不做）

- Interviewer Chief 的 ReAct loop 工具级展示（chief 现有 `chiefToolCalls` 字段够用）
- 折叠状态持久化到 localStorage
- 导出 trace 为图片/JSON
- 在面试历史详情页重放 trace

---

## 七、文件改动清单（实现期参考）

### 后端

| 操作   | 路径                                                 | 内容                                                                                                           |
| ------ | ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Modify | `backend/app/agents/prepare/research_agent.py`       | ReAct loop 各步骤 emit `tool_thinking_*` / `tool_call_*` 事件；加 `_summarize_args` / `_summarize_result` 辅助 |
| Modify | `backend/app/agents/prepare/graph.py`                | `stream_prepare_events` 增加 `on_custom` 事件分支，转换为前端约定 SSE event                                    |
| Modify | `backend/tests/unit/test_research_agent.py`          | 新增 emit 验证用例（mock `get_stream_writer`）                                                                 |
| Modify | `backend/tests/integration/test_prepare_with_mcp.py` | 验证完整 SSE 事件序列                                                                                          |

### 前端

| 操作   | 路径                                                                            | 内容                                                                                                                            |
| ------ | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Modify | `frontend/lib/prepare-types.ts`                                                 | event 联合追加 5 项；data 追加新字段；新增 `ReactIteration` / `ToolCallStep`；`TraceNodeData` 追加 `reactSteps` / `reactStatus` |
| Modify | `frontend/app/interview/_components/interview-chat.tsx`（或 `agent-trace.tsx`） | SSE handler 加新事件分支，按 `step_id` 聚合到 `reactSteps`                                                                      |
| Modify | `frontend/app/interview/_components/trace-node.tsx`                             | 新增 `reactSteps` prop，研发节点是 `research_agent` 时渲染展开/折叠 + 嵌入 `ReactStepTree`                                      |
| Create | `frontend/app/interview/_components/react-step-tree.tsx`                        | `ReactStepTree` + `IterationGroup` 组件                                                                                         |
| Create | `frontend/app/interview/_components/tool-call-card.tsx`                         | `ToolCallCard` 组件                                                                                                             |
| Create | `frontend/app/interview/_components/react-step-tree.test.tsx`                   | Testing Library 覆盖：流式 token 累积、tool_call 状态切换、折叠行为                                                             |

---

## 八、未来演化

| 阶段       | 能力                                         | 触发                           |
| ---------- | -------------------------------------------- | ------------------------------ |
| 本期（V1） | research_agent 工具级 trace 展示             | 演示价值需求                   |
| V2         | Chief ReAct loop 也用同套 ReactStepTree 渲染 | 复用模式                       |
| V3         | 折叠状态持久化到 localStorage                | 用户反馈"每次刷新都要重新展开" |
| V4         | Trace 历史归档：在面试详情页能查看历史 trace | 反馈复盘需求                   |

---

## 九、面试可讲性

- **协议扩展能力**：在既有 SSE 协议上**追加** 5 个事件类型而不破坏现有客户端——展示"可扩展协议设计"思维
- **流式可视化**：think 文字是逐字流式呈现的（跟 ChatGPT 体感一致）——展示对流式 UX 的把握
- **降级路径**：旧版前端 + 新后端 / 新前端 + 旧后端 都能工作——展示前后向兼容意识
- **数据模型聚合**：把无序的 SSE 事件按 `(iteration, step_id)` 聚合成结构化树——展示"事件驱动 → 结构化状态"的工程思维
