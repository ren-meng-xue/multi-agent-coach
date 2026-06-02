# Supervisor 改用真 Subagent 并行调度

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 supervisor 在 `implementation` step 的"顺序切面具"升级为用 Claude Code Agent 工具真正并行召唤 `backend-engineer` + `frontend-engineer` subagent，实现 `.ai/workflows/feature.yaml` 已声明但尚未落地的 `mode: parallel`。同步清理因此变为死代码的 `.ai/agents/` 面具文件，保留 `supervisor.md` 和 `planner.md`。

**Architecture:**
- `.claude/agents/*.md` 已创建（backend / frontend / tester / reviewer），是 Claude Code 引擎可直接启动的 subagent system prompt。
- `supervisor.md` 需新增"Subagent Dispatch"段落，声明哪些 step 改用 Agent 工具、并行还是串行、各自写哪些文件、status.json 由谁管。
- `CLAUDE.md §0` 补充说明"并行 step 由 supervisor 用 Agent 工具发起真 subagent，非切面具"。
- `.ai/agents/{backend,frontend,tester,reviewer}.md` 迁移内容后删除，避免新旧两套并存造成混乱。

**Tech Stack:** Markdown / Claude Code `.claude/agents/` subagent protocol / Agent OS workflow yaml

---

## 关键设计决策

### 哪些 step 改用 subagent，哪些保持面具

| Step | 调度方式 | 理由 |
|---|---|---|
| `implementation`（`mode: parallel`） | Agent 工具并行调 backend-engineer + frontend-engineer | feature.yaml 已声明 parallel，两者无依赖可真并行 |
| `implementation`（`mode: sequential`） | 顺序 Agent 工具调用，或保持面具切换 | bugfix/hotfix 通常只改单侧 |
| `review` | Agent 工具调 reviewer | reviewer 无需用户交互，可独立跑 |
| `qa` | Agent 工具调 tester | tester 无需用户交互，可独立跑 |
| `planning` | 保持面具（planner） | 需要展示 plan.md 并等用户拍板，卡点交互在 supervisor 层 |

### status.json 并发写入避免

subagent 只写自己负责的文件（backend → `handoff.md` 追加段；frontend → `handoff.md` 追加段）。  
status.json 的 state 变更**只由 supervisor** 在收到两个 subagent 都完成后写入。两个 subagent 的 system prompt 中明确禁止修改 status.json。

---

## File Map

| 角色 | 路径 | 变更 |
|---|---|---|
| 调度大脑 | `.ai/agents/supervisor.md` | 新增 Subagent Dispatch 段；Auto Relay Rule 补充并行调用逻辑 |
| 全局协议 | `CLAUDE.md` §0 | 补充"并行 step 用真 subagent"说明 |
| 后端 subagent | `.claude/agents/backend.md` | 补充"禁止写 status.json"规则（已有文件，小改） |
| 前端 subagent | `.claude/agents/frontend.md` | 同上 |
| 测试 subagent | `.claude/agents/tester.md` | 确认内容完整，无需改动 |
| 审查 subagent | `.claude/agents/reviewer.md` | 确认内容完整，无需改动 |
| 面具清理 | `.ai/agents/backend.md` | 删除（内容已迁移到 .claude/agents/） |
| 面具清理 | `.ai/agents/frontend.md` | 删除 |
| 面具清理 | `.ai/agents/tester.md` | 删除 |
| 面具清理 | `.ai/agents/reviewer.md` | 删除 |

---

## Task 1：更新 supervisor.md，新增 Subagent Dispatch 段

**Files:**
- Modify: `.ai/agents/supervisor.md`

### Step 1-1：在 Skill Dispatch 表之后新增 Subagent Dispatch 段落

- [ ] 打开 `.ai/agents/supervisor.md`，在 `## Skill Dispatch` 段落之后插入新段落 `## Subagent Dispatch`

新段落内容：

```markdown
## Subagent Dispatch（真并行调度）

当 workflow step 的 `mode: parallel` 且 `owners` 包含多个角色时，supervisor 改用 Agent 工具真正并行调起对应 subagent，而非顺序切面具。

### 并行调用规则

1. **同时发起**：在同一条回复中输出多个 Agent 工具调用，目标分别为 `backend-engineer` 和 `frontend-engineer`
2. **prompt 格式**：每个 subagent 的 prompt 必须包含：
   - task_id（当前任务目录路径）
   - 本次需要完成的 step 名称
   - 需要读取的 plan.md 路径
   - 需要追加的 handoff.md 路径
   - 明确禁止：不得修改 status.json
3. **等待完成**：两个 subagent 都返回后，supervisor 才更新 status.json
4. **冲突检测**：收到两个 subagent 的 handoff 段后，检查是否有未解决的冲突；如有，进入 blocked

### 串行 step 的 subagent 调用

`review` 和 `qa` step 虽然不并行，但也改用 Agent 工具调起独立 subagent（非切面具）：

```
review step → Agent(reviewer, prompt=<task context>)
qa step     → Agent(tester, prompt=<task context>)
```

收到 subagent 返回结果后，supervisor 读取 review.md / handoff.md 的结论（APPROVED / CHANGES_REQUESTED / PASSED / FAILED），再决定下一步流转。

### 仍保持面具的 step

- `planning`：需要展示 plan.md 并等用户拍板，交互在 supervisor 层
- `conflict-resolution`：需要向用户呈现冲突摘要并等裁决
- `ship`：发布前卡点需要用户确认
```

### Step 1-2：更新 Auto Relay Rule，补充并行调用时机

- [ ] 在 `Auto Relay Rule` 段落里，在"切到下一 step → 戴对应 owner 面具"之前加一条判断：

```markdown
- 若该 step 的 `mode: parallel` 且 `owners` 有多个角色 → 走 Subagent Dispatch，用 Agent 工具并行调起；收到全部结果后再更新 status.json
- 其余 step → 按原面具切换逻辑
```

---

## Task 2：更新 CLAUDE.md §0，补充并行 subagent 说明

**Files:**
- Modify: `CLAUDE.md`

### Step 2-1：在 §0 "七条硬规则"之前补充并行机制说明

- [ ] 在 §0 末尾（七条硬规则之后、§1 之前）追加：

```markdown
### 并行 Step 的 Subagent 机制

当 workflow step 声明 `mode: parallel` 时，supervisor 使用 Claude Code Agent 工具真正并行调起多个 subagent（定义在 `.claude/agents/`），而非顺序切面具。这是 feature workflow `implementation` step 的默认执行方式。Subagent 只写自己负责的文件，status.json 由 supervisor 在全部 subagent 完成后统一更新。
```

---

## Task 3：补全 .claude/agents/ 中的"禁止写 status.json"规则

**Files:**
- Modify: `.claude/agents/backend.md`
- Modify: `.claude/agents/frontend.md`

### Step 3-1：backend.md 规则补充

- [ ] 在 `.claude/agents/backend.md` 的"规则"部分追加一条：
  - `禁止读写 status.json —— 状态流转由 supervisor 管理`

### Step 3-2：frontend.md 规则补充

- [ ] 在 `.claude/agents/frontend.md` 的"规则"部分追加一条：
  - `禁止读写 status.json —— 状态流转由 supervisor 管理`

---

## Task 4：删除已迁移的 .ai/agents/ 面具文件

**前置条件：** Task 1、2、3 全部完成后执行。

**Files:**
- Delete: `.ai/agents/backend.md`
- Delete: `.ai/agents/frontend.md`
- Delete: `.ai/agents/tester.md`
- Delete: `.ai/agents/reviewer.md`

### Step 4-1：确认 .claude/agents/ 内容完整

- [ ] 对比 `.ai/agents/backend.md` 和 `.claude/agents/backend.md`，确认后者包含所有关键规则（禁止修改前端、必须写 handoff.md 等）
- [ ] 对比 `.ai/agents/frontend.md` 和 `.claude/agents/frontend.md`，同上
- [ ] 对比 `.ai/agents/tester.md` 和 `.claude/agents/tester.md`，确认测试命令和 PASSED/FAILED 规则完整
- [ ] 对比 `.ai/agents/reviewer.md` 和 `.claude/agents/reviewer.md`，确认 Verdict 规则完整

### Step 4-2：删除面具文件

- [ ] `rm .ai/agents/backend.md`
- [ ] `rm .ai/agents/frontend.md`
- [ ] `rm .ai/agents/tester.md`
- [ ] `rm .ai/agents/reviewer.md`

---

## 验收标准

- [ ] supervisor.md 有 `Subagent Dispatch` 段，说明并行 step 的 Agent 工具调用规则
- [ ] CLAUDE.md §0 有并行 subagent 机制说明
- [ ] `.claude/agents/backend.md` 和 `frontend.md` 有"禁止写 status.json"规则
- [ ] `.ai/agents/{backend,frontend,tester,reviewer}.md` 已删除
- [ ] `.ai/agents/supervisor.md` 和 `.ai/agents/planner.md` 保留不动
- [ ] 在对话里发起"请并行完成：backend-engineer 实现后端，frontend-engineer 实现前端"，观察 Claude Code 同时启动两个 subagent
