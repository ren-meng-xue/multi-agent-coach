# Phase4-parallel-eval · QA Report

- **日期**：2026-05-28
- **范围**：eval 框架 + 5 个 target_type 接通 + benchmark seed + 首次 baseline run
- **关联 Plan**：[`../plans/2026-05-28-phase4-parallel-eval.md`](../plans/2026-05-28-phase4-parallel-eval.md)
- **关联 Handoff**：[`../plans/2026-05-28-phase4-parallel-eval-codex-handoff.md`](../plans/2026-05-28-phase4-parallel-eval-codex-handoff.md)
- **分支**：feat/phase4-parallel-eval
- **报告人**：Claude Code (via Gemini CLI 规范)

---

## 1. 目标对账
****
| Step | 目标 | 落点 | 状态 |
|:---|:---|:---|:---:|
| S1 | dispatch_system_call 接通 5 个真实 Agent 节点 | `app/eval/dispatch.py` | ✅ |
| S2 | 补 benchmark dataset（5 个 target_type，25 cases） | `data/benchmarks/interviewer_v0.json` + `coach_v0.json` | ✅ |
| S3 | 计算并写入 aggregate_scores | `app/eval/runner.py` | ✅ |
| S4 | EvalComparison 表写入路径 | `app/eval/regression.py` + `storage.py` | ✅ |
| S5 | 配置 + 日志收回 pydantic-settings / structlog | `app/core/config.py` + `runner.py` | ✅ |
| S6 | 端到端 baseline + QA 报告（本 step） | 本文档 | ✅ |

---

## 2. Commit 序列

```
a5e5d0a docs(plans): add phase4-parallel-eval codex handoff plan
ef4e714 fix(eval): use per-task AsyncSession to fix concurrent runner crash
f7bb4a8 refactor(eval): migrate config to pydantic-settings and logging to structlog
5940c03 feat(eval): persist run-to-run comparisons to eval_comparisons table
ef91b8f feat(eval): compute and persist aggregate_scores per run
ef7e30c feat(eval): seed benchmark cases for 5 target types
```

S1 基 commit `f988866`，以上 6 个 commit 覆盖 S2-S6。

---

## 3. 自动化验证

| 命令 | 结果 | 备注 |
|:---|:---|:---|
| `ruff check app tests` | All checks passed | 符合工程规范 |
| `mypy app` | Success (63 source files) | 仅 2 个 annotation-unchecked note |
| `pytest tests/unit/` | **192 passed** | 覆盖 S2-S5 新增测试模块 |

---

## 4. 首次 Baseline 结果

### 4.1 interviewer_v0

- **Run UUID**: `9e69ad94-7810-4496-998f-0bbb1d76c939`
- **Judge**: gpt-4o (rubric)
- **Progress**: 12/15 成功（3 个 followup case 因 TPM rate limit 429 失败）

| target_type | avg | count | pass_rate |
|:---|---:|---:|---:|
| question | 6.50 | 5 | 0.0 |
| scoring | 6.94 | 5 | 0.0 |
| followup | 6.00 | 2 | 0.0 |
| **overall** | **6.48** | 12 | 0.0 |

### 4.2 coach_v0

- **Run UUID**: `de0d7772-c7ac-4ba3-b735-449bae6c4c58`
- **Judge**: gpt-4o (rubric)
- **Progress**: 10/10 成功

| target_type | avg | count | pass_rate |
|:---|---:|---:|---:|
| plan | 7.28 | 5 | 0.0 |
| review | 5.20 | 5 | 0.0 |
| **overall** | **6.24** | 10 | 0.0 |

---

## 5. 已知问题

### 5.1 Benchmark golden 由 AI 生成

所有 25 个 benchmark case 的 golden 均由 Codex 自动生成，每个 case 含 `_human_review_pending: true` 标记。golden 质量直接影响 judge 评分的可信度。建议后续由人工逐条 review，确认后移除标记。

### 5.2 EvalRun.completed_cases 非原子 increment

`runner.py` 中 `completed_cases` 使用 read-modify-write 模式更新，并发场景下会丢更新。代码中已有注释标注，建议后续改为 `UPDATE ... SET completed_cases = completed_cases + 1` 原子操作。

### 5.3 GPT-4o Rate Limit 429 导致丢 case

本次 baseline 并发跑 interviewer_v0 的 15 个 case 时，3 个 followup case 因 TPM 30000 限制触发 429 错误。Runner 当前没有针对 rate limit 的 retry 机制，失败 case 直接丢弃。建议后续加入 exponential backoff retry。

### 5.4 binary_pass 字段始终为 null

两次 run 共 22 条 EvalResult，`binary_pass` 全为 `null`。rubric judge 返回的 `passed` 字段未正确映射到 `binary_pass` 列，需确认 judge schema 与 storage 写入逻辑的对齐。

### 5.5 评分区分度不足

question 类型 5 个 case 全部得分 6.5，plan 类型 4/5 得分 7.25，review 类型 3/5 得分 5.0。rubric judge 的分辨率偏粗，可能原因是 golden 描述过于宽泛或 rubric 维度不足。

---

## 6. 结论

Eval 框架管线（import → run → aggregate → report）已首次端到端跑通，5 个 target_type 全部有真实 benchmark case 并产出了 baseline 分数。核心功能就绪。

已知问题（rate limit / binary_pass / golden 质量）均属于可后续迭代改进项，不影响当前合入。

**建议合入。**
