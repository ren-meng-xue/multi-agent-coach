# TODOS

> 跨 PR 的延后项。已识别但当前 scope 不做的工作。

---

## T-1: dirty tree pre-commit guard

**Source:** `/plan-eng-review` on `feat/phase4-parallel-eval`（codex outside voice C5）/ decision D15
**Status:** Deferred to Phase 4 hooks
**Priority:** P3

**What:** 为每个 `git add ... && git commit` 加 dirty-tree 检查，确认只暂存了 plan 指定的具体文件。

**Why:** plan 用 `git add <具体文件>` 而非 `-A`，风险已受限；但 agent 习惯性 `git add -A` 仍可能误把仓中 30+ 个无关未提交改动一起提交。当前 MVP 阶段靠 plan 明示约束，无机械保护。

**Pros (做):**
- pre-commit hook 可机械 enforce，agent 笔误不会通过
- Phase 4 hook 阶段是天然位置

**Cons (做):**
- MVP scope 不上 hook（spec §3 Non-Goals）
- 增加 hook 维护成本

**Context for future picker:** plan task Step 3 模式是 `git add <文件列表> && git commit -m "..."`。hook 应在 pre-commit 时 diff `git diff --cached --name-only` 与 task 声明的文件列表，不一致则 abort。

**Depends on:** Phase 4 hook 框架启动（spec §3）

---

## T-2: 破坏性动作 confirm 门控

**Source:** `/plan-eng-review` on `feat/phase4-parallel-eval`（codex outside voice C7）/ decision D16
**Status:** Deferred to Phase 4 hooks
**Priority:** P3

**What:** 为破坏性动作（`rm -rf` 删 fixture、`git checkout` 还原文件）加机械化 confirm 门控。

**Why:** 当前 plan Task 8 Step 6 `rm -rf .ai/tasks/TEST-001 TEST-002 TEST-BROKEN`、Task 12 Step 6 `git checkout` 都是局部 scope，路径明确风险低。但未来 agent 跳到不同任务、路径变化时，可能误删实产。

**Pros (做):**
- agent 跳雷场景被拦
- 与项目 Agent 协作原则一致（"破坏性动作必须明示"）

**Cons (做):**
- MVP scope 不上 hook
- confirm 提示过多会让 agent 工作流卡顿

**Context for future picker:** 候选机制：pre-rm wrapper 拦截 `rm -rf` 检查路径前缀；`git checkout` 前显示要还原的文件 + 等待 yes/no。Phase 4 hook 框架可挂在 PreToolUse 上。

**Depends on:** Phase 4 hook 框架启动

---
