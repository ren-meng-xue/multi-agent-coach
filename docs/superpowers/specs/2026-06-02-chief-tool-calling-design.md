# Chief Tool Calling 重构设计文档

- 日期：2026-06-02
- 范围：`backend/app/agents/interviewer/chief.py` + 关联 state / graph / eval 适配

---

## 一、背景与目标

当前 `chief_think` 的决策机制是**假 ReAct**：LLM 只负责流式输出"思考文本"供 SSE 展示，真正的行动决策由 Python if/else 完成；`chief_next_action` 是纯代码字符串，不是 LLM 的输出。

本次改造目标：用 `model.bind_tools([...])` 让 Chief LLM **真正输出 tool_calls** 来决定调哪个子 agent，实现名副其实的 ReAct 循环。并行工具调用（evaluate + design 同时跑）作为自然结果而非特殊分支。

**不改动**：chief_respond、coach、prepare、前端、数据库、API 接口。

---

## 二、核心架构

### 2.1 ReAct 循环（每轮面试 turn）

```
chief_messages = [
    SystemMessage(CHIEF_SYSTEM_PROMPT + 当前上下文),
    HumanMessage(候选人最新回答)
]

loop (最多 MAX_CHIEF_ITERATIONS 次):
    response = await model.bind_tools(tools).ainvoke(chief_messages)
    chief_messages.append(response)

    if response.tool_calls 为空:
        # LLM 认为工具结果已够，输出最终推理文本
        chief_thoughts.append(response.content)
        break

    # 并行执行所有 tool_calls（单 tool 或多 tool 均支持）
    results = await asyncio.gather(*[execute_tool(tc) for tc in response.tool_calls])
    for tc, result in zip(response.tool_calls, results):
        chief_messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
        _store_result_to_state(tc["name"], result, partial)  # 写 evaluator_report / designer_dual_output

# chief_respond 用 partial 里的结果做最终问题格式化（同现在）
```

### 2.2 并行工具调用

LLM 可在一次响应里同时输出多个 tool_call（Claude API 原生支持）：

```
# LLM 输出示例（首次收到候选人回答后）
AIMessage.tool_calls = [
    {"name": "evaluate_answer", "args": {}},
    {"name": "design_question", "args": {"focus": "dual"}}
]
↓ asyncio.gather 并行执行
evaluator_report + designer_dual_output 同时写入 state
↓ LLM 再次调用（看到两个 ToolMessage）
AIMessage.tool_calls = []  → 输出推理文本 → break
↓
chief_respond 用 _pick_question() 选追问或新题
```

`focus="dual"` 让 designer 同时准备追问和新题，不依赖 eval 结果，因此可以与 `evaluate_answer` 并行跑。

---

## 三、工具定义

三个工具以**闭包工厂**形式定义，每次 `chief_think` 调用时绑定当前 state 上下文：

```python
def _make_chief_tools(state: InterviewState, partial: dict) -> list:

    async def _evaluate_answer() -> str:
        """评估候选人最新回答的质量，更新画像，返回决策建议。
        收到候选人回答后必须首先调用（首轮启动除外）。"""
        result = await run_evaluator({
            "session_id": state["session_id"],
            "latest_answer": _last_human_message(state),
            "conversation_context": _conversation_context(state),
            "existing_profile": state.get("candidate_profile") or {},
            ...
        })
        # 写入 partial（不修改 state，由外层合并）
        partial["evaluator_report"] = result
        partial["candidate_profile"] = result.get("updated_profile") or state.get("candidate_profile")
        partial["turn_evaluations"] = _merge_evals(state, result)
        return json.dumps({
            "summary_score": result.get("scoring", {}).get("summary_score"),
            "report_text": result.get("report_text"),
            "missing_dimensions": result.get("scoring", {}).get("missing_dimensions"),
        }, ensure_ascii=False)

    async def _design_question(focus: str = "new_question") -> str:
        """设计下一个面试问题或追问。
        focus: "new_question"=新题, "dual"=同时准备追问和新题（与 evaluate_answer 并行时使用）。
        首轮启动调用此工具，focus="new_question"。"""
        if focus == "dual":
            result = await run_designer_dual({...})
            partial["designer_dual_output"] = result
        else:
            result = await run_designer({"focus": focus, ...})
            partial["designer_output"] = result
        return json.dumps(result, ensure_ascii=False)

    async def _query_profile() -> str:
        """获取候选人当前能力画像摘要，不触发 LLM。"""
        profile = {**state.get("candidate_profile") or {}, **partial.get("candidate_profile", {})}
        return json.dumps(profile, ensure_ascii=False)

    return [
        StructuredTool.from_function(coroutine=_evaluate_answer, name="evaluate_answer", ...),
        StructuredTool.from_function(coroutine=_design_question, name="design_question",
                                     args_schema=_DesignQuestionArgs, ...),
        StructuredTool.from_function(coroutine=_query_profile, name="query_profile", ...),
    ]
```

**关键设计**：tools 写入 `partial` dict 而非直接修改 state；外层函数在 loop 结束后统一合并到返回 state。

---

## 四、State 变更

### 新增字段

```python
chief_messages: list[BaseMessage]
# Chief 自己的对话历史（SystemMessage + HumanMessage + AIMessage + ToolMessage）
# 每轮面试 turn 开始时初始化，不跨 turn 累积
```

### 移除字段

```python
chief_next_action: str   # 被 chief_messages[-1].tool_calls 替代
chief_tool_input: dict   # 被 tool_call args 替代
```

### 保留字段（不变）

`chief_iteration`, `chief_thoughts`, `chief_tool_results`, `evaluator_report`, `designer_output`, `designer_dual_output`, `candidate_profile`, `turn_evaluations`

---

## 五、节点变更

### `chief_think`（重构）

**改前**：`_chief_reason_stream`（流式+丢弃）+ Python if/else 决定 `chief_next_action`

**改后**：

1. 初始化 `chief_messages`（首次迭代）或读取已有值
2. 调用 `model.bind_tools(tools).ainvoke(chief_messages)`
3. append response 到 chief_messages
4. 返回更新后的 `chief_messages`（tool_calls 信息在 AIMessage 里）

无 Python 决策逻辑，只是 LLM 调用 + 消息追加。

### `chief_execute`（重构）

**改前**：读 `chief_next_action` 字符串 dispatch

**改后**：

1. 读 `chief_messages[-1].tool_calls`
2. 用 `_make_chief_tools(state, partial)` 构建 tool_map
3. `asyncio.gather(*[tool_map[tc["name"]].arun(tc["args"]) for tc in tool_calls])`
4. 追加 ToolMessages 到 chief_messages
5. 合并 `partial` 到返回 state

### `route_after_chief_think`（小改）

```python
# 改前
def route_after_chief_think(state):
    action = state.get("chief_next_action", "respond")
    if action in {"evaluate_and_design", ...}:
        return "chief_execute"
    return "chief_respond"

# 改后
def route_after_chief_think(state):
    msgs = state.get("chief_messages") or []
    last = msgs[-1] if msgs else None
    if isinstance(last, AIMessage) and last.tool_calls:
        return "chief_execute"
    return "chief_respond"
```

### `chief_respond`（不变）

仍然从 state 读 `evaluator_report`、`designer_output`、`designer_dual_output`，用 `_pick_question()` 选题，处理 closing/prepared question 格式化。

---

## 六、SSE 显示

`graph.py` 的 `chief_think` node_done 事件：

```python
# 改前
payload["chief_next_action"] = node_dict.get("chief_next_action", "")

# 改后
msgs = node_dict.get("chief_messages") or []
last = msgs[-1] if msgs else None
tool_calls = [tc["name"] for tc in (getattr(last, "tool_calls", None) or [])]
payload["chief_tool_calls"] = tool_calls      # e.g. ["evaluate_answer", "design_question"]
payload["chief_thoughts"] = node_dict.get("chief_thoughts", [])
```

前端调度台展示 `chief_tool_calls` 代替原来的 `chief_next_action`（字段名变，渲染逻辑相似）。

---

## 七、Eval 适配（system_calls.py）

`_call_agent_quality` 的 loop 逻辑需更新：

```python
# 改前：检查 chief_next_action 字符串
action = state.get("chief_next_action", "respond")
if action in {"evaluate_and_design", ...}:
    state = await chief_execute(state)

# 改后：检查 chief_messages[-1].tool_calls
msgs = state.get("chief_messages") or []
last = msgs[-1] if msgs else None
if isinstance(last, AIMessage) and last.tool_calls:
    state = await chief_execute(state)
```

初始化 state 时新增 `chief_messages: []`，移除 `chief_next_action` / `chief_tool_input`。

---

## 八、CHIEF_SYSTEM_PROMPT 更新

需明确告知 Chief 可用工具及何时并行调用：

关键指令增加：

- 收到候选人回答后，同时调用 `evaluate_answer` 和 `design_question(focus="dual")`
- 首轮启动只调用 `design_question(focus="new_question")`，跳过评估
- 候选人表达结束意图时不调用工具，直接输出"收尾"文本
- 题数已满且回答充分时直接输出"收尾"文本
- 不万金油追问；一次只提一个问题

---

## 九、文件变更清单

| 文件                                              | 改动                                                                                 |
| ------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `backend/app/agents/interviewer/chief.py`         | 重构 chief_think / chief_execute / route_after_chief_think；新增 `_make_chief_tools` |
| `backend/app/agents/interviewer/chief_prompts.py` | 更新 CHIEF_SYSTEM_PROMPT，说明工具及并行策略                                         |
| `backend/app/agents/interviewer/state.py`         | 新增 `chief_messages`；移除 `chief_next_action`, `chief_tool_input`                  |
| `backend/app/agents/interviewer/graph.py`         | 更新 node_done SSE 事件（chief_tool_calls 替代 chief_next_action）                   |
| `backend/app/eval/system_calls.py`                | 更新 `_call_agent_quality` 的 loop 条件判断                                          |

**不动**：designer、evaluator、coach、prepare、前端、API、数据库。

---

## 十、明确不做

1. 修改 `chief_respond` 的格式化逻辑
2. 让 Chief LLM 的最终文本输出直接作为候选人面试官回复（仍由 Python chief_respond 处理）
3. 引入 LangGraph ToolNode（改动 graph 结构代价过大）
4. 把 prepare Supervisor 改成 tool calling
5. 跨 turn 保留 chief_messages（每轮重新初始化，不累积）

---

## 十一、测试策略

### 必须更新

- `tests/unit/test_chief_reasoning.py`：mock `model.bind_tools().ainvoke` 返回 `AIMessage(tool_calls=[...])`，验证路由到 chief_execute
- `tests/unit/test_chief_safety.py`：验证 iteration 超限 / 终止词识别 / 首轮跳过评估（这些靠 prompt 指令，需在 mock 层验证 chief_messages 内容）

### 新增

- `tests/unit/test_chief_tool_calling.py`：
  - 验证 evaluate_answer + design_question 并行执行（asyncio.gather 路径）
  - 验证单工具调用路径
  - 验证 ToolMessage 正确追加到 chief_messages

### 集成验证

完整面试 3-5 轮：节点不崩 → SSE `chief_tool_calls` 字段出现 → 报告正常产出。
