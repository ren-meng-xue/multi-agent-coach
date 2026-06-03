# Interview Three Gaps Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复面试系统三大机制断层：Supervisor矛盾推理、Chief调度机械化、Evaluator重复盲区。

**Architecture:** 在 `_EvaluatorScoring` schema 新增两个语义信号（`is_repeated_answer` / `followup_would_help`），让 Chief 的追问/换题决策由 LLM 语义驱动而非硬编码阈值驱动。同时修复 Supervisor prompt 的推理文字与 DECISION JSON 矛盾。

**Tech Stack:** Python 3.12, Pydantic, LangChain, LangGraph, Pytest, Ruff

---

## File Map

| 文件                                              | 改动类型 | 说明                                                             |
| ------------------------------------------------- | -------- | ---------------------------------------------------------------- |
| `backend/app/agents/prepare/prompts.py`           | Modify   | Fix 1: Supervisor 无JD路径推理对齐                               |
| `backend/app/agents/interviewer/prompts.py`       | Modify   | Fix 2+3: EVALUATOR_SCORING_PROMPT 新增两字段说明                 |
| `backend/app/agents/interviewer/nodes.py`         | Modify   | Fix 2+3: `_EvaluatorScoring` 新增字段；`evaluator_node` 传播字段 |
| `backend/app/agents/interviewer/state.py`         | Modify   | Fix 3: `TurnEvaluation` TypedDict 新增字段                       |
| `backend/app/agents/interviewer/chief.py`         | Modify   | Fix 2+3: `_answer_is_sufficient` 使用新信号                      |
| `backend/app/agents/evaluator/nodes.py`           | Modify   | Fix 3: `_turn_evaluation_from_scoring` 传播新字段                |
| `backend/app/services/interview_turn.py`          | Modify   | Fix 2: `max_followups` 默认值 2→3                                |
| `backend/tests/unit/test_interview_three_gaps.py` | Create   | 所有新字段 + 决策逻辑的单元测试                                  |

---

## Task 1: Fix 1 — Supervisor prompt 推理/决策对齐

**Files:**

- Modify: `backend/app/agents/prepare/prompts.py:4-27`

**背景：** `SUPERVISOR_COMBINED_PROMPT` 的调用规则里，规则3是"若用户有JD才运行jd_analysis"，无JD直接跳规则4→question_gen。但LLM推理倾向于输出"建议用户提供JD"，与实际 DECISION 矛盾，面板里推理文字与行为不一致。

- [ ] **Step 1: 修改 SUPERVISOR_COMBINED_PROMPT，在规则4后补充无JD说明**

将 `backend/app/agents/prepare/prompts.py` 中的 `SUPERVISOR_COMBINED_PROMPT` 改为：

```python
SUPERVISOR_COMBINED_PROMPT = """你是面试准备 Supervisor，负责调度各子 Agent。

【岗位方向准则】
- 优先且完整保留用户提供的「目标岗位/方向」关键词。
- 严禁将具体岗位（如 AI Agent 工程师）简化为通用名称（如 软件工程师）。

当前状态快照：
{state_summary}

已完成工具：{completed_tools}

调用规则（按优先级）：
1. 若用户完全没有提供岗位方向信息 → next = "need_direction"
2. 若有用户背景且 memory_search 未完成 → next = "memory_search"
3. 若用户有 JD 且 jd_analysis 未完成 → next = "jd_analysis"
4. 若 question_gen 未完成 → next = "question_gen"
   （注意：若无JD则跳过jd_analysis直接到这一步，推理中不要建议用户提供JD，
   因为系统无法暂停等待——在 reasoning 中注明"无JD，将基于岗位方向生成通用题"即可）
5. 若 question_gen 已完成 → next = "END"

每个工具只能调用一次。

输出格式（两部分，中间不要分隔线）：
第一部分：用「中文」逐行推理（每行以"• "开头，每行不超过40字，2-3行即可）。
第二部分：最后单独一行，严格按以下格式输出 JSON 决策（不要换行，不要多余内容）：
DECISION: {{"next": "...", "direction": "...", "reasoning": "..."}}"""
```

- [ ] **Step 2: 验证 prompt 格式正确（无语法错误）**

```bash
cd backend && uv run python -c "from app.agents.prepare.prompts import SUPERVISOR_COMBINED_PROMPT; print('OK', len(SUPERVISOR_COMBINED_PROMPT))"
```

Expected: `OK <number>` 无报错

- [ ] **Step 3: 运行已有 prepare 相关测试，确认无回归**

```bash
cd backend && uv run pytest tests/unit/test_prepare_nodes.py tests/unit/test_prepare_graph.py -v 2>&1 | tail -20
```

Expected: 所有已有测试 PASS

- [ ] **Step 4: Commit**

```bash
cd backend && git add app/agents/prepare/prompts.py
git commit -m "fix(prepare): align supervisor prompt — no-JD path no longer suggests providing JD"
```

---

## Task 2: Fix 2+3 — 更新 `_EvaluatorScoring` schema 新增两信号字段

**Files:**

- Modify: `backend/app/agents/interviewer/nodes.py:300-310`（`_EvaluatorScoring`）
- Modify: `backend/app/agents/interviewer/state.py:12-26`（`TurnEvaluation`）

**背景：**

- `followup_would_help: bool` — LLM 评估继续追问是否有价值（False 时即使分数 < 7.0 也切题）
- `is_repeated_answer: bool` — 本轮回答与上一轮有高度重叠（True 时立即切题，不追问）

- [ ] **Step 1: 先写失败测试**

创建 `backend/tests/unit/test_interview_three_gaps.py`：

```python
"""Unit tests for interview three-gaps fixes."""
from __future__ import annotations

from app.agents.interviewer.nodes import _EvaluatorScoring
from app.agents.interviewer.chief import _answer_is_sufficient


class TestEvaluatorScoringNewFields:
    def test_default_followup_would_help_is_true(self):
        s = _EvaluatorScoring()
        assert s.followup_would_help is True

    def test_default_is_repeated_answer_is_false(self):
        s = _EvaluatorScoring()
        assert s.is_repeated_answer is False

    def test_followup_would_help_can_be_set_false(self):
        s = _EvaluatorScoring(followup_would_help=False)
        assert s.followup_would_help is False

    def test_is_repeated_answer_can_be_set_true(self):
        s = _EvaluatorScoring(is_repeated_answer=True)
        assert s.is_repeated_answer is True


class TestAnswerIsSufficient:
    def _make_report(self, score=5.0, missing=None, repeated=False, followup_help=True):
        scoring = {
            "summary_score": score,
            "missing_dimensions": missing or [],
            "is_repeated_answer": repeated,
            "followup_would_help": followup_help,
        }
        return {"scoring": scoring}

    def test_high_score_no_missing_is_sufficient(self):
        assert _answer_is_sufficient(self._make_report(score=7.5)) is True

    def test_high_score_with_missing_not_sufficient(self):
        assert _answer_is_sufficient(self._make_report(score=7.5, missing=["量化指标"])) is False

    def test_low_score_not_sufficient_by_default(self):
        assert _answer_is_sufficient(self._make_report(score=5.5)) is False

    def test_repeated_answer_is_sufficient_regardless_of_score(self):
        # is_repeated_answer=True → 立即切题，不管分数
        assert _answer_is_sufficient(self._make_report(score=4.0, repeated=True)) is True

    def test_followup_would_not_help_is_sufficient(self):
        # followup_would_help=False → 继续追问没价值，切题
        assert _answer_is_sufficient(self._make_report(score=5.0, followup_help=False)) is True

    def test_followup_would_help_true_and_low_score_not_sufficient(self):
        assert _answer_is_sufficient(self._make_report(score=5.0, followup_help=True)) is False
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && uv run pytest tests/unit/test_interview_three_gaps.py -v 2>&1 | tail -20
```

Expected: FAIL（`_EvaluatorScoring` 缺少新字段，`_answer_is_sufficient` 逻辑未更新）

- [ ] **Step 3: 更新 `_EvaluatorScoring`（nodes.py）**

在 `backend/app/agents/interviewer/nodes.py` 中，找到 `class _EvaluatorScoring(BaseModel):` 块（约第300-310行），将其改为：

```python
class _EvaluatorScoring(BaseModel):
    bullets: list[str] = []
    technical_depth: float = 5.0
    quantified_results: float = 5.0
    failure_tradeoffs: float = 5.0
    structure: float = 5.0
    summary_score: float = 5.0
    candidate_level: Literal["beginner", "junior", "mid", "senior"] = "junior"
    latent_signals: list[str] = []
    missing_dimensions: list[str] = []
    # Fix 2: 追问价值信号——False 时即使分数 < 7.0 也应切题
    followup_would_help: bool = True
    # Fix 3: 重复回答检测——True 时立即切题，不再追问
    is_repeated_answer: bool = False
```

- [ ] **Step 4: 更新 `TurnEvaluation` TypedDict（state.py）**

在 `backend/app/agents/interviewer/state.py` 的 `TurnEvaluation` 中，在 `missing_dimensions` 后添加：

```python
class TurnEvaluation(TypedDict, total=False):
    """单轮答题的评估结果，由 evaluator_node 写入。"""

    question_index: int
    followup_index: int
    bullets: list[str]
    technical_depth: float
    quantified_results: float
    failure_tradeoffs: float
    structure: float
    summary_score: float
    candidate_level: CandidateLevel
    latent_signals: list[str]
    missing_dimensions: list[str]
    # Fix 2+3：新增语义信号字段
    followup_would_help: bool
    is_repeated_answer: bool
```

- [ ] **Step 5: 运行测试（只有 schema 测试通过，chief 测试还不通过）**

```bash
cd backend && uv run pytest tests/unit/test_interview_three_gaps.py::TestEvaluatorScoringNewFields -v 2>&1 | tail -20
```

Expected: 4 PASS

---

## Task 3: Fix 2+3 — 更新 `_answer_is_sufficient` 使用新信号

**Files:**

- Modify: `backend/app/agents/interviewer/chief.py:101-102`（`_answer_is_sufficient`）

- [ ] **Step 1: 更新 `_answer_is_sufficient`（chief.py）**

在 `backend/app/agents/interviewer/chief.py` 中，找到 `_answer_is_sufficient` 函数（约第101-102行），将其改为：

```python
def _answer_is_sufficient(report: dict[str, Any] | None) -> bool:
    scoring = (report or {}).get("scoring") or {}
    # Fix 3: 重复回答 → 立即切题（继续追问无意义）
    if scoring.get("is_repeated_answer"):
        return True
    # Fix 2: LLM 明确判断继续追问无价值 → 切题
    if not scoring.get("followup_would_help", True):
        return True
    # 原有逻辑：分数足够且无缺失维度
    return _score(report) >= 7.0 and not _missing_dimensions(report)
```

- [ ] **Step 2: 运行全部 chief 相关测试**

```bash
cd backend && uv run pytest tests/unit/test_interview_three_gaps.py -v 2>&1 | tail -20
```

Expected: 全部 10 个测试 PASS

- [ ] **Step 3: Commit（Task 2+3 schema 与决策逻辑）**

```bash
cd backend
git add app/agents/interviewer/nodes.py \
        app/agents/interviewer/state.py \
        app/agents/interviewer/chief.py \
        tests/unit/test_interview_three_gaps.py
git commit -m "fix(interviewer): add is_repeated_answer + followup_would_help signals to EvaluatorScoring and chief decision logic"
```

---

## Task 4: Fix 2+3 — 更新 Evaluator prompt，让 LLM 输出新字段

**Files:**

- Modify: `backend/app/agents/interviewer/prompts.py:97-112`（`EVALUATOR_SCORING_PROMPT`）

- [ ] **Step 1: 更新 EVALUATOR_SCORING_PROMPT**

在 `backend/app/agents/interviewer/prompts.py` 中，将 `EVALUATOR_SCORING_PROMPT` 改为：

```python
EVALUATOR_SCORING_PROMPT = (
    "你是 AI 面试委员会的评估官。请对候选人本轮回答进行深度评估并打分。\n\n"
    "【打分维度】（各 0-10 分）：\n"
    "- technical_depth：技术深度\n"
    "- quantified_results：是否给出量化指标（数据、QPS、延迟等）\n"
    "- failure_tradeoffs：是否考虑到失败、降级或方案权衡\n"
    "- structure：表达是否条理清晰、逻辑严密\n"
    "summary_score = 以上 4 维度均值，保留一位小数。\n\n"
    "【画像识别】：\n"
    "- candidate_level：根据表现判定级别（beginner/junior/mid/senior）\n"
    "- latent_signals：识别出的具体工程能力或行为信号（如：workflow_orchestration, cloud_native_mindset, rigorous_testing 等）\n"
    "- missing_dimensions：**【核心】识别候选人回答中明显缺失、以后需要加强的知识点或能力项**（如：缺少高可用设计、未考虑边界条件、缺乏成本意识等）。这些将作为其后续的练习重点。\n\n"
    "【追问价值判断】：\n"
    "- followup_would_help（布尔）：本题是否还有追问价值。"
    "若候选人已明确表示不了解、回答内容已充分穷尽、或分数虽低但追问只会重复空转 → 设为 false；"
    "否则设为 true（默认值）。\n"
    "- is_repeated_answer（布尔）：本轮回答是否与上一轮回答有高度文字重叠（≥70% 内容相同）。"
    "若是 → 设为 true，代表候选人在回避追问、输出车轱辘话；否则设为 false（默认值）。\n\n"
    "【文字要求】：\n"
    "bullets 字段填入刚才推理输出的 2-3 条要点摘要（去掉行首 · 符号）。\n\n"
    "【上下文】：\n{context}"
)
```

- [ ] **Step 2: 验证 prompt 可导入**

```bash
cd backend && uv run python -c "from app.agents.interviewer.prompts import EVALUATOR_SCORING_PROMPT; print('OK')"
```

Expected: `OK`

---

## Task 5: Fix 3 — 在 evaluator/nodes.py 中传播新字段

**Files:**

- Modify: `backend/app/agents/evaluator/nodes.py:24-42`（`_turn_evaluation_from_scoring`）

**背景：** `evaluator/nodes.py` 的 `_turn_evaluation_from_scoring` 把 `_EvaluatorScoring` 对象转为 `TurnEvaluation` dict。新字段需要在此传播，否则 Chief 看到的 `scoring` dict 里没有新字段。

- [ ] **Step 1: 更新 `_turn_evaluation_from_scoring`**

在 `backend/app/agents/evaluator/nodes.py` 中，将 `_turn_evaluation_from_scoring` 函数改为：

```python
def _turn_evaluation_from_scoring(
    scoring: _EvaluatorScoring,
    *,
    question_index: int,
    followup_index: int,
) -> TurnEvaluation:
    return {
        "question_index": question_index,
        "followup_index": followup_index,
        "bullets": list(scoring.bullets),
        "technical_depth": scoring.technical_depth,
        "quantified_results": scoring.quantified_results,
        "failure_tradeoffs": scoring.failure_tradeoffs,
        "structure": scoring.structure,
        "summary_score": scoring.summary_score,
        "candidate_level": scoring.candidate_level,
        "latent_signals": list(scoring.latent_signals),
        "missing_dimensions": list(scoring.missing_dimensions),
        # Fix 2+3: 传播新语义信号字段
        "followup_would_help": scoring.followup_would_help,
        "is_repeated_answer": scoring.is_repeated_answer,
    }
```

- [ ] **Step 2: 同步更新 interviewer/nodes.py 中的 evaluator_node**

在 `backend/app/agents/interviewer/nodes.py` 的 `evaluator_node` 函数（约第353-425行）中，找到构造 `entry: TurnEvaluation` 的字典，在 `"missing_dimensions"` 后添加两个新字段：

```python
    entry: TurnEvaluation = {
        "question_index": state.get("current_question_index", state.get("question_count", 0)),
        "followup_index": state.get("followup_count", 0),
        "bullets": list(scoring.bullets),
        "technical_depth": scoring.technical_depth,
        "quantified_results": scoring.quantified_results,
        "failure_tradeoffs": scoring.failure_tradeoffs,
        "structure": scoring.structure,
        "summary_score": scoring.summary_score,
        "candidate_level": scoring.candidate_level,
        "latent_signals": list(scoring.latent_signals),
        "missing_dimensions": list(scoring.missing_dimensions),
        # Fix 2+3: 传播新语义信号字段
        "followup_would_help": scoring.followup_would_help,
        "is_repeated_answer": scoring.is_repeated_answer,
    }
```

- [ ] **Step 3: 运行 ruff 确认无 lint 错误**

```bash
cd backend && uv run ruff check app/agents/evaluator/nodes.py app/agents/interviewer/nodes.py
```

Expected: 无输出（无错误）

- [ ] **Step 4: Commit**

```bash
cd backend
git add app/agents/evaluator/nodes.py \
        app/agents/interviewer/nodes.py \
        app/agents/interviewer/prompts.py
git commit -m "fix(evaluator): propagate followup_would_help and is_repeated_answer through evaluation chain"
```

---

## Task 6: Fix 2 — max_followups 默认值 2→3

**Files:**

- Modify: `backend/app/services/interview_turn.py:164`

**背景：** 在新语义信号驱动下，Chief 会在"话题穷尽"或"重复作答"时提前切题，因此把硬上限从 2 提高到 3 可以给 LLM 更多空间、减少过早触发硬限制的情况。

- [ ] **Step 1: 修改 `_build_state` 中的 max_followups**

在 `backend/app/services/interview_turn.py` 中，找到 `_build_state` 函数（约第145-165行），将 `"max_followups": 2` 改为：

```python
    return {
        "session_id": str(session.id),
        "user_id": user_id,
        "is_first_time": is_first_time,
        "target_role": session.target_role or "",
        "target_company": session.target_company or "",
        "user_background": session.user_background or "",
        "messages": messages,
        "stage": cast(Any, session.stage),
        "question_count": session.question_count,
        "total_questions": session.total_questions,
        "followup_count": session.followup_count,
        "max_followups": 3,  # 提升到3，配合语义信号让LLM有更多空间决策，而非过早触发硬限制
    }
```

- [ ] **Step 2: 验证无 lint 错误**

```bash
cd backend && uv run ruff check app/services/interview_turn.py
```

Expected: 无输出

- [ ] **Step 3: Commit**

```bash
cd backend
git add app/services/interview_turn.py
git commit -m "fix(interview): increase max_followups default 2→3 to give semantic signals more room to operate"
```

---

## Task 7: 全量测试验证

**Files:**

- Run tests only（无代码修改）

- [ ] **Step 1: 运行全部单元测试**

```bash
cd backend && uv run pytest tests/unit/ -v 2>&1 | tail -30
```

Expected: 所有测试 PASS，包括新增的 10 个 `test_interview_three_gaps` 测试

- [ ] **Step 2: 运行 mypy 类型检查**

```bash
cd backend && uv run mypy app/agents/interviewer/ app/agents/evaluator/ app/agents/prepare/ app/services/interview_turn.py 2>&1 | tail -20
```

Expected: `Success: no issues found` 或仅有已知 ignore 的警告

- [ ] **Step 3: 运行 ruff 全量 lint**

```bash
cd backend && uv run ruff check app/ 2>&1 | head -20
```

Expected: 无输出（或仅有已知警告）

- [ ] **Step 4: 最终 commit（如有遗漏文件）**

```bash
cd backend && git status
# 若有未提交文件：
git add <files> && git commit -m "fix(interview): finalize three-gaps fix — all tests pass"
```

---

## 验收检查清单

- [ ] Supervisor 面板推理文字：无JD时不出现"建议提供JD"措辞
- [ ] `_EvaluatorScoring` 包含 `followup_would_help` 和 `is_repeated_answer` 字段
- [ ] `TurnEvaluation` TypedDict 包含两个新字段
- [ ] `_answer_is_sufficient` 在 `is_repeated_answer=True` 时返回 True
- [ ] `_answer_is_sufficient` 在 `followup_would_help=False` 时返回 True
- [ ] `evaluator/nodes.py` 和 `interviewer/nodes.py` 均传播新字段
- [ ] `max_followups` 默认值为 3
- [ ] 全部单元测试通过
- [ ] ruff + mypy 无新增错误
