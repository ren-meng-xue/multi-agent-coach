# Agentic vs State Machine Interviewer

- 日期：2026-06-02
- Baseline：旧 `master -> chain -> node` state machine
- Experiment：`Chief Interviewer -> Evaluator Agent / Question Designer Agent`

## 实验设计

使用 `backend/data/benchmarks/interviewer_quality.json` 评估单轮面试决策。

核心维度：

- `decision_quality`：该追问、出新题或收尾时是否决策正确
- `delegation_quality`：Chief 是否在合适时机委托 Evaluator / Designer
- `signal_coverage`：Evaluator 是否覆盖 golden 中的信号与弱点

## 当前状态

本报告先记录实验入口和指标口径。实际 baseline/experiment 分数需要在具备 LLM key 的环境中运行：

```bash
cd backend
uv run python -m app.eval.cli run --suite interviewer_quality --system-version agentic-v1
```

后续补充分数表和 bad case 分析。
