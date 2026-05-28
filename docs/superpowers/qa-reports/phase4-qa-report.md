# Phase 4+ Candidate Modeling · QA Report

- 日期：2026-05-28
- 范围：候选人建模 + latent signals 提取 + 信号驱动追问
- 关联 Spec：[`../specs/2026-05-28-phase4-plus-candidate-modeling-design.md`](../specs/2026-05-28-phase4-plus-candidate-modeling-design.md)
- 关联 Plan：[`../plans/2026-05-28-phase4-plus-candidate-modeling.md`](../plans/2026-05-28-phase4-plus-candidate-modeling.md)
- 分支：`feat/phase4-parallel-eval`
- 报告人：实施与 review 由 Claude Code 完成，手工 QA 由用户执行

---

## 1. 目标对账

Phase 4+ 的核心目标是把面试官 Agent 从"关键词匹配"切换到"信号驱动"：

| 目标 | 落点 | 状态 |
|---|---|---|
| 评估官跨轮提取 candidate_level / latent_signals / missing_dimensions | `evaluator_node` | ✅ |
| candidate_profile 跨轮累积（latent_signals 去重保序，latest_level 取最新） | `evaluator_node` | ✅ |
| MASTER 输出结构化 followup_focus 指导下一动作 | `master_node` + `_InterviewMasterDecision` | ✅ |
| followup 消费 focus + latent_signals + missing_dimensions，拒绝万金油 | `followup_node` + `FOLLOWUP_SYSTEM_PROMPT` | ✅ |
| SSE 透传新字段到前端 | `stream_interviewer_turn_events` | ✅ |
| 前端 Trace 面板渲染 candidate_level / latent_signals chips | `trace-node.tsx` | ✅ |

---

## 2. Commit 序列

```
9ea1f6d  feat(frontend): render candidate profile chips on evaluator trace node
ba403de  feat(interviewer): stream candidate_level and followup_focus via SSE
655d517  feat(interviewer): followup consumes focus, latent_signals, missing_dimensions
c7e107b  feat(interviewer): master decides followup_focus from candidate profile
c3f4e1a  feat(interviewer): evaluator extracts candidate_level and latent signals across turns
4acc5ae  feat(interviewer): extend state with candidate_profile and followup_focus
24d8a39  docs: add phase 4+ candidate modeling spec and plan
```

总改动 +500 / -25，分布在 12 个文件（后端 7 / 前端 5）。

---

## 3. 自动化验证

| 命令 | 结果 |
|---|---|
| `cd backend && .venv/bin/python -m ruff check .` | clean |
| `cd backend && .venv/bin/python -m mypy app` | clean |
| `cd backend && .venv/bin/python -m pytest tests/` | **137 passed** |
| `cd frontend && pnpm test` | **83 passed** |
| `cd frontend && pnpm typecheck` | clean |
| `cd frontend && pnpm build` | ⏳ **未执行**（见 §6 遗留 TODO） |

### Phase 4+ 新增/扩展测试条目

- `backend/tests/unit/test_interviewer_master_node.py`：+4（schema 默认值、focus 写状态、context 含 profile、闭环兜底）
- `backend/tests/unit/test_interviewer_evaluator_node.py`：+6（schema 字段、消息窗口截断、profile 累积去重、focus 注入 prompt 等）
- `backend/tests/unit/test_interviewer_graph.py`：+2（master node_done payload / evaluator node_done payload）
- `frontend/app/interview/_components/trace-node.test.tsx`：+2（有数据渲染 chips / 无数据不渲染）

---

## 4. 手工 QA（按 Spec §1.2 真实脚本）

### 场景 1.2：beginner 候选人 + workflow_orchestration 信号

用户在 `/interview` 真实输入了 Spec §1.2 的脚本片段：「不知道事件流怎么管 / 平时用 Claude Code 帮我做 / 也试过 Codex」。

观察到的行为：

| 验证点 | 实际结果 | 通过 |
|---|---|---|
| evaluator 在 Trace 卡渲染 `beginner` / `junior` badge | 出现 | ✅ |
| latent_signals chips 至少出现一条工程信号 | 出现 `workflow_orchestration` | ✅ |
| followup 不再追问"为什么选 GPT 5.5 / 参数怎么调" | 未出现 | ✅ |
| followup 转向"event lifecycle / 三类事件统一" | 出现架构向追问 | ✅ |

Phase 4+ 设计目标在该场景下确认达成：系统从候选人口语化描述中识别出隐含工程信号，并把"信号"翻译成工程化追问，而不是机械抓取关键词。

> 备注：手工 QA 由用户在本地 dev 环境执行，未留存截图。本报告复述用户口头反馈，未独立复现。

---

## 5. 已知风险

按风险等级排序，所有项均为可接受、暂不阻塞合入。

### R1 · latent_signals 是 LLM 自由生成字符串，无枚举校验【中】

- **现象**：`_EvaluatorScoring.latent_signals: list[str]` 没限制取值集合，LLM 可能在不同 session 产出近义但不同 key（如 `workflow_orchestration` / `workflow-orchestration` / `event_orchestration`）。
- **影响**：候选人画像跨 session 不可比；`followup_focus="latent_signal:<key>"` 的 key 拼写漂移会让 followup prompt 翻译失准。
- **缓解**：当前用例集很小，未观察到漂移；后续若上线，应加白名单或在 evaluator prompt 里固化枚举。
- **不修原因**：Spec 没要求枚举校验，过早加约束可能伤泛化能力。

### R2 · `followup_focus="latent_signal:<key>"` 翻译质量依赖 LLM【中】

- **现象**：FOLLOWUP_SYSTEM_PROMPT 通过自然语言要求 LLM「用工程化语言翻译信号」，对小模型可能仍退化成万金油（"能展开说说吗？"）。
- **影响**：低质量 LLM 下 followup 体验回退。
- **缓解**：当前使用 GPT-4 级别模型，prompt 内附了一个正向示例锚定。
- **不修原因**：硬编码信号→追问模板会失去信号驱动的灵活性。

### R3 · candidate_profile 仅 session 内累积，未持久化【低】

- **现象**：profile 存在 LangGraph state 里，AsyncPostgresSaver 会随 checkpoint 落库，但跨 session（新 thread_id）不会复用。
- **影响**：用户重新开一场面试时画像清零。
- **缓解**：Spec 明确这是 session 内累积，跨 session 复用属于 Phase 5+ 范围。
- **不修原因**：超出本 Phase scope。

### R4 · followup 测试位置归错文件【低】

- **现象**：`test_followup_injects_focus_and_signals_into_prompt` 等两个 followup 测试放在 `test_interviewer_evaluator_node.py` 里。
- **影响**：维护时不容易找。
- **缓解**：测试逻辑正确，137 测试全通过。
- **修复建议**：下次重构时挪到独立 `test_interviewer_followup_node.py`，本次不动以免污染 commit。

### R5 · master `followup_focus` phase2 失败兜底为空串【低】

- **现象**：`master_node` 中 `_master_phase2_decide` 抛错时 `followup_focus=""`，followup_node 退化到原版（无 focus / 无 signals）。
- **影响**：LLM down 时追问退化但不崩；与原 Phase 3 行为一致。
- **状态**：这是预期行为，已在测试 `test_master_phase2_failure_falls_back` 覆盖。

### R6 · frontend `pnpm build` 未跑【低】

- **现象**：Plan 6.1 要求执行 `pnpm build`（含 eslint 全量扫描 + Next.js 生产构建），本次只跑了 `pnpm test` + `pnpm typecheck`。
- **影响**：未发现的 eslint 警告或 build 阶段错误可能被遗漏。
- **修复建议**：合入前补跑一次 `pnpm build`。详见 §6。

---

## 6. 遗留 TODO

| # | 项 | 优先级 |
|---|---|---|
| T1 | 补跑 `cd frontend && pnpm build`，确认 eslint + production build 通过 | 合入前 |
| T2 | followup 测试搬迁到 `test_interviewer_followup_node.py` | 下次重构时 |
| T3 | latent_signals 是否加枚举白名单 | Phase 5+ 决策 |
| T4 | candidate_profile 跨 session 复用方案 | Phase 5+ |

---

## 7. 结论

Phase 4+ 候选人建模 + 信号驱动追问的实现按 Spec 与 Plan 完成。自动化测试全绿，手工 QA 在 Spec §1.2 主场景下达成预期。已知风险均为可接受范围，未阻塞合入。

唯一阻塞合入项：**T1（前端 `pnpm build`）**。完成后可推远程 / 开 PR。
