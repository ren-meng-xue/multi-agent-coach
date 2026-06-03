# Trace 面板 UX 修复设计文档

- 日期：2026-06-02
- 范围：`backend/app/agents/interviewer/graph.py` + `frontend/app/interview/_components/trace-node.tsx`

---

## 一、背景与问题

当前上线后 trace 面板有两个 UX 问题：

### 问题 1：准备面板一次性展示所有 5 道题目

`trace-node.tsx:129-187` 专门为 `question_gen` 节点做了题目 JSON 解析和卡片渲染。LLM 生成 5 道题后全部展示在准备阶段面板中。用户在面试开始前就已看到全部题目，面试体验被破坏。

### 问题 2：面试官 trace 面板显示内部子 agent 节点名，用户看不懂

evaluator 和 designer 是独立的 LangGraph 子图。父图用 `astream_events` 时，子图内部节点事件会冒泡上来：

- **Evaluator 子图**：`analyze_answer → update_profile → respond_to_chief`
- **Designer 子图**：`design → validate → respond_to_chief`

当前 `_HIDDEN_NODES` 仅包含 `{load_context, report, chief_execute}`，没有包含这些子图内部节点。这些节点不在 `_PUBLIC_TRACE_NODES` 映射中，前端因此显示原始 id 作为 label，且无 token 内容，最终呈现为：

```
- design:
  (无详细信息)
- validate:
  (无详细信息)
- respond_to_chief:
  (无详细信息)
```

用户完全看不懂这些是什么。

---

## 二、解决方案

### 2.1 隐藏子图内部节点

在 `graph.py` 的 `_HIDDEN_NODES` 中加入所有 designer/evaluator 子图的内部节点名，阻断其 event 冒泡到前端。

这些节点执行的功能（评估打分、设计题目）的结果已通过 `chief_think` 的 `node_done` payload 向上传递：

- 评估结果：`candidate_level`, `latent_signals`, `missing_dimensions`, `summary_score`
- 工具调用：`chief_tool_calls` 徽章（"评估回答"、"设计题目"）

用户依然能看到 chief 的决策推理文本和评估结论。

### 2.2 补上出题 agent 结果到 chief_think node_done

当前 `chief_think` node_done 已携带评估结果，但未携带 designer 的题目输出。增加以下字段：

```python
# graph.py chief_think node_done 新增
"designed_question": node_dict.get("designer_output", {}).get("question_text", ""),
"designed_category": node_dict.get("designer_output", {}).get("question_category", "technical"),
"designed_source": node_dict.get("designer_output", {}).get("source", "llm"),
```

前端 `trace-node.tsx` 在 `chief_think` 节点中渲染一行："下一题：[category] designed_question"。

### 2.3 准备面板不渲染题目卡片

`trace-node.tsx` 中 `question_gen` 节点不再做 JSON 解析和题目卡片渲染。改为显示：

```
已为你定制 5 道专属面试题，面试中将逐题呈现。
```

具体改动：删除 `id === "question_gen" && tokens` 分支的 JSON 解析 + 卡片渲染逻辑，替换为固定文案。

**不变**：后端仍生成 5 道题，存入 `prepared_questions`，面试官 `ask_question_node` / `designer._prepared_question()` 仍从中逐题抽取。

---

## 三、改动后一个面试轮次的 trace 面板

```
AI 思考过程 - 分析与出题
  ┌─ 规划工具调用 (chief_think) ─────────────────────
  │ → 候选人展示了 Vue 组件通信的多种方式，但未涉及
  │   实际性能优化和异常处理经验，建议追问…
  │ [评估回答] [设计题目]
  │ 中级 │ 项目主导力 · 组件抽象 │ 缺失：异常处理
  │ 📝 新题：请描述你处理过的最复杂的前端异常场景…
  └──────────────────────────────────────────────────
  ┌─ 组织面试回复 (chief_respond) ───────────────────
  │ → (面试官的实际回复文本)
  └──────────────────────────────────────────────────
```

---

## 四、文件变更清单

| 文件                                                    | 改动                                                                                                                                                                                                     |
| ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/app/agents/interviewer/graph.py`               | `_HIDDEN_NODES` 增加 `design`, `validate`, `respond_to_chief`, `analyze_answer`, `update_profile`, `design_dual`；`chief_think` node_done 增加 `designed_question`/`designed_category`/`designed_source` |
| `frontend/lib/prepare-types.ts`                         | `TraceNodeData` 增加可选字段 `designedQuestion`/`designedCategory`/`designedSource`                                                                                                                      |
| `frontend/app/interview/_components/trace-node.tsx`     | 删除 `question_gen` 的题目 JSON 解析渲染逻辑，改为固定文案；`chief_think` / `chief_respond` 节点增加出题信息展示                                                                                         |
| `frontend/lib/interview-chat.ts`                        | `InterviewTraceNodeEvent` 增加 `designedQuestion` 等字段                                                                                                                                                 |
| `frontend/app/interview/_components/interview-chat.tsx` | `flushTraceBuffer` 中 `phase === "done"` 分支传递新字段                                                                                                                                                  |

---

## 五、测试策略

### 后端

- `tests/unit/test_prepare_nodes.py`：验证 `question_gen_node` 仍生成 5 道题，不受前端改动影响
- 手动验证：启动面试 → 打开浏览器 → 确认准备面板不再显示题目卡片 → 面试中题目逐题出现
- 手动验证：面试 trace 面板不再出现 `design`/`validate`/`respond_to_chief` 等原始节点名

### 前端

- `pnpm typecheck` 通过
- `pnpm build` 通过

### 不做

- 不新增后端单元测试（改动仅涉及节点名过滤列表和 node_done payload 扩展，现有测试覆盖已足够）
- 不改动 evaluator/designer 子图结构
- 不改动 prepare pipeline 的题目生成逻辑
