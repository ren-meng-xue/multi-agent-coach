# Phase 4-parallel-eval 实施 Plan（事后补 · LLM-as-Judge 评估框架）

**对应 Spec**：⚠️ 缺失。本 plan 同时承担一份"轻量 spec 提炼"（见 §零）。如果要走完整 spec 流程，请额外跑 `/spec` 产出 `docs/superpowers/specs/2026-05-28-phase4-parallel-eval-design.md`。
**分支**：`feat/phase4-parallel-eval`
**目标**：建立一个 **可重复、可对比、可回归** 的 LLM-as-Judge 评估框架，能持续测量本项目 5 类 Agent 输出质量（question / scoring / followup / review / plan），支持 baseline ↔ experiment 的回归对比与趋势监控。
**Plan 性质**：代码已先于 plan 落地（这是 protocol 违背），本 plan 按"现状盘点 + 补 gap + 收口"三段反向组织，**不重写已经写好的代码**，只补 plan 应有的责任：定义边界、暴露未做的事、给出验收门槛。

---

## 零、轻量 Spec 提炼（因 spec 缺失，写在此处）

### 0.1 问题陈述

| 现象 | 痛点 |
|------|------|
| Phase 1-5 已有 5 个 Agent 子图、~20 处 LLM 调用 | 没法回答"这次改的 prompt / 模型 / 节点逻辑，到底有没有让产品变差" |
| 现有测试覆盖结构正确性（"接口被调用了") | 不覆盖**质量正确性**（"输出到底好不好") |
| 改 prompt 没有"基线"概念 | 调一次 prompt 就要靠人眼随便点几下，主观不可比 |

### 0.2 设计原则（已隐含在代码里，本 plan 显式化）

1. **LLM-as-Judge 是必选项，不是 nice-to-have**：项目所有产出都是自然语言，单测无法判分。
2. **数据持久化先 SQL，不引 Vector DB**：和 Phase 5 共享记忆层一致的取舍。
3. **3 种 judge 模式并存**：rubric（细粒度评分）、comparative（A/B 对比）、binary（pass/fail 冒烟），各有用途，不互相替代。
4. **5 类 target_type**：与 Agent 节点产物一一对应 —— question（出题）/ scoring（评分一致性）/ followup（追问）/ review（复盘）/ plan（训练计划）。
5. **dev-only**：默认不对外暴露；通过 `RUN_LLM_EVAL` 环境变量 + dev_auth_bypass 双重门控。
6. **不阻塞主流程**：评估在 BackgroundTask / CLI 异步跑，不影响在线 API 延迟。

### 0.3 范围

- ✅ 在范围：judge 实现 / runner 调度 / 数据持久化 / 回归对比 / CLI / API
- ❌ 不在范围：frontend UI、CI 集成、生产环境真实流量评估、跨用户对比、自动调 prompt

### 0.4 与项目其它 phase 的关系

```
Phase 1-5    →  生成产物（question / scoring / followup / review / plan）
                            │
                            ▼
Phase 4-parallel-eval（本期） →  评估产物质量 + 跨版本对比
                            │
                            ▼
Phase 6+（未启动）          →  自动调优 / vector retrieval / 对话式 coach
```

---

## 一、总体策略

- **现状盘点优先**：先把"已经做了什么"枚举清楚，标 ✅ / 🟡 / ❌；再写"还差什么"。
- **不重构**：除明显违背 CLAUDE.md 规范的地方（见 §五 收口工作），其它代码暂不重构。
- **TDD 反推不现实**：代码已落地。本 plan 用"已有 5 份测试文件 + 539 行测试"作为既成事实，下一步补缺测试。
- **验证命令**（每步实现后跑）：
  - 后端：`cd backend && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy app && .venv/bin/python -m pytest tests/`
  - 真实评估冒烟：`cd backend && RUN_LLM_EVAL=<secret> uv run eval-cli run --suite interviewer_v0 --limit 1`（**当前会跑 mock 不会跑真 Agent**，是后续 Step S1 要修的事）

---

## 二、已落地清单（✅ 已完成）

### 2.1 数据模型层

| 表 | 文件 | 行数 | 状态 |
|----|------|------|------|
| `eval_suites` | `backend/app/models/eval.py` | 24-46 | ✅ |
| `eval_cases` | `backend/app/models/eval.py` | 49-77 | ✅ |
| `eval_runs` | `backend/app/models/eval.py` | 80-120 | ✅ |
| `eval_results` | `backend/app/models/eval.py` | 123-157 | ✅ |
| `eval_comparisons` | `backend/app/models/eval.py` | 160-189 | 🟡 表已建 / 无写入路径 |
| Alembic 迁移 | `backend/alembic/versions/cbe658f34eb2_add_eval_tables.py` | 121 | ✅ |

### 2.2 评估维度

| Target | 维度数 | pass_threshold 范围 | 状态 |
|--------|--------|---------------------|------|
| `question` | 4（relevance / specificity / depth / clarity） | 6.0 | ✅ |
| `scoring` | 5（4 个 score_agreement 维度 + signal_reasonableness） | 6.0–7.0 | ✅ |
| `followup` | 3（weakness_targeting / specificity / depth_probe） | 6.0–7.0 | ✅ |
| `review` | 4（insight_depth / cross_session / actionability / tone） | 6.0–7.0 | ✅ |
| `plan` | 4（weakness_alignment / specificity / feasibility / role_accuracy） | 6.0–7.0 | ✅ |

定义在 `backend/app/eval/dimensions.py:26-157`，**总共 20 个评估维度**。

### 2.3 Judge 实现

| Judge | 模式 | 调用次数 | fallback | 状态 |
|-------|------|----------|----------|------|
| `RubricJudge` | rubric | 2 次 LLM（reasoning stream + structured score） | 全维度兜底 5.0 + reasoning="Judge failed" | ✅ |
| `ComparativeJudge` | comparative | 1 次 LLM（structured output） | tie + confidence=0.0 | ✅ |
| `BinaryJudge` | binary | 1 次 LLM（structured output） | passed=False + confidence=0.0 | ✅ |
| `SelfReflectionJudge`（wrapper） | 任意 + 反思 | 内层 + 反思 1 次 | 透传内层结果 | ✅ |

重试装饰器：`_retry_llm`（stop_after_attempt(3) + wait_exponential），覆盖 `APIConnectionError / APITimeoutError / InternalServerError / RateLimitError`，符合 CLAUDE.md 第 8 条。✅

### 2.4 编排与持久化

- `EvalRunner`：semaphore 限并发 5，per-case try/except，写 `EvalResult`，更新 `completed_cases`。位置 `backend/app/eval/runner.py:11-69`。✅
- `EvalStorage`：CRUD（get_suite_by_name / import_suite / create_run / update_run / save_result / get_run / get_results / get_latest_runs）。位置 `backend/app/eval/storage.py:10-108`。✅
- `RegressionTester`：`compare_runs`（improved/degraded/stable 三桶）+ `detect_regression`（improving/stable/declining）。位置 `backend/app/eval/regression.py:7-68`。✅

### 2.5 入口

- **CLI**：`eval-cli` 已注册到 `pyproject.toml:33`，6 个子命令（run / import-suite / list-suites / compare / trend / report）。位置 `backend/app/eval/cli.py`。✅
- **API**：6 个 endpoint，挂在 `/api/v1/eval/*`，dev-only 鉴权。位置 `backend/app/api/v1/eval.py`。✅
- **Reporter**：markdown + json 输出。位置 `backend/app/eval/reporter.py`。✅

### 2.6 测试

| 文件 | 行数 | 覆盖范围 |
|------|------|----------|
| `test_eval_dimensions.py` | 22 | DIMENSIONS 结构形状 |
| `test_eval_schemas.py` | 130 | RubricJudgeScore / ComparativeScore / BinaryScore 边界 |
| `test_eval_models.py` | 141 | 5 张表 ORM 字段 |
| `test_eval_judge.py` | 184 | 3 个 Judge 的 mock LLM 测试 |
| `test_eval_api.py`（integration） | 62 | API 路由挂载 + 鉴权 |
| **合计** | **539** | — |

---

## 三、🟡 已写但不可用的部分（半成品）

### 3.1 `mock_system_call` 是 **mock**（最大债务）

位置：`cli.py:26-28` + `api/v1/eval.py:58-61`

```python
async def mock_system_call(input_json):
    await asyncio.sleep(0.1)
    return {"answer": "mock api answer"}
```

**含义**：整个 eval 框架接收 `cases` → 调"被评估系统" → 调 judge 评分。但"被评估系统"是个永远返回 `{"answer": "mock answer"}` 的占位函数。**即便 judge 是真 LLM，也是在评一个假答案**，得分没有任何意义。

**影响**：眼下 1400 行代码 + 5 张表 + 1 份迁移在 production-ready 表面下，实际 **从未产出过一次有价值的评估数据**。

### 3.2 `aggregate_scores` 字段没人写

- `EvalRun.aggregate_scores` 字段已定义（`models/eval.py:108`）。
- `EvalRunner.run` 完成后只更新 `status=completed`，**没有计算 aggregate**（`runner.py:69`）。
- `RegressionTester.detect_regression` 依赖 `aggregate_scores`（`regression.py:50-52`），但因为没人写，**趋势曲线永远是 0**。

### 3.3 `EvalComparison` 表创了，但 `compare_runs` 不往里写

- `compare_runs` 只返回 dict（`regression.py:11-41`），没有写 `eval_comparisons` 表。
- 表只有 schema、没有 use site。要么删表，要么补写入路径。

### 3.4 `datasets.py` 只有占位实现

- `load_suite` 只是 `json.load`。
- `list_suites()` 读 `data/benchmarks/*.json`。
- 实际 seed 文件 `backend/data/benchmarks/interviewer_v0.json` **只有 1 个 stub case**（`q_001`，input 是 `{"role": "AI"}`，golden 是 `{"overall": 8.0}`）。
- 没有 5 个 target_type 的真实 benchmark cases。

### 3.5 鉴权违背 pydantic-settings

`api/v1/eval.py:32-38` 直接读 `os.getenv("RUN_LLM_EVAL")` / `os.getenv("APP_ENV")`，违背 CLAUDE.md 后端规范第 1 条「配置必须走 pydantic-settings」。

### 3.6 日志违背 structlog

`runner.py:58` 用 `print(f"Error running case ...")` 而不是 `structlog`，违背 CLAUDE.md 第 6 条「禁止 print」。

### 3.7 `__init__.py` 空文件

`backend/app/eval/__init__.py` 0 字节，没暴露公共 API。CLI 入口 `eval-cli = "app.eval.cli:main"` 直接打到 `cli.py`，但模块本身没有公开符号。

---

## 四、❌ 完全缺失的部分

### 4.1 没有 spec / 没有 plan / 没有 QA 报告

| Artifact | 应在 | 现况 |
|----------|------|------|
| spec | `docs/superpowers/specs/2026-05-28-phase4-parallel-eval-design.md` | ❌ |
| plan | `docs/superpowers/plans/2026-05-28-phase4-parallel-eval.md` | ✅ **本文件** |
| qa-report | `docs/superpowers/qa-reports/phase4-parallel-eval-qa-report.md` | ❌（也未跑过 QA） |

### 4.2 没有"接通真实 Agent"的适配层

eval 框架需要 5 个 `system_call(input_json) -> dict`：

| target_type | 应该调 | 当前 |
|-------------|--------|------|
| `question` | `prepare` agent 的出题节点 | ❌ mock |
| `scoring` | `interviewer` 子图的 evaluator_node | ❌ mock |
| `followup` | `interviewer` 子图的 master/followup 节点 | ❌ mock |
| `review` | `coach` 子图的 review_node | ❌ mock |
| `plan` | `coach` 子图的 plan_node | ❌ mock |

### 4.3 没有真实 benchmark dataset

需要每个 target_type 至少 10 个真实 case + golden，目前合计 1 个 stub。

### 4.4 没有 frontend UI

`/coach`、`/reports`、`/dashboard` 都没接 eval。开发者跑了 eval 之后只能去翻 DB 或 CLI 输出。

### 4.5 没有端到端跑过的证据

没有任何一次 `eval_runs.status='completed'` 的真实记录，没有 baseline，没有"prompt 调优带来的得分变化"的证据。

### 4.6 没有 integration test 覆盖完整 flow

`test_eval_api.py` 只有 62 行，验证路由挂载 + 鉴权，**没有从 cases 输入 → Agent 调用 → Judge 评分 → DB 写入 → Reporter 输出的端到端测试**。

---

## 五、收口工作清单（按推荐顺序，独立 commit）

> 每步都要先写/扩展失败测试，再实现。每步独立 commit，等待用户确认。

### Step S1 · 接通真实 Agent（最关键）— 风险：中

**目标**：把 `mock_system_call` 替换为 5 个对应 target_type 的真实 Agent 调用。

**改动**：
- 新建 `backend/app/eval/system_calls.py`，导出 `SYSTEM_CALLS: dict[TargetType, Callable]`。
- 每个 target_type 一个轻封装：从 `input_json` 取出参数 → 调对应 LangGraph 子图的相关节点（用 `ainvoke` 单节点跑，不跑整图） → 返回标准化 dict。
- `cli.py:26-28` 和 `api/v1/eval.py:58-61` 替换 `mock_system_call` 为 `SYSTEM_CALLS[target_type]`。

**测试**（新建 `tests/unit/test_eval_system_calls.py`）：
- 5 个 target_type 各一个 mock LLM 测试，验证输入 schema → 输出 schema 正确。
- 1 个集成测试：用真实 DB + mock LLM 跑 `EvalRunner.run` 一个 case，验证 result 落表。

**风险**：调真实 Agent 可能耦合 LangGraph state shape。缓解：用 `ainvoke` 单节点测，不跑整图；如果耦合太重，回退为"用 Agent 的 service 层薄包装"。

**Commit**：`feat(eval): wire eval system_calls to real agent nodes`

---

### Step S2 · 补 benchmark dataset — 风险：低

**目标**：每个 target_type 至少 10 个真实 case，落 `data/benchmarks/*.json`。

**改动**：
- `data/benchmarks/interviewer_v0.json`：补 10 个 `question` case、10 个 `followup` case、10 个 `scoring` case。
- 新建 `data/benchmarks/coach_v0.json`：10 个 `review` case、10 个 `plan` case。
- 每个 case 含 `input_json`（真实历史 session 切片） + `golden`（人工写的参考答案 + overall 分）。
- 跑 `eval-cli import-suite --file data/benchmarks/*.json` 入库。

**测试**：
- `tests/unit/test_eval_benchmarks.py`：扫描 `data/benchmarks/*.json`，验证每个 case 字段完整、target_type ∈ TargetType。

**风险**：写 golden 是脑力活，可能拖慢节奏。缓解：先写 5 个/类，跑通整条管线再补到 10。

**Commit**：`feat(eval): seed real benchmark cases for 5 target types`

---

### Step S3 · 计算并写入 aggregate_scores — 风险：低

**目标**：`EvalRunner.run` 完成时计算 aggregate 并 update。

**改动**：
- 在 `runner.py:69` 之前加：聚合本 run 所有 results 的 overall_score（按 target_type 分组取平均 + 总体平均），写入 `eval_runs.aggregate_scores`。
- 形状参考 `EvalRunSummary.results_by_type`：`{target_type: {avg, pass_rate, count}, "overall": float}`。

**测试**（扩展 `test_eval_judge.py` 或新建 `test_eval_runner.py`）：
- 跑 3 个 mock case → 验证 `aggregate_scores` 字段已写入 + 总体平均算对。

**风险**：低。

**Commit**：`feat(eval): compute and persist aggregate_scores per run`

---

### Step S4 · 修 EvalComparison 写入路径 — 风险：低

**目标**：`compare_runs` 把对比结果落表，便于事后回看。

**改动**：
- `regression.py:compare_runs` 末尾追加：对每个 target_type 维度生成一条 `EvalComparison` 行（run_a_id / run_b_id / metric / score_a / score_b / delta / winner / significant）。
- "significant" 阈值：|delta| > 0.5 算显著（与现有 improved/degraded 阈值对齐）。

**测试**：
- `test_eval_regression.py`：跑 2 个 mock runs → compare → 验证 `eval_comparisons` 行已写入。

**风险**：低。

**Commit**：`feat(eval): persist run-to-run comparisons to eval_comparisons table`

---

### Step S5 · 收口违规：config + logging — 风险：低

**目标**：把 `os.getenv` 收回 `pydantic-settings`，把 `print` 收回 `structlog`。

**改动**：
- `backend/app/core/config.py` 增字段：`run_llm_eval_secret: str | None = None`、`app_env: Literal["dev","prod"] = "dev"`。
- `api/v1/eval.py:32-38` 改用 `get_settings()`。
- `runner.py:58` 改用 `structlog.get_logger("app.eval.runner").error(...)`。

**测试**：
- 现有 `test_eval_api.py` 把 `os.environ` patch 改成 `monkeypatch.setattr(get_settings, ...)`。

**风险**：低。

**Commit**：`refactor(eval): migrate config to pydantic-settings and print to structlog`

---

### Step S6 · 端到端跑一次真实评估，落 QA 报告 — 风险：中

**目标**：用真实 LLM 跑一次 baseline run，证明整条管线 work，落档 `docs/superpowers/qa-reports/phase4-parallel-eval-qa-report.md`。

**改动**：
- 跑 `RUN_LLM_EVAL=<secret> uv run eval-cli run --suite interviewer_v0 --judge-model gpt-4o`。
- 等 run 完成，跑 `eval-cli report --run-id <uuid> --format markdown` 输出基线报告。
- 写 QA 报告（参考 phase5-qa-report.md 格式）：覆盖目标对账、commit 序列、自动化验证、关键实现点、已知风险、结论。

**风险**：会真的烧 tokens。50 个 case × rubric (2 次 LLM/case) ≈ 100 次 GPT-4o 调用。预估 < $5。

**Commit**：`docs: add phase 4-parallel-eval qa report with first real baseline run`

---

### Step S7（可选） · frontend `/dashboard` 或新页面接 eval — 风险：低，但与 review scope 关系不大

**目标**：让 baseline / experiment / trend 在前端能可视化。

**判断**：本期建议**不做**。理由：
- eval 是 dev-only 工具，没有用户消费。
- CLI + markdown 报告 + DB 查询足够开发者使用。
- 留作 Phase 6+ 决策（如果决定开放评估面板给非工程人员）。

**Commit**：跳过。

---

## 六、风险与回退

| 编号 | 风险 | 缓解 |
|------|------|------|
| E1 | mock_system_call 替换后，LangGraph state shape 与 eval input 不对齐 | S1 测试逐 target_type 验证；接不上的回退为 service 层薄包装 |
| E2 | 真 LLM 评估烧 tokens | `--limit` 参数控制；默认只跑 5 case 冒烟；nightly 才跑全量 |
| E3 | benchmark golden 质量决定一切（garbage in → garbage out） | golden 必须人工 review，最好同侪/二人核对 |
| E4 | `RubricJudge._reasoning_stream` 跑完不用结果（reasoning 流式只是为了 prompt cache？） | 是设计意图（先 reasoning 后 score 的 CoT），但**当前实现 reasoning 输出没存**。S6 之前先决定要不要存 reasoning 到 `judge_reasoning` 字段 |
| E5 | `SelfReflectionJudge` 在 runner 里没接入 | 当前 cli/api 只 new BinaryJudge/ComparativeJudge/RubricJudge，没 wrapper。S6 之前决定要不要默认套 SelfReflection |
| E6 | Alembic 迁移上线失败 | 已有 downgrade（`cbe658f34eb2:109-120`）；上线前预演一次 upgrade → downgrade → upgrade |

---

## 七、不做的事（明确边界）

- 不做 frontend UI（Step S7 已跳过）
- 不做 CI 集成（暂不在每次 PR 自动跑 eval）
- 不做自动调 prompt / 自动迭代（属 Phase 6+）
- 不引入 vector retrieval / embedding-based similarity（一致延后到 Phase 6+）
- 不重构 `SelfReflectionJudge`（已实现但未接入，先观察是否真的需要）
- 不动 `coach_opening.py`（与 eval 无关）

---

## 八、Phase 4-parallel-eval 可合入 main 的检查点

按"最小可合入"原则，**S1 + S2 + S3 + S5 + S6 完成**即可合入；S4 / S7 留作后续。

| 步骤 | 内容 | 必须？ |
|------|------|--------|
| S1 | 接通真实 Agent | ✅ 必须 |
| S2 | 补 benchmark（每类至少 5 个） | ✅ 必须 |
| S3 | 写 aggregate_scores | ✅ 必须 |
| S4 | EvalComparison 写入 | 🟡 推荐 |
| S5 | config + logging 收口 | ✅ 必须（合规） |
| S6 | 端到端跑通 + QA 报告 | ✅ 必须（验收证据） |
| S7 | frontend | ❌ 跳过 |

未完成 S1/S2/S6 之前 **不应合入 main** —— 否则等于把 1400 行"形状对、内容假"的代码塞进主分支。

---

## 九、合入后的衍生项（仅记录，不实施）

- 自动跑 eval 的 nightly CI（独立 workflow，独立 secrets）
- 用 eval 结果驱动 prompt 自动调优（DSPy / textgrad）
- 引入 LLM-as-Judge 之外的 metric（latency p99 / token cost / tool-call accuracy）
- SelfReflectionJudge 默认开启 + 对比开/关的 calibration
- 把 eval 报告嵌入 `/ship` 工作流（基线退化阻止发布）

---

## 十、本 plan 与项目 protocol 的对账

| 协议规则（`docs/protocols/ai-workflow-protocol.md`） | 本期遵守情况 |
|-----------------------------------------------------|--------------|
| 中风险任务流程：`spec → planning → implementation → review → qa` | ❌ 跳过 spec + planning，直接 implementation |
| 所有重要阶段必须生成 markdown artifacts | 🟡 implementation 已完成，spec 缺失，**plan 本期补齐**，QA 报告留到 Step S6 |
| `/plan-ceo-review` 输出在 `docs/reviews/ceo-review.md` | ⏸ 本期跳过 review（用户选择"先补 plan、不评审"） |
| 后端：配置必须走 pydantic-settings | ❌ → Step S5 修 |
| 后端：日志 structlog，禁止 print | ❌ → Step S5 修 |
| 后端：LLM 调用 retry + timeout + 失败日志 | ✅ judge.py 有 _retry_llm 装饰器 |
| 后端：数据库迁移必须走 Alembic | ✅ 有 cbe658f34eb2 |
| 测试：新功能至少 success case + failure case | 🟡 已有 539 行测试，但缺 end-to-end |

**结论**：代码实现质量整体可接受（retry / structured output / 5 张表设计合理 / 3 种 judge 实现完整），但 **流程违背 + mock 占位 + 未跑通真实数据**导致目前不应直接合入。本 plan 把 gap 标完、路径标清楚，剩下就看你按 Step S1-S6 推进。

---

## 十一、为什么这份 plan 在 "review scope" 决策时被推荐成为下一步

用户在 `/plan-ceo-review` 中选择了 C「先补 plan、不评审」。本 plan 的目的是：

1. 让"flow 违背"显性化 —— 你看到这份 plan 之后，下次起新模块前会知道先写 spec。
2. 让"mock 占位"显性化 —— §三 3.1 列出来，不再隐藏在 1400 行表面之下。
3. 让"可合入门槛"显性化 —— §八 给出可执行的 Definition of Done。
4. 保留 review 入口 —— 你随时可以基于这份 plan 跑 `/plan-ceo-review` 或 `/plan-eng-review`，把"要不要继续做 eval"的战略问题摆上桌。

如果你确认要继续做 eval，下一步推荐顺序：
1. 跑 `/spec` 把 §零的 spec 提炼写成完整 spec 文件（可选；本 plan 自带 spec 提炼，已够用）
2. 跑 `/plan-eng-review` 让 eng 视角审一遍这份 plan（推荐）
3. 按 §五 Step S1 → S6 逐步落地，每步独立 commit + 等用户确认
