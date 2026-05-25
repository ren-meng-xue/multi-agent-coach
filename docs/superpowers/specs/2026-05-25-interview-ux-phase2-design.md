# 面试房间 UX 阶段 2 设计

**日期**：2026-05-25  
**状态**：待实施  
**范围**：开场白 · Closing 过渡 · 结束报告卡

---

## 背景与问题

当前面试房间（`/interview`）存在两个 UX 缺陷：

1. **空白开场**：进入页面时 `messages = []`，用户看到一片空白，不知道该做什么。
2. **Closing 后静默重启**：面试结束（session `status = completed`）后，用户继续发消息，后端静默创建新 session，前端毫无感知，AI 重新进入 opening 阶段询问基本信息，体验割裂。

此外，面试结束后缺少结构化反馈，用户无法了解自己的表现。

## 产品分层背景

后续会接入 `coach.html` 设计的 Coach 页，作为面试前的个性化引导入口。届时：
- **Coach 页**：处理开场寒暄、历史回顾、目标设置
- **面试房间**：专注于一问一答的正式面试

当前 Coach 页尚未上线，面试房间承担入口职责，需自行提供开场引导。

---

## 设计目标

| 目标 | 衡量标准 |
|------|---------|
| 用户进入页面即知道该做什么 | 有可见的 AI 引导消息 |
| 面试结束有清晰的结束态 | 显示报告卡 + 重置入口 |
| 消除 closing 后的迷失感 | 无静默重启现象 |

---

## 方案选型

报告生成采用**独立 `report_node`**（方案 B），在 `closing_node` 之后单独运行：

- `closing_node`：只生成结束语，职责不变
- `report_node`：专职结构化评分，可独立测试

放弃的方案：
- **扩展 closing_node 兼做评分**：混用职责，prompt 复杂
- **积累式评分（无额外 LLM）**：需改 `DecideNextOutput` + state schema，改动面更大，且 decide 语义是"路由决策"而非"评分"

---

## 架构与数据流

### LangGraph 图变化

```
修改前：closing → END
修改后：closing → report → END
```

### SSE 事件流（closing 阶段）

```
delta(token...) → state(stage=closing) → report({...}) → done
```

### 报告数据结构

4 个评分维度与 `DECIDE_SYSTEM_PROMPT` 中已有的评判维度完全对齐，保证整个面试过程使用同一套标准。

```ts
interface InterviewReport {
  overall_score: number      // 0-10，各维度均值 × 2
  technical_depth: number    // 0-5，技术深度
  quantified_results: number // 0-5，量化结果
  failure_tradeoffs: number  // 0-5，失败与权衡
  structure: number          // 0-5，结构完整性
  highlights: string[]       // 2-3 条具体亮点（中文）
  improvements: string[]     // 2-3 条改进建议（中文）
}
```

---

## 后端改动

### `state.py`

新增字段：

```python
report: dict[str, object]  # 由 report_node 填入，空 dict 表示生成失败
```

### `prompts.py`

新增 `REPORT_SYSTEM_PROMPT`：

```python
REPORT_SYSTEM_PROMPT = (
    "你是面试评估专家。请根据完整的面试对话对候选人进行结构化评分。"
    "评分维度各 0-5 分：technical_depth（技术深度）、quantified_results（量化结果）、"
    "failure_tradeoffs（失败与权衡）、structure（结构完整性）。"
    "overall_score = 各维度均值 × 2，保留一位小数。"
    "highlights：2-3 条具体亮点；improvements：2-3 条具体改进建议。"
    "所有文字字段必须用中文。"
)
```

### `nodes.py`

新增 `ReportOutput` Pydantic 模型和 `report_node`：

```python
class ReportOutput(BaseModel):
    overall_score: float
    technical_depth: float
    quantified_results: float
    failure_tradeoffs: float
    structure: float
    highlights: list[str]
    improvements: list[str]

async def report_node(state: InterviewState) -> InterviewState:
    """面试结束后生成结构化评分报告。"""
    model = _chat_model().with_structured_output(ReportOutput)
    output = await model.ainvoke(
        [SystemMessage(content=REPORT_SYSTEM_PROMPT), *_state_messages(state)]
    )
    if not isinstance(output, ReportOutput):
        log.warning("interviewer_report_unexpected_output", output=str(output))
        return {"report": {}}
    return {"report": output.model_dump()}
```

### `graph.py`

```python
graph.add_node("report", nodes.report_node)
# 原：graph.add_edge("closing", END)
# 改：
graph.add_edge("closing", "report")
graph.add_edge("report", END)
```

### `interview_turn.py`

`stream_interview_turn` 在 `state` 事件后补发 `report` 事件：

```python
if session.stage == "closing":
    # 现有 status/completed_at 更新逻辑不变
    report_data = output.get("report")
    if report_data:
        yield {"event": "report", "data": report_data}
```

---

## 前端改动

### `lib/interview-chat.ts`

新增 `InterviewReport` 类型和 `onReport` 回调：

```ts
export interface InterviewReport {
  overall_score: number
  technical_depth: number
  quantified_results: number
  failure_tradeoffs: number
  structure: number
  highlights: string[]
  improvements: string[]
}

// streamInterviewChat 参数新增：
onReport?: (report: InterviewReport) => void

// event 分发新增：
if (event === "report") {
  params.onReport?.(data as InterviewReport);
}
```

### 新建 `_components/report-card.tsx`

内联在聊天流中的评分卡，样式与面试房间现有风格一致（白底、圆角、细边框）。

布局：
```
本轮面试报告
综合评分  7.2 / 10
──────────────────
技术深度    ████░  4.0 / 5
量化结果    ███░░  3.0 / 5
失败与权衡  ████░  4.0 / 5
结构完整性  ████░  4.0 / 5
──────────────────
亮点
· ...
· ...
改进建议
· ...
· ...
```

### `_components/interview-chat.tsx`

**① 预置开场消息（消除空白状态）**

```ts
const OPENING_MESSAGE: InterviewChatMessage = {
  role: "assistant",
  content: "你好！在开始之前，请告诉我：\n\n**① 目标岗位**（如 AI Agent 工程师）\n**② 目标公司类型**（大厂 / 创业公司 / 外企）\n**③ 想练习的项目背景**（一句话简述）",
}
const [messages, setMessages] = useState([OPENING_MESSAGE]);
```

此消息为纯前端 UI 占位，不存入 DB，不影响后端 opening node 的 prompt 逻辑。

**② report 状态**

```ts
const [report, setReport] = useState<InterviewReport | null>(null);
// streamInterviewChat 调用里加：
onReport: setReport,
```

**③ 报告卡内联渲染**

```tsx
{/* messages.map(...) 之后 */}
{report && <ReportCard report={report} />}
```

**④ closing 后重置入口**

```tsx
{progress.stage === "closing" && (
  <div className="shrink-0 px-5 pb-3">
    <Button variant="outline" onClick={handleNewRound}>
      开始新一轮面试
    </Button>
  </div>
)}
```

输入框始终可用（用户可继续追问），按钮仅提供清晰的重置入口。

**⑤ handleNewRound**

```ts
function handleNewRound() {
  abortRef.current?.abort();
  setMessages([OPENING_MESSAGE]);
  setProgress({ stage: "opening", question_count: 0, total_questions: 5 });
  setReport(null);
}
```

重置后用户下一条消息会在后端自然创建新 session（现有逻辑不变）。

---

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| `report_node` LLM 返回非预期结构 | log warning，返回 `{"report": {}}`，前端不渲染报告卡，closing 消息正常显示 |
| 前端未收到 `report` 事件 | `report` state 保持 `null`，静默降级 |
| closing 阶段超时 | 复用 `llm_timeout_seconds`，无需额外配置 |

---

## 测试覆盖

### 后端

**`tests/unit/test_interviewer_graph.py`**
- `report_node` 正常路径：给定完整对话历史，返回合法 `ReportOutput`，各字段类型正确
- `report_node` 异常路径：LLM 返回非预期结构，返回空 dict，记 warning 日志

**`tests/integration/test_interview_turn_service.py`**
- closing 阶段完整流：`stream_interview_turn` 发出 `report` SSE 事件，data 包含 `overall_score`

### 前端

**`interview-chat.test.tsx`**
- 初始渲染：messages 包含开场消息，不为空数组
- closing 阶段：显示"开始新一轮面试"按钮，输入框仍可用
- `handleNewRound`：messages 重置为 `[OPENING_MESSAGE]`，report 清为 null
- report 事件触发：`ReportCard` 渲染，显示 `overall_score`

**`report-card.test.tsx`**
- 正常数据：各维度分数、亮点、改进建议均正确渲染
- 边界：highlights / improvements 为空数组时不崩溃

---

## 不在本次范围内

- Coach 页接入（阶段 3）
- 报告历史列表 / 分数趋势（阶段 3）
- 面试房间刷新后恢复历史消息（独立 task）
- opening 阶段角色快捷 chip（Coach 页上线后自然解决）
