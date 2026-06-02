# Phase4-parallel-eval · Codex Handoff Plan（Step S2-S6）

**目的**：把 eval 框架从「mock 已替换 / benchmark 仅 1 个 stub / 从未跑过真实评估」推进到「benchmark 真实 / aggregate 完整 / 跑过 baseline / QA 报告归档」的可合入状态。

**执行者**：Codex CLI（或其它 AI Agent）。用户只在 Step S6 之前出现一次（必须 ACK 才能真跑烧 token 的 baseline 评估）。

**总 plan 来源**：[`./2026-05-28-phase4-parallel-eval.md`](./2026-05-28-phase4-parallel-eval.md) §五。本文件只承担 Step S2-S6 的执行细节。

**当前进度**：
- ✅ S1 已完成（commit `f988866`，dispatch_system_call 已接通 5 个真实 Agent 节点）
- ⏳ S2-S6 待做

---

## 0. 全局规则（每一步都必须遵守）

工程规则全部来源于 [`CLAUDE.md`](../../../CLAUDE.md)。Codex 必须先读它，然后按下述硬约束执行：

| 编号 | 规则 | 违反后果 |
|------|------|----------|
| R1 | **TDD**：每步先写 failing test → 实现 → 重跑 test → 全绿 | 不允许"先写实现再写测试" |
| R2 | **不允许 `git add -A` 或 `git add .`** | 必须按精确文件名 add |
| R3 | **禁止** `git push` / `git merge` / `git rebase` | 这些动作由用户手动执行 |
| R4 | 每个 Step 独立 commit，message 用 conventional commits | 不许把多个 step 合到一个 commit |
| R5 | **每步落地前必须跑通三件套**：`ruff check` + `mypy app` + `pytest tests/unit/` | 任一项失败立即停下，向用户报告 |
| R6 | **禁止** `print()`；日志用 `structlog.get_logger(...)` | 见 CLAUDE.md 后端规范第 6-7 条 |
| R7 | **禁止** 直接读 `os.getenv()`；配置走 `app.core.config.get_settings()` | 见 CLAUDE.md 后端规范第 1 条 |
| R8 | **禁止** silently swallow exceptions；所有 try/except 必须 log + 抛或显式兜底 | 见 CLAUDE.md 后端规范第 10-12 条 |
| R9 | 任何验证失败时**停下并汇报**，不要硬 patch / 不要回避问题 / 不要绕过测试 | 安全栏 |
| R10 | 不要做与本 step **无关的重构** | 见 CLAUDE.md 开发流程第 5 条 |

**验证命令（每步实现完都跑）**：
```bash
cd backend && .venv/bin/python -m ruff check app tests
cd backend && .venv/bin/python -m mypy app
cd backend && .venv/bin/python -m pytest tests/unit/
```

**关于 integration test**：`tests/integration/` 依赖 docker postgres。本机 DB 端口可能配置错位（postgres 在 5433，backend 默认连 5432）。**Codex 跑 integration test 失败时不要尝试修复 DB 端口配置**，向用户汇报即可。所有 step 只要求 `pytest tests/unit/` 全过。

---

## Step S2 · 补 benchmark dataset

**目标**：每个 `target_type` 至少 5 个真实 case + golden，落到 `backend/data/benchmarks/*.json`。这是 eval 的"试卷"。

### S2.1 改动文件

- `backend/data/benchmarks/interviewer_v0.json` —— 重写（当前仅 1 个 stub），覆盖 3 类：
  - 5 个 `question` case（input：direction / weak_areas / star_stories / jd_context；golden：参考题目数组 + overall ≥ 7.0）
  - 5 个 `scoring` case（input：messages 历史片段 + target_role + 已有 turn_evaluations；golden：评分参考值）
  - 5 个 `followup` case（input：followup_focus / 最近一条 turn_evaluation / messages；golden：参考追问 + overall ≥ 7.0）
- `backend/data/benchmarks/coach_v0.json` —— 新建：
  - 5 个 `review` case（input：candidate_memory + last_session_report；golden：参考复盘要点 + overall ≥ 6.0）
  - 5 个 `plan` case（input：review_text + candidate_memory；golden：参考 plan_json 关键字段）

**golden 质量约定**：Codex 自动生成的 golden 必然没有真专家质量，但**格式必须严格合规**。每个 case 末尾必须有 `"_human_review_pending": true` 标记，表示"等人工 review 后再删除此标记"。

### S2.2 失败测试

新建 `backend/tests/unit/test_eval_benchmarks.py`：

```python
"""扫描 data/benchmarks/ 下所有 suite，验证 schema 完整性。"""
from pathlib import Path

import pytest

from app.eval.datasets import load_suite
from app.eval.dimensions import TargetType


BENCHMARKS_DIR = Path(__file__).parent.parent.parent / "data" / "benchmarks"


@pytest.mark.parametrize("benchmark_file", list(BENCHMARKS_DIR.glob("*.json")))
def test_benchmark_schema_valid(benchmark_file):
    suite = load_suite(str(benchmark_file))
    assert "name" in suite
    assert "judge_mode" in suite
    assert "cases" in suite
    assert isinstance(suite["cases"], list)
    assert len(suite["cases"]) >= 5, f"{benchmark_file.name} 至少 5 个 case"

    seen_target_types = set()
    for c in suite["cases"]:
        assert "id" in c
        assert "target_type" in c
        # target_type 必须是 TargetType 枚举之一
        assert c["target_type"] in {t.value for t in TargetType}
        assert "input_json" in c
        seen_target_types.add(c["target_type"])

    # 每个 suite 至少覆盖 1 个 target_type
    assert len(seen_target_types) >= 1


def test_all_target_types_have_at_least_one_case():
    """整套 benchmark 必须覆盖全部 5 个 target_type。"""
    all_target_types = set()
    for f in BENCHMARKS_DIR.glob("*.json"):
        suite = load_suite(str(f))
        for c in suite["cases"]:
            all_target_types.add(c["target_type"])
    expected = {t.value for t in TargetType}
    missing = expected - all_target_types
    assert not missing, f"以下 target_type 没有 benchmark case: {missing}"
```

### S2.3 验证

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_eval_benchmarks.py -v
cd backend && .venv/bin/python -m ruff check app tests
cd backend && .venv/bin/python -m mypy app
cd backend && .venv/bin/python -m pytest tests/unit/
```

### S2.4 Commit

`feat(eval): seed benchmark cases for 5 target types`

精确 add：
```bash
git add backend/data/benchmarks/interviewer_v0.json
git add backend/data/benchmarks/coach_v0.json
git add backend/tests/unit/test_eval_benchmarks.py
```

---

## Step S3 · 计算并写入 aggregate_scores

**目标**：`EvalRunner.run` 完成后聚合本次 run 所有 `EvalResult.overall_score` 并写入 `EvalRun.aggregate_scores`，让 trend 曲线不再永远为 0。

### S3.1 改动文件

- `backend/app/eval/runner.py`
  - `_run_one` 不变
  - `run()` 在所有 task gather 完之后、`update_run(status="completed", ...)` 之前，新增 aggregate 计算：
    - 拉本次 run 全部 results
    - 按 target_type 分组 → `{target_type: {avg, pass_rate, count}}`
    - 计算总体 overall（所有 target_type avg 的平均）
    - 拼成 `aggregate_scores = {"overall": float, "by_target_type": {...}}`
    - `await self.storage.update_run(run_id, aggregate_scores=aggregate_scores, status="completed", ...)`

### S3.2 失败测试

新建 `backend/tests/unit/test_eval_runner_aggregate.py`：

```python
"""验证 EvalRunner 跑完后会写入 aggregate_scores。"""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.eval.dimensions import TargetType
from app.eval.runner import EvalRunner


@pytest.mark.asyncio
async def test_runner_writes_aggregate_scores_after_completion():
    storage = MagicMock()
    storage.update_run = AsyncMock()
    storage.save_result = AsyncMock()
    storage.get_run = AsyncMock(return_value=MagicMock(completed_cases=0))
    storage.get_results = AsyncMock(return_value=[
        MagicMock(target_type="question", overall_score=8.0, binary_pass=True),
        MagicMock(target_type="question", overall_score=6.0, binary_pass=False),
        MagicMock(target_type="scoring", overall_score=7.0, binary_pass=True),
    ])

    judge = MagicMock()
    judge.judge = AsyncMock(return_value=MagicMock(
        model_dump=lambda: {"overall": 7.0},
        reasoning="r",
        overall=7.0,
        passed=True,
    ))

    async def fake_system_call(tt, inp):
        return {"answer": "x"}

    runner = EvalRunner(storage, judge, fake_system_call)
    cases = [
        MagicMock(id=uuid4(), case_key="q1", target_type="question", input_json={}, golden_json=None),
    ]
    run_id = uuid4()
    await runner.run(run_id, cases)

    # 最后一次 update_run 应该带 aggregate_scores
    final_call = storage.update_run.call_args_list[-1]
    kwargs = final_call.kwargs
    assert "aggregate_scores" in kwargs
    agg = kwargs["aggregate_scores"]
    assert "overall" in agg
    assert "by_target_type" in agg
    # 验证按 target_type 分组算了 avg
    assert agg["by_target_type"]["question"]["avg"] == pytest.approx(7.0)
    assert agg["by_target_type"]["question"]["count"] == 2
    assert agg["by_target_type"]["scoring"]["avg"] == pytest.approx(7.0)
```

### S3.3 验证

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_eval_runner_aggregate.py -v
# + ruff + mypy + pytest tests/unit/
```

### S3.4 Commit

`feat(eval): compute and persist aggregate_scores per run`

精确 add：
```bash
git add backend/app/eval/runner.py
git add backend/tests/unit/test_eval_runner_aggregate.py
```

---

## Step S4 · EvalComparison 表写入路径

**目标**：`RegressionTester.compare_runs` 把每个 target_type 维度的对比结果落 `eval_comparisons` 表。

### S4.1 改动文件

- `backend/app/eval/regression.py`
  - `compare_runs` 末尾追加：对每个 target_type 维度生成 1 行 `EvalComparison` 并 add → commit
  - 字段：`run_a_id`, `run_b_id`, `suite_name`（取 run_a.suite.name），`metric`（target_type），`score_a` / `score_b`（该 target_type 的 avg），`delta = score_b - score_a`，`winner ∈ {"a", "b", "tie"}`（按 |delta| > 0.5 判定显著），`significant = |delta| > 0.5`
- `backend/app/eval/storage.py`
  - 新增 `save_comparison(comparison_data: dict) -> EvalComparison`

### S4.2 失败测试

新建 `backend/tests/unit/test_eval_regression.py`：

```python
"""验证 RegressionTester.compare_runs 写入 EvalComparison 表。"""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.eval.regression import RegressionTester


@pytest.mark.asyncio
async def test_compare_runs_writes_eval_comparison_rows():
    storage = MagicMock()
    # 两次 run 的 results，分布在不同 target_type
    storage.get_results = AsyncMock(side_effect=[
        # run A
        [MagicMock(case_key="q1", target_type="question", overall_score=6.0),
         MagicMock(case_key="s1", target_type="scoring", overall_score=7.0)],
        # run B
        [MagicMock(case_key="q1", target_type="question", overall_score=8.0),
         MagicMock(case_key="s1", target_type="scoring", overall_score=7.2)],
    ])
    storage.get_run = AsyncMock(return_value=MagicMock(suite=MagicMock(name="interviewer_v0")))
    storage.save_comparison = AsyncMock()

    tester = RegressionTester(storage)
    out = await tester.compare_runs(uuid4(), uuid4())

    # 1) 函数返回保留原有 improved/degraded/stable 三桶
    assert "improved" in out
    assert "degraded" in out
    assert "stable" in out

    # 2) 必须 save_comparison 被调用，且至少含 question 一行 significant
    assert storage.save_comparison.await_count >= 1
    called_args_list = [c.args[0] for c in storage.save_comparison.call_args_list]
    metrics = [c.get("metric") for c in called_args_list]
    assert "question" in metrics
    # question: 6.0 → 8.0, delta=2.0, |delta|>0.5 → significant + winner='b'
    q_row = next(c for c in called_args_list if c["metric"] == "question")
    assert q_row["winner"] == "b"
    assert q_row["significant"] is True
    assert q_row["delta"] == pytest.approx(2.0)
```

### S4.3 验证

`pytest tests/unit/test_eval_regression.py -v` + 三件套

### S4.4 Commit

`feat(eval): persist run-to-run comparisons to eval_comparisons table`

精确 add：
```bash
git add backend/app/eval/regression.py
git add backend/app/eval/storage.py
git add backend/tests/unit/test_eval_regression.py
```

---

## Step S5 · 配置 + 日志收回 pydantic-settings / structlog

**目标**：消除 commit 1 引入的 `os.getenv` + `print` 违规，符合 CLAUDE.md 后端规范。

### S5.1 改动文件

- `backend/app/core/config.py`
  - 新增字段：
    ```python
    run_llm_eval_secret: SecretStr | None = None  # 触发 eval 用的 secret
    app_env: Literal["dev", "prod"] = "dev"
    ```
- `backend/app/api/v1/eval.py`
  - `verify_eval_auth` 改用 `get_settings()`，删除 `os.getenv`
- `backend/app/eval/runner.py`
  - 第 58 行 `print(f"Error running case {case.case_key}: {e}")` 改为：
    ```python
    log = get_logger("app.eval.runner")
    log.error("eval_case_failed", case_key=case.case_key, error=str(e))
    ```
  - 顶部 import `from app.core.logging import get_logger`

### S5.2 失败测试

修改 `backend/tests/integration/test_eval_api.py` 已有的 `verify_eval_auth` 相关 test，改用 settings monkeypatch（如果 test 之前用 `os.environ`）。

新增 `backend/tests/unit/test_eval_runner_logging.py`：

```python
"""验证 EvalRunner 失败 case 用 structlog 而非 print。"""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.eval.runner import EvalRunner


@pytest.mark.asyncio
async def test_runner_logs_via_structlog_on_case_failure(capsys):
    storage = MagicMock()
    storage.update_run = AsyncMock()
    storage.save_result = AsyncMock()
    storage.get_run = AsyncMock(return_value=MagicMock(completed_cases=0))
    storage.get_results = AsyncMock(return_value=[])

    judge = MagicMock()

    async def broken_system_call(tt, inp):
        raise RuntimeError("simulated crash")

    runner = EvalRunner(storage, judge, broken_system_call)
    cases = [
        MagicMock(id=uuid4(), case_key="c1", target_type="question",
                  input_json={}, golden_json=None),
    ]
    with patch("app.eval.runner.log") as mock_log:
        await runner.run(uuid4(), cases)
        assert mock_log.error.called or mock_log.warning.called

    captured = capsys.readouterr()
    # 不允许 print 输出到 stdout
    assert "Error running case" not in captured.out
```

### S5.3 验证

三件套全过 + `grep -rn "print(" backend/app/eval/` 应为空（除 cli.py 用户输出）。

### S5.4 Commit

`refactor(eval): migrate config to pydantic-settings and logging to structlog`

精确 add：
```bash
git add backend/app/core/config.py
git add backend/app/api/v1/eval.py
git add backend/app/eval/runner.py
git add backend/tests/unit/test_eval_runner_logging.py
# 如有改 integration test:
git add backend/tests/integration/test_eval_api.py
```

---

## Step S6 · 端到端跑一次真实评估 + 落 QA 报告

**⚠️ 这一步会真烧 OpenAI token，Codex 必须先停下让用户 ACK 才能跑。**

### S6.1 用户 ACK 协议

Codex 完成 S2-S5 之后，**不要自动跑 S6**。改为输出以下消息并停下等待：

```
S2-S5 已完成。S6 需要真实 OpenAI API key 跑 baseline 评估，
预计烧 ~50-100 次 GPT-4o 调用，成本 < $5。
请用户：
1. 确认 backend/.env 已配 OPENAI_API_KEY
2. 启动 docker postgres（如果端口和 backend 配置不一致请先对齐）
3. 跑 alembic upgrade head 确保 eval 表存在
4. 回复 'go-s6' 触发我执行 S6.2-S6.4
```

### S6.2 用户 ACK 后执行

用户回复 `go-s6` 后，Codex 顺序执行：

```bash
# 1. 导入 benchmark 数据
cd backend && .venv/bin/python -m app.eval.cli import-suite --file data/benchmarks/interviewer_v0.json
cd backend && .venv/bin/python -m app.eval.cli import-suite --file data/benchmarks/coach_v0.json

# 2. 跑 baseline（先 --limit 1 冒烟验证管线 work）
cd backend && APP_ENV=dev .venv/bin/python -m app.eval.cli run \
  --suite interviewer_v0 \
  --judge-mode rubric \
  --judge-model gpt-4o \
  --limit 1 \
  --system-version baseline_$(git rev-parse --short HEAD)

# 验证：DB 中应有一条 EvalRun，status='completed'，aggregate_scores 非空

# 3. 跑完整 baseline
cd backend && APP_ENV=dev .venv/bin/python -m app.eval.cli run \
  --suite interviewer_v0 \
  --judge-mode rubric \
  --judge-model gpt-4o \
  --system-version baseline_$(git rev-parse --short HEAD)

cd backend && APP_ENV=dev .venv/bin/python -m app.eval.cli run \
  --suite coach_v0 \
  --judge-mode rubric \
  --judge-model gpt-4o \
  --system-version baseline_$(git rev-parse --short HEAD)

# 4. 生成 markdown 报告
cd backend && .venv/bin/python -m app.eval.cli report --run-id <interviewer_run_id> --format markdown > /tmp/interviewer_baseline.md
cd backend && .venv/bin/python -m app.eval.cli report --run-id <coach_run_id> --format markdown > /tmp/coach_baseline.md
```

### S6.3 落 QA 报告

新建 `docs/superpowers/qa-reports/phase4-parallel-eval-qa-report.md`，模板参考 `phase5-qa-report.md`：

```markdown
# Phase4-parallel-eval · QA Report

- **日期**：<填执行日期>
- **范围**：eval 框架 + 5 个 target_type 接通 + benchmark seed + 首次 baseline run
- **关联 Plan**：[`../plans/2026-05-28-phase4-parallel-eval.md`](../plans/2026-05-28-phase4-parallel-eval.md)
- **关联 Handoff**：[`../plans/2026-05-28-phase4-parallel-eval-codex-handoff.md`](../plans/2026-05-28-phase4-parallel-eval-codex-handoff.md)
- **分支**：feat/phase4-parallel-eval
- **报告人**：Codex CLI

## 1. 目标对账
（列 plan §五 各 step 实际状态，对应 S1-S6）

## 2. Commit 序列
（git log --oneline，列本期所有 commit）

## 3. 自动化验证
（ruff / mypy / pytest 三件套结果）

## 4. 首次 Baseline 结果
（贴 interviewer_v0 + coach_v0 的 markdown 报告片段）

## 5. 已知问题
- benchmark 的 golden 由 Codex 自动生成，所有 case 含 `_human_review_pending: true`
  标记。建议后续由人工 review 提升质量。
- ...

## 6. 结论
**建议合入 / 不建议合入** + 理由
```

### S6.4 Commit

`docs: add phase 4-parallel-eval qa report with first baseline run`

精确 add：
```bash
git add docs/superpowers/qa-reports/phase4-parallel-eval-qa-report.md
```

---

## 完成后的状态

完成 S2-S6 后，分支状态：

```
当前分支 feat/phase4-parallel-eval：
  S1 commit f988866  (wire eval system_calls to real agent nodes)
  S2 commit          (seed benchmark cases for 5 target types)
  S3 commit          (compute and persist aggregate_scores per run)
  S4 commit          (persist run-to-run comparisons to eval_comparisons table)
  S5 commit          (migrate config to pydantic-settings and logging to structlog)
  S6 commit          (add phase 4-parallel-eval qa report with first baseline run)
```

**这时候用户可以做的事**（Codex 不要做）：
1. Review benchmark golden 质量，移除 `_human_review_pending` 标记
2. 决定要不要把 `feat/phase4-parallel-eval` 合入 main
3. 决定是否补 frontend UI 展示评估结果（Step S7，已在总 plan 中标记为"跳过本期"）

---

## Codex 行为兜底（防意外）

1. **不要修 docker / 端口 / .env / OS-level 配置**。这些是用户机器的事。
2. **不要 force push / rebase / merge**。任何会改写 git 历史的动作必须由用户做。
3. **不要跑 frontend 命令**。本期所有工作都在 backend。
4. **任何一步失败超过 1 次重试仍失败，立即停下汇报**。不要把测试用 `pytest.mark.skip` 跳过、不要把失败的 assert 删掉。
5. **不允许越过本 plan 范围**做任何额外工作（即使你觉得"顺手就做了更好"）。如果发现额外问题，记在 QA 报告 §5 即可。

---

## 给用户的执行指引

把这份 plan 喂给 codex 的方式（例）：

```bash
# 在项目根目录
codex exec \
  --prompts "读 docs/superpowers/plans/2026-05-28-phase4-parallel-eval-codex-handoff.md 并完整执行 Step S2 到 S5。S6 之前必须停下等我 ACK。严格遵守 plan 中的 R1-R10 全局规则。" \
  --sandbox workspace-write
```

S5 完成后 codex 会停下，你确认环境（OPENAI_API_KEY / docker postgres / alembic）就绪后回复 `go-s6` 让它继续。
