# Evaluator + Designer 并行执行设计文档

- 日期：2026-06-02
- 范围：interviewer graph 内 chief_execute 并行优化 + Designer 双方案输出

---

## 一、背景与问题

### 1.1 当前串行瓶颈

候选人每次回答后，Chief 执行两次串行阻塞调用：

```
候选人回答
    ↓
chief_execute → await run_evaluator()   ← 阻塞等待（~2-4s）
    ↓
chief_execute → await run_designer()    ← 阻塞等待（~2-4s）
    ↓
chief_respond → 发题给候选人
```

**总延迟 = Evaluator 耗时 + Designer 耗时**，实测约 4-8 秒。

### 1.2 根本原因

`chief_think` 把"评估"和"出题"拆成两个连续 action，每个 action 对应一次 `chief_execute` 调用。两者之间有**表面依赖**（Designer 需要知道分数才能决定追问还是新题），但这个依赖可以通过让 Designer 同时生成两个方案来解除。

### 1.3 目标

- 将每轮延迟从 `Evaluator + Designer` 缩短到 `max(Evaluator, Designer)`
- 保持现有决策规则不变（分数阈值、追问上限）
- 不改动 API 接口、前端、state schema 中用户可见的字段

---

## 二、设计方案

### 2.1 核心思路：乐观并行 + 事后选题

```
候选人回答
    ↓
chief_think → action = "evaluate_and_design"（新 action）
    ↓
chief_execute → asyncio.gather(
    run_evaluator(),          # 评估本轮回答
    run_designer_dual(),      # 同时生成：追问 + 新题 两个方案
)
    ↓ 两者都完成
chief_think → 根据 Evaluator 分数选哪道题：
    分 < 7 且追问次数 < 上限  → 用 followup_question
    分 ≥ 7 或追问次数达上限  → 用 new_question
    → action = "respond"
    ↓
chief_respond → 发题给候选人
```

**关键取舍**：Designer 在不知道评分结果的情况下出题，需要根据对话上下文自行推断追问方向。追问质量略低于现在（现在有 Evaluator 的 `missing_dimensions` 做 focus），但延迟减少约 40-50%。

### 2.2 什么时候走并行、什么时候不走

| 场景                        | 走并行？          | 原因                          |
| --------------------------- | ----------------- | ----------------------------- |
| 首轮（question_count == 0） | 否                | 没有回答可评估，只需 Designer |
| 候选人回答后（正常轮次）    | **是**            | 两个 agent 都需要跑           |
| 候选人表达结束意图          | 否                | 直接 closing，不需要出题      |
| 追问次数达上限              | 否（仅 Designer） | 结论已确定是新题，无需评估    |

### 2.3 决策规则（与现有一致，不变）

```python
def _pick_question(eval_report, designer_dual, followup_count, max_followups):
    score = _score(eval_report)
    answer_sufficient = score >= 7.0 and not _missing_dimensions(eval_report)
    if answer_sufficient or followup_count >= max_followups:
        return designer_dual["new_question"]
    return designer_dual["followup_question"]
```

---

## 三、需要改动的内容

### 3.1 Designer 输出 schema 新增双方案字段

**文件**：`backend/app/agents/designer/state.py`

```python
class DesignerState(TypedDict):
    ...
    # 新增
    followup_question: str   # 并行模式下的追问方案
    new_question: str        # 并行模式下的新题方案
    # 现有字段保留（单方案路径仍可用）
    output: dict             # {"question_text": ..., "source": ...}
```

### 3.2 Designer 新增 dual 节点

**文件**：`backend/app/agents/designer/nodes.py`

新增 `design_dual` 节点：单次 LLM 调用，prompt 要求同时输出追问和新题，使用对话上下文推断追问方向（不依赖 Evaluator 的 `missing_dimensions`）。

**新增输出 Pydantic model**：

```python
class DesignerDualOutput(BaseModel):
    followup_question: str
    new_question: str
    source: Literal["generated", "prepared"]
```

### 3.3 Designer graph 新增 dual 路径

**文件**：`backend/app/agents/designer/graph.py`

新增 `run_designer_dual()` 函数，走 `design_dual → respond_to_chief` 路径，返回 `DesignerDualOutput`。

### 3.4 chief_think 新增 evaluate_and_design action

**文件**：`backend/app/agents/interviewer/chief.py`

在 `chief_think` 的判断逻辑里：

```python
# 修改前（两个连续 action）：
elif not state.get("evaluator_report"):
    action = "evaluate_answer"
elif not state.get("designer_output"):
    action = "design_question"

# 修改后（合并为一个并行 action）：
elif not state.get("evaluator_report") and not state.get("designer_dual_output"):
    action = "evaluate_and_design"
elif state.get("evaluator_report") and state.get("designer_dual_output"):
    # 在 chief_think 里直接选题，不再需要额外 execute
    action = "respond"
```

### 3.5 chief_execute 新增并行分支

**文件**：`backend/app/agents/interviewer/chief.py`

```python
elif action == "evaluate_and_design":
    eval_report, designer_dual = await asyncio.gather(
        _execute_evaluate(state),
        _execute_design_dual(state),
    )
    # 选题
    question = _pick_question(
        eval_report,
        designer_dual,
        state.get("followup_count", 0),
        state.get("max_followups", 2),
    )
    partial = {
        "evaluator_report": eval_report,
        "designer_dual_output": designer_dual,
        "designer_output": {"question_text": question, "source": designer_dual.source},
        ...
    }
```

### 3.6 InterviewState 新增字段

**文件**：`backend/app/agents/interviewer/state.py`

```python
designer_dual_output: dict | None   # 并行模式下 Designer 的双方案原始输出
```

---

## 四、不改动的内容

- FastAPI 路由层、SSE 事件格式
- `chief_respond` 逻辑（仍然读 `designer_output["question_text"]`）
- 首轮 `design_question` 单方案路径
- `closing_node`、`report_node`
- 前端所有代码
- 数据库 schema

---

## 五、降级与容错

| 失败场景           | 处理方式                                                                  |
| ------------------ | ------------------------------------------------------------------------- |
| Evaluator 失败     | `eval_report = {"scoring": {}}` → 分数为 0 → 走追问路径（如追问未到上限） |
| Designer dual 失败 | 降级到现有串行路径（先 evaluate 再 design）                               |
| 两者都失败         | 已有 `chief_respond` fallback 兜底                                        |

---

## 六、验收标准

1. 候选人回答后，后端日志中 Evaluator 和 Designer 的调用时间戳**重叠**（证明并行）
2. 分数 < 7 且追问未到上限时，发出的是追问而非新题
3. 分数 ≥ 7 或追问已到上限时，发出的是新题
4. 前端界面、SSE 事件流与现在行为一致
5. 首轮行为不变（只走 Designer 单方案）
