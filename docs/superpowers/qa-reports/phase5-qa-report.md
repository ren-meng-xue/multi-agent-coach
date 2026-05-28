# Phase 5 教练 Agent + 共享记忆层 · QA Report

- **日期**：2026-05-28
- **范围**：教练 LangGraph 子图 + `candidate_memory` 持久化表 + 五阶段流程串联 + `/coach` 复盘视图
- **关联 Spec**：[`../specs/2026-05-28-phase5-coach-agent-shared-memory-design.md`](../specs/2026-05-28-phase5-coach-agent-shared-memory-design.md)
- **关联 Plan**：[`../plans/2026-05-28-phase5-coach-agent-shared-memory.md`](../plans/2026-05-28-phase5-coach-agent-shared-memory.md)
- **分支**：`feat/phase4-parallel-eval`
- **报告人**：Gemini CLI (Auto-Edit Mode)

---

## 1. 目标对账

Phase 5 的核心目标是将系统从“单次模拟”升级为“长期教练关系”，建立完整的练-评-学闭环：

| 目标 | 落点 | 状态 |
|:---|:---|:---:|
| **长期记忆持久化**：跨 Session 汇总等级、信号及短板标签 | `CandidateMemory` + `upsert_candidate_memory` | ✅ |
| **面试自动复盘**：面试结束时触发画像更新，不阻塞报告 | `interviewer/nodes.py` (report_node) | ✅ |
| **教练子图实现**：深度叙事复盘 + 结构化训练计划 | `app/agents/coach/` (LangGraph Subgraph) | ✅ |
| **状态驱动导航**：派生 User Stage (Prepare/Interview/Coach) | `derive_user_stage` + `/user/stage` API | ✅ |
| **流式复盘体验**：前端通过 SSE 展示流式文本与计划卡片 | `coach-dashboard.tsx` + `/coach/review` SSE | ✅ |
| **训练计划闭环**：基于建议开启针对性面试 | `CoachPlanCard` + `enterInterviewRoom` | ✅ |

---

## 2. Commit 序列

```
a372de9  test: update model tests for phase 5 tables
e5c0376  feat(frontend): implement state-driven coach dashboard with SSE review and training plans
b605133  feat(api): add coach review sse and plans endpoints
37c4df6  feat(coach): add coach langgraph subgraph with review and plan nodes
0ec6570  feat(coach): derive user stage from session and plan state
9021d0a  feat(interviewer): persist candidate profile to memory on report
0af8a9d  feat(coach): add candidate_memory upsert service
e3adafc  feat(db): add candidate_memory and coach_plans tables
```

总改动涉及 15+ 文件，实现了完整的后端 Agent 逻辑与前端状态机驱动视图。

---

## 3. 自动化验证

| 命令 | 结果 | 备注 |
|:---|:---|:---|
| `cd backend && pytest tests/` | **187 passed** | 覆盖了 Service, Node, API 核心逻辑 |
| `cd frontend && pnpm test` | **83 passed** | 包含 CoachDashboard 状态切换测试 |
| `cd backend && ruff check .` | clean | 符合工程规范 |
| `cd backend && mypy app` | clean | 类型安全校验通过 |
| `cd frontend && pnpm typecheck` | clean | 前端类型安全通过 |

### Phase 5 新增测试模块

- `tests/unit/test_candidate_memory_service.py`: 验证信号去重、FIFO、短板计数。
- `tests/unit/test_interviewer_report_node.py`: 验证面试结束时内存持久化的触发。
- `tests/unit/test_user_stage.py`: 验证 4 种业务场景下的阶段派生。
- `tests/unit/test_coach_nodes.py`: 验证教练子图各节点的独立逻辑。
- `tests/integration/test_coach_endpoint.py`: 验证 API 挂载与 403 防护。

---

## 4. 关键实现点说明 (已根据 Review 修复)

### 4.1 共享记忆层 (Shared Memory)
使用了 `candidate_memory` 表作为 user_id 维度的聚合。
- **数据类型**：已将所有 JSON 字段修正为 `JSONB`，提升了性能并保留了扩展查询能力。
- **信号处理**：采用 FIFO (最近 50 条) 策略，通过集合去重保持画像清晰。

### 4.2 状态驱动的 UI 与 交互优化
- **显式触发逻辑**：根据 Spec 约束，面试结束后不再自动触发复盘。用户需显式点击“开始深度复盘”按钮，从而避免了无效的 LLM 调用。
- **Token 级流式复盘**：后端已从“一次性发送”升级为通过 `astream_events` 产出真实的 Token 流。前端可以实时看到复盘文本逐字蹦出，极大提升了交互的“生命感”。

### 4.3 契约一致性与健壮性
- **API 契约**：修正了 `plans/latest` 在无数据时返回 `null` 而非 `{}`，对齐了前后端类型定义。
- **环境变量**：统一使用 `NEXT_PUBLIC_API_URL`，解决了潜在的 Base URL 配置冲突。
- **后端幂等**：`persist_node` 现在会检查 session 是否已有计划并执行更新操作，防止数据冗余。

---

## 5. 已知风险与备注

- **DB 迁移**：Alembic 迁移脚本手动精简了对 LangGraph 内部表的误操作，后续维护需注意 Alembic autogenerate 的副作用。
- **测试环境**：集成测试中针对 SSE 的全量 mock 较为复杂，目前主要通过 Unit Test 覆盖逻辑，Integration Test 验证路由挂载。

---

## 6. 结论

Phase 5 成功打通了 AI 面试教练的完整闭环。系统现在不仅能“面”，更能“教”。长期记忆层的建立为后续 Phase 6（多 Agent 协同复盘）奠定了坚实的基础。

**建议合入。**
