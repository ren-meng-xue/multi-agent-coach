# Review: QA Bank（用户面试题库）

## Verdict

**APPROVED**（带 1 条 Note，不阻塞进入 qa step）

---

## Alignment Check

- [x] 已覆盖 Task Goal（用户可上传/下载题库 + 面试时 Coach 从题库选题）
- [x] 修改范围符合 Plan（docs/superpowers/plans/2026-06-01-qa-bank.md Task 3-7）
- [x] 未引入明显超范围变更

---

## Scope

Task 3-7 涉及 **8 个后端文件 + 5 个前端文件**，覆盖 plan 中声明的全部 File Map：

**Backend（Task 3-4）**
- `backend/app/schemas/qa_bank.py` ✓
- `backend/app/api/v1/qa_bank.py` ✓
- `backend/app/main.py`（路由挂载）✓
- `backend/app/schemas/interview.py`（TurnRequest 加 `use_qa_bank`）✓
- `backend/app/agents/interviewer/state.py`（InterviewState 加 `qa_bank_items`）✓
- `backend/app/agents/interviewer/nodes.py`（`_state_messages()` 注入题库 block）✓
- `backend/app/services/interview_turn.py`（参数 + session 写标志 + 加载题库）✓
- `backend/app/api/v1/interview.py`（透传 `use_qa_bank`）✓

**Frontend（Task 5-7）**
- `frontend/lib/qa-bank.ts`（client）✓
- `frontend/app/settings/_components/qa-bank-card.tsx` ✓
- `frontend/app/settings/settings-view.tsx`（引入 + 加载 + 渲染 + token state）✓
- `frontend/lib/interview-chat.ts`（`StreamInterviewChatOptions.useQABank` + body 透传）✓
- `frontend/app/interview/_components/interview-chat.tsx`（首轮调用透传）✓
- `frontend/app/coach/coach-dashboard.tsx`（state + summary 加载 + toggle UI + enterInterviewRoom 上下文）✓

---

## Findings

### Blocking Issues

无。

### Risks

- **不可中途切换题库模式**：`session.use_qa_bank` 一旦在首轮（`session.stage == "opening"`）写为 `True`，后续 turn 不会回滚。这符合 plan 的"一次面试一种模式"设计，但若用户期望"中途关闭"会感到困惑。属于设计选择，**不阻塞**。
- **首轮 use_qa_bank=False 后无法再开启**：同上对偶，首轮没传 True，后续即使前端补传也不会触发题库注入。这同样是 plan 的预期行为。
- **`fetchQABankSummary` 鉴权失败时静默回退**（coach-dashboard.tsx L309-314 catch 后给空 summary）：好处是不阻塞 Dashboard 加载；坏处是用户看不到错误。建议加一次 `console.warn` 便于排查（**Suggestion 级**）。

### Suggestions

1. **`qaBankToggle` 在两处渲染**（coach-dashboard.tsx L487、L508）—— plan 只声明"在 enterInterviewRoom 按钮之前"展示。实际同一个 `qaBankToggle` 节点被嵌入两个分支位置（应为不同阶段的入口）。
   - 现状不会出 bug，但**两份 React 节点共享同一变量**实际只会渲染一处（React 不允许同节点出现两次于同一 commit）。需要 QA 时验证哪一个分支真正展示了开关、另一处是否成 dead code。
   - **不阻塞，留 qa 阶段验证**。

2. **`raise BadRequestException(...) from exc`**（qa_bank.py L77-78、L85-86）是对 plan 的**正向改进**（Python 异常链最佳实践），建议保留。无需改回。

3. **`qa_bank_items: list[dict[str, Any]] | None`**（state.py L70）较 plan 的 `list[dict] | None` 更严格，类型友好，建议保留。

### Test Coverage

- Task 2 parser 测试：plan 要求 `pytest tests/test_qa_bank_parser.py -v` 8 passed。handoff.md 自报 `8/8 通过`，需 qa step 复核。
- Task 3-7 plan 未要求新增单元测试。
- 前端测试：handoff.md 提到 `Updated related frontend tests for the new request body and type-safe optional trace callback`，需 qa step 跑 `pnpm test` 验证。

---

## Alignment vs Plan: Spec coverage

对照 plan 末尾 Self-Review 表，逐项核验：

| Spec 需求 | 实现位置 | 状态 |
|-----------|---------|------|
| 下载 Markdown 模板 | `/api/v1/user/qa-bank/template` + `QABankCard` 下载按钮 | ✓ |
| 上传填好的模板解析入库 | `/api/v1/user/qa-bank/upload` + `parse_qa_markdown` + `upsert_qa_bank` | ✓ |
| 按 category 覆盖（不影响其他 category）| `upsert_qa_bank` 仅 delete `items` 中出现的 category | ✓ |
| 缺失必填字段的条目跳过并计数 | `parse_qa_markdown` 返回 `skipped` | ✓ |
| 设置页展示题库条目数量摘要 | `/api/v1/user/qa-bank/summary` + `QABankCard.summaryText` | ✓ |
| 面试开始前的开关（有题库才展示）| `qaBankTotal > 0` 条件渲染 | ✓ |
| `use_qa_bank` 持久化到 session | `interview_turn.py` L339-341 写 `session.use_qa_bank=True` | ✓ |
| Agent 从题库选题（注入提示词）| `nodes.py` `_state_messages` 拼 `【用户已准备的题目库】` block | ✓ |
| 每轮对比参考答案给反馈 | 通过提示词隐式实现，模型可见参考答案 | ✓（待 qa 实测确认） |
| 题库为空但开关开启 → 降级正常模式 | `interview_turn.py` L375-377 `qa_bank_items=[]` 时 `_state_messages` 不注入 block | ✓ |
| 上传非 .md 文件返回 400 | `qa_bank.py` L71-72 `BadRequestException("请上传 .md 格式的文件")` | ✓ |
| `InterviewSession.use_qa_bank` 字段 | Task 1 已交付（不在本次 review 范围，但下游依赖成立）| ✓ |
| 新表 `user_qa_bank` | Task 1 已交付 | ✓ |

---

## Next Action

- next_owner: **tester**
- next_state: **qa**
- qa 重点：
  1. `pytest backend/tests/test_qa_bank_parser.py -v`（确认 8/8 仍然通过）
  2. `pnpm test`（确认前端已更新测试通过）
  3. 手动验证：
     - 设置页下载模板 → 编辑 → 上传 → 摘要刷新
     - 上传非 .md / 空文件 → 400
     - Dashboard `qaBankTotal > 0` 时显示开关；开关切到 ON → 进入面试 → 首轮 system prompt 中应注入题库 block
     - 题库为空但开关开启 → 降级，不应出现 "【用户已准备的题目库】" 文案
     - **建议同时验证 `qaBankToggle` 在 L487 vs L508 两处分支是否都真正可见**
