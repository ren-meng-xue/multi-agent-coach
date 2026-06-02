# Phase 4+ 设计文档：候选人建模 + Latent Signals + 追问策略

**日期**：2026-05-28
**范围**：面试官 LangGraph 子图（evaluator / followup / master）+ SSE 透传 + 前端 trace 节点渲染
**目标**：把面试官 Agent 从"关键词触发的审讯器"改造成"基于候选人画像 + 隐含工程信号的引导者"。

---

## 一、背景与问题

### 1.1 当前进度

- 第 1～3 步：流式对话、单面试官 Agent、JD 分析 + 出题 Orchestrator 全部已上线。
- 第 4 步「评估 Agent + 并行评分」：evaluator_node 已实现并写入 `turn_evaluations`，每轮 4 维评分 + 流式 bullets，前端通过 `TurnTraceCard` 可见。但其行为仍有缺陷（见下）。
- 第 5 / 6 步未启动。

### 1.2 真实场景暴露的缺陷

人类候选人在面试中表达：

> 我没做过 AI Agent 的项目，这是第一个 multi-agent。一开始不知道怎么落地项目，不知道事件流，工具事件、AI 事件、人类回复事件分不清。后端我也不熟，但用了 Claude Code CLI + Codex，定义 spec、做 plan-first，再用其他模型敲代码，降本增效，最后用 review / qa-only 兜底。

系统的实际反应：抓到 `Claude / Codex / GPT` 三个名词，连续追问"为什么选 GPT 5.5"、"参数怎么调"、"有没有代码示例"。

根因（落到代码）：

| 现象 | 代码根因 |
|------|---------|
| 只会关键词匹配，丢失"事件流 / orchestration / state lifecycle"等隐含信号 | `evaluator_node` 只输出 4 维分数 + 30 字 bullets，无结构化能力提取 |
| 追问机械、万金油 | `FOLLOWUP_SYSTEM_PROMPT` 只指示「基于回答深挖」，未告知"追问什么方向" |
| 不区分 junior / senior | `InterviewState` 无任何候选人画像字段，所有人按同一标准追问 |
| 局部理解、不做跨轮综合 | `_build_evaluator_context` 只截取最近一题问题 + 最近一句用户回答 |
| MASTER 决策粒度过粗 | 只决定 `chain`（评估 / 追问 / 出题 / 收尾），不决定"追问朝哪个方向" |

### 1.3 本期目标（一句话）

让 evaluator 不再只打分，而是同时**提取候选人画像 + 隐含工程信号**；让 followup **基于这些信号选择追问方向**；让 master **告诉 followup 朝哪个方向追问**。前端在 evaluator 节点完成时**追加渲染**这些新字段。

---

## 二、设计原则

1. **State 向后兼容**：所有新字段 `total=False` 可选，旧序列化数据不报错。
2. **prompt 是行为载体**：本期不引入新节点、不动 graph 拓扑、不动 DB schema。
3. **失败回退**：LLM 输出新字段失败时，节点继续工作（评分照常打、追问照常出），仅缺失新字段。
4. **token 成本可控**：evaluator 跨轮上下文有截断上限。
5. **不做的事**：跨 session 的 candidate model 累积、reflexion 反思、LLM-as-Judge —— 全部留给后续阶段。

---

## 三、数据流

```
用户回答提交
  ↓
load_context (不变)
  ↓
master_node
  ├─ 输入：跨轮 latent_signals + 最新回答片段 + question_count + followup_count
  ├─ Phase 1 流式推理（保留现状，UI 已渲染）
  ├─ Phase 2 结构化输出：
  │    - chain（原有）
  │    - followup_focus（新增）：追问应该朝哪个方向，枚举值：
  │          architecture / tradeoff / failure_handling /
  │          scaling / quantification / latent_signal:<signal_key> /
  │          none（不需要 focus 时用，例如 closing）
  │    - reason（原有）
  ↓
evaluator_node（chain 含时）
  ├─ 输入：完整 messages（截断至最近 N 条） + target_role
  ├─ 输出 _EvaluatorScoring：
  │    - 原 4 维评分（不变）
  │    - bullets（不变）
  │    - candidate_level（新）：beginner / junior / mid / senior
  │    - latent_signals（新）：list[str]，候选人未明说但可推断的工程能力 tag
  │    - missing_dimensions（新）：list[str]，本轮回答缺失的关键点
  ├─ 写入 turn_evaluations[-1]
  └─ 把 latent_signals 累计写入 state.candidate_profile（去重保序）
  ↓
followup_node（chain 含时）
  ├─ 输入：followup_focus + latent_signals + missing_dimensions + 最近一轮上下文
  ├─ Prompt 改造：从"基于回答深挖"改为"针对 focus + 信号生成一个具体问题"
  └─ 输出 assistant_message（流通道不变）
```

---

## 四、State / Schema 变更

### 4.1 `backend/app/agents/interviewer/state.py`

```python
class TurnEvaluation(TypedDict, total=False):
    # 原有字段 (不变)
    question_index: int
    followup_index: int
    bullets: list[str]
    technical_depth: float
    quantified_results: float
    failure_tradeoffs: float
    structure: float
    summary_score: float
    # 新增
    candidate_level: Literal["beginner", "junior", "mid", "senior"]
    latent_signals: list[str]
    missing_dimensions: list[str]


class CandidateProfile(TypedDict, total=False):
    """跨轮累积的候选人画像。只在本次 session 内累积。"""
    latest_level: Literal["beginner", "junior", "mid", "senior"]
    latent_signals: list[str]  # 累积去重
    last_updated_turn: int


class InterviewState(TypedDict, total=False):
    # 原有字段 (不变)
    ...
    # 新增
    candidate_profile: CandidateProfile
    followup_focus: str  # 由 master 输出，followup 消费，单次有效
```

### 4.2 `_EvaluatorScoring`（Pydantic）

```python
class _EvaluatorScoring(BaseModel):
    bullets: list[str] = []
    technical_depth: float = 5.0
    quantified_results: float = 5.0
    failure_tradeoffs: float = 5.0
    structure: float = 5.0
    summary_score: float = 5.0
    # 新增
    candidate_level: Literal["beginner", "junior", "mid", "senior"] = "junior"
    latent_signals: list[str] = []
    missing_dimensions: list[str] = []
```

### 4.3 `_InterviewMasterDecision`（Pydantic）

```python
class _InterviewMasterDecision(BaseModel):
    chain: list[str] = []
    reason: str = ""
    # 新增
    followup_focus: str = ""  # 空串表示无 focus
```

**注意**：`followup_focus` 只是一个字符串，不做严格枚举校验（LLM 容易输出超出枚举的值）；followup_node 内部对未知值做兜底（按"general"处理）。

---

## 五、Prompt 改造

### 5.1 `EVALUATOR_SCORING_PROMPT`（改）

在原 4 维评分指令后追加：

```
【额外字段】
- candidate_level：根据回答口吻、术语熟练度、是否承认不熟悉，判断 beginner/junior/mid/senior。
  · beginner：首次做该领域、明显在学习；junior：1-2 年经验；mid：3-5 年；senior：架构级
- latent_signals：候选人未明说但能推断出的工程能力 tag（小写下划线），例如：
  · workflow_orchestration / event_driven_architecture / state_management /
    prompt_engineering / cost_optimization / fallback_strategy / observability
  · 每条 tag 必须能从原话推断出来；编不出来就留空数组
- missing_dimensions：本轮回答缺失的关键点，从以下集合中选：
  · architecture / quantification / failure_handling / tradeoff / scaling / debugging
```

### 5.2 `EVALUATOR_REASONING_PROMPT`（小改）

允许在 2-3 条 bullets 中显式包含一条"隐含信号识别"，例如：

```
·候选人提到事件分类 → 已涉及 orchestration
```

### 5.3 `MASTER_DECISION_PROMPT`（改）

在 chain 之外追加 `followup_focus` 输出指令。同时把"候选人画像 + 最近 latent signals"塞进 context。

### 5.4 `FOLLOWUP_SYSTEM_PROMPT`（重写）

```
你是一位资深技术面试官。请基于以下信息生成一个具体追问。

【信息】
- followup_focus：本轮追问方向（如 architecture / tradeoff / latent_signal:workflow_orchestration）
- latent_signals：候选人本轮暴露的隐含能力 tag
- missing_dimensions：候选人本轮回答缺失的关键点
- 候选人最近回答（节选）

【准则】
1. 一次只问一个问题。
2. 优先级：followup_focus > missing_dimensions > latent_signals。
3. 如果 followup_focus 指向某个 latent_signal，请用工程化语言"翻译"出来再问。
   例：信号是 workflow_orchestration → "你提到要管理 tool/AI/human 三类事件，能展开说说这套 event lifecycle 是怎么设计的吗？"
4. 拒绝万金油追问：禁止问"为什么选这个模型 / 参数怎么调 / 有没有代码示例"，除非候选人原话提到模型选型/参数。
5. 候选人是 beginner 时，避免一上来就追问 benchmark / 分布式 / 参数。
6. 语气专业、克制。
```

### 5.5 不动的 prompt

- `QUESTION_SYSTEM_PROMPT`（已经包含"拒绝廉价赞美"等准则）
- `CLOSING_SYSTEM_PROMPT`
- `REPORT_*` 系列（不动；新字段对 report 透明）
- `MASTER_REASONING_PROMPT`（可微调让推理 bullet 更贴近 focus，但不强求）

---

## 六、节点函数改造（`nodes.py`）

### 6.1 `_build_evaluator_context`

```python
def _build_evaluator_context(state: InterviewState) -> str:
    """改：保留最近 N 轮上下文 + 候选人画像。"""
    MAX_TURNS = 8  # 最近 8 条消息（约 4 轮一问一答），token 上限兜底
    msgs = state.get("messages", [])[-MAX_TURNS:]
    transcript = []
    for m in msgs:
        role = "面试官" if getattr(m, "type", "") == "ai" else "候选人"
        text = str(getattr(m, "content", ""))[:400]
        transcript.append(f"{role}：{text}")

    profile = state.get("candidate_profile") or {}
    signals_so_far = profile.get("latent_signals") or []

    parts = []
    if state.get("target_role"):
        parts.append(f"目标岗位：{state['target_role']}")
    if signals_so_far:
        parts.append(f"已识别的隐含信号：{', '.join(signals_so_far[:10])}")
    parts.append("【最近对话】")
    parts.extend(transcript)
    return "\n".join(parts)
```

### 6.2 `evaluator_node`

把 `_EvaluatorScoring` 的新字段写进 `TurnEvaluation` 和 `candidate_profile`：

```python
entry: TurnEvaluation = {
    ...原有字段,
    "candidate_level": scoring.candidate_level,
    "latent_signals": list(scoring.latent_signals),
    "missing_dimensions": list(scoring.missing_dimensions),
}
# 累积 candidate_profile
old_profile = state.get("candidate_profile") or {}
old_signals = old_profile.get("latent_signals") or []
new_signals = list(dict.fromkeys(old_signals + list(scoring.latent_signals)))[:20]
new_profile: CandidateProfile = {
    "latest_level": scoring.candidate_level,
    "latent_signals": new_signals,
    "last_updated_turn": state.get("question_count", 0),
}
return {**state, "turn_evaluations": updated, "candidate_profile": new_profile}
```

### 6.3 `_build_master_context`

加进画像信息：

```python
profile = state.get("candidate_profile") or {}
if profile.get("latest_level"):
    parts.append(f"候选人画像：{profile['latest_level']}；已识别信号：{', '.join(profile.get('latent_signals', [])[:5])}")
```

### 6.4 `master_node`

把 `decision.followup_focus` 写入 state：

```python
return {
    **state,
    "chain": final_chain,
    "master_reason": reason,
    "followup_focus": decision.followup_focus,
}
```

### 6.5 `followup_node`

读取 `followup_focus / latent_signals / missing_dimensions`，把它们写进追问 prompt 的 SystemMessage：

```python
async def followup_node(state: InterviewState) -> InterviewState:
    focus = state.get("followup_focus", "")
    last_eval = (state.get("turn_evaluations") or [{}])[-1]
    latent = last_eval.get("latent_signals", []) or []
    missing = last_eval.get("missing_dimensions", []) or []
    extra_ctx = (
        f"\n【本轮追问信号】\n"
        f"- followup_focus: {focus or '无'}\n"
        f"- latent_signals: {', '.join(latent) or '无'}\n"
        f"- missing_dimensions: {', '.join(missing) or '无'}"
    )
    text = await _generate_text(FOLLOWUP_SYSTEM_PROMPT + extra_ctx, state)
    return {
        "stage": "interview",
        "followup_count": state.get("followup_count", 0) + 1,
        "assistant_message": text,
    }
```

---

## 七、SSE / 前端透传

### 7.1 `graph.py` 的 evaluator `node_done` payload

在原 `summary_score` 之外追加：

```python
if ev_node == "evaluator" and isinstance(node_dict, dict):
    evals = node_dict.get("turn_evaluations") or []
    if evals:
        last = evals[-1]
        payload["summary_score"] = last.get("summary_score")
        payload["candidate_level"] = last.get("candidate_level")
        payload["latent_signals"] = last.get("latent_signals", [])
        payload["missing_dimensions"] = last.get("missing_dimensions", [])
```

### 7.2 `master` `node_done` payload

追加 `followup_focus`：

```python
if ev_node == "master" and isinstance(node_dict, dict):
    payload["chain"] = node_dict.get("chain", [])
    payload["followup_focus"] = node_dict.get("followup_focus", "")
```

### 7.3 前端 `lib/prepare-types.ts`（或对应类型文件）

`InterviewTraceNodeEvent` 在 `phase === "done"` 时新增可选字段：

```ts
candidateLevel?: "beginner" | "junior" | "mid" | "senior";
latentSignals?: string[];
missingDimensions?: string[];
followupFocus?: string;
```

`TraceNodeData` 增加：

```ts
candidateLevel?: ...;
latentSignals?: string[];
missingDimensions?: string[];
```

### 7.4 `trace-node.tsx` 渲染（追加块）

evaluator 节点完成后，在 reasoning bullets 下面追加一个"画像 + 信号"区域：

```tsx
{id === "evaluator" && status === "done" && (candidateLevel || latentSignals?.length || missingDimensions?.length) && (
  <div className="mt-2 flex flex-wrap gap-1.5 pl-2.5 border-l-[1.5px] border-black/[0.04] dark:border-white/[0.04]">
    {candidateLevel && (
      <span className="rounded bg-[#E1F5F2] text-[#0D6B5E] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider">
        {candidateLevel}
      </span>
    )}
    {latentSignals?.map((sig) => (
      <span key={sig} className="rounded bg-[#534AB7]/5 text-[#534AB7]/70 px-1.5 py-0.5 text-[9px] font-medium">
        {sig}
      </span>
    ))}
    {missingDimensions?.length ? (
      <span className="text-[9px] text-rose-500/60">缺失：{missingDimensions.join(" · ")}</span>
    ) : null}
  </div>
)}
```

不动现有布局、颜色系统、状态机。

---

## 八、测试策略

### 8.1 后端单测（pytest）

- `tests/test_interviewer_state.py`（新建或扩展）：
  - `TurnEvaluation` 默认无新字段也能初始化。
  - `CandidateProfile` 累积去重保序、上限 20。
- `tests/test_interviewer_nodes.py`（扩展）：
  - **evaluator 跨轮上下文**：mock messages 多于 8 条时只保留最近 8 条。
  - **evaluator 新字段写入 state**：mock LLM 返回 `latent_signals=["x","y"]`、`candidate_level="junior"`，断言 `turn_evaluations[-1]` 与 `candidate_profile` 含对应字段。
  - **candidate_profile 累积**：连续两轮 evaluator 调用，前轮 `["a","b"]`、后轮 `["b","c"]` → 累积 `["a","b","c"]`。
  - **followup 消费 focus**：state 携带 `followup_focus="architecture"` + `latent_signals=["workflow_orchestration"]`，断言 prompt（通过 mock 捕获 SystemMessage）含 `followup_focus` 字符串与信号。
  - **master 输出 followup_focus**：mock 决策返回 `followup_focus="tradeoff"`，断言写入 state。
  - **回退**：LLM 抛错时，evaluator 仍返回原结构（无新字段时不崩）。

### 8.2 前端单测（vitest）

- `trace-node.test.tsx`：evaluator done 且带 latentSignals 时，渲染对应 chips；都没有时不渲染额外块。
- `interview-chat.test.tsx`：`node_done` 携带新字段时，正确合并进 `TraceNodeData`。

### 8.3 不写 e2e

QA 报告流程已稳定，本期只做单元 + 组件层，避免引入 Playwright 维护成本。

---

## 九、风险与回退

| 风险 | 触发 | 缓解 |
|------|------|------|
| LLM 不稳定，新字段格式不对 | structured_output 没拿到新字段 | Pydantic 默认值兜底，evaluator 仍写入 turn_evaluations |
| token 涨 30%（evaluator 跨轮） | 长 session | `MAX_TURNS=8` 截断；后续如成本敏感可降到 6 |
| followup_focus 漂移到 graph 状态外 | followup_node 没读到 | followup 走 prompt-only，未读到则按"无 focus"生成，行为退化到现状 |
| report_json 写入新字段后旧消费方报错 | Coach 页面读历史 report | 现 Coach 只用 `improvements / highlights / score`，新字段是追加；前端用 `?.` 兜底 |
| 前端 chips 视觉过载 | latent_signals 过多 | trace-node 渲染时截断至前 5 条 |

**回退**：所有改动都是非破坏性追加。如果出问题，可单独 revert prompt 改动或新字段写入，graph 仍正常工作。

---

## 十、明确不做的事

1. **跨 session 累积候选人画像** → 第 5 步 shared memory 层
2. **Reflexion 反思 / 自我修正** → 后续阶段
3. **LLM-as-Judge 系统级评估** → 第 6 步
4. **修改 DB schema / Alembic 迁移** → 不需要
5. **新增 graph 节点（如 candidate_modeling_node）** → 本期靠 evaluator 兼任，避免过度抽象
6. **修改 Coach 开场词逻辑** → 不动
7. **e2e Playwright 测试** → 不写
8. **新增前端面板（confidence panel / understanding panel）** → 本期只在 evaluator 节点追加渲染

---

## 十一、交付检查表

- [ ] `state.py` 字段扩展通过类型检查
- [ ] `_EvaluatorScoring / _InterviewMasterDecision` 新字段
- [ ] `evaluator_node` 写入 candidate_profile
- [ ] `followup_node` 消费 focus + signals
- [ ] `master_node` 输出 followup_focus
- [ ] SSE evaluator `node_done` payload 含新字段
- [ ] 前端 `TraceNodeData` 类型 + `trace-node.tsx` 渲染
- [ ] 后端 ruff / mypy / pytest 全过
- [ ] 前端 typecheck / test 全过
- [ ] 至少一条 QA 验证：对照本文 §1.2 的真实对话脚本，followup 不再机械追问模型参数
