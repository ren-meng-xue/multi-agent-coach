# Multi-Agent Cockpit MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `.ai/` 框架下补齐首跑必需的最小文件集，跑通一次 TASK-001 端到端，验证 5 角色 + status.json + cockpit 只读总览。

**Architecture:** 5 个 tmux window（cockpit / planner / backend / reviewer / tester）+ 单一同步契约（`.ai/tasks/*/status.json`）+ 一个 30 行 bash 读盘脚本。无 hook、无 bus、无自动派工。

**Tech Stack:** bash + jq + tmuxinator。所有 agent 文件用 markdown，状态文件用 JSON。不引入 Python/Node 运行时。

**Spec:** `docs/superpowers/specs/2026-05-29-multi-agent-cockpit-mvp-design.md`

**已知简化（相对 spec）：**
- spec §5.1 写"时间显示成 X 分钟前"。macOS BSD `date` 不支持含冒号时区的 ISO8601 解析（`+08:00`），为遵守 spec "纯 bash + jq" 约束，cockpit 显示改为 ISO 字符串的 `HH:MM` 切片。"X 分钟前" 留到复盘后决定是否引入 python3。

**Eng-review 后注入（2026-05-29，/plan-eng-review 14 个决定）：**

| # | 决定 | 落地任务 |
|---|---|---|
| D1 | 维持 scope（14 文件 / 13 task）| — |
| D2 | cockpit 加 schema 枚举 lint（state/owner 不合法显示 INVALID） | Task 8 |
| D3 | reviewer bootstrap 补 "顺便核对 README 与 .ai/ 实际目录一致性" | Task 12 Step 4 |
| D4 | cockpit `trunc()` 用 awk 按列位（wcwidth）替代 bash byte-slice | Task 8 |
| D5 | cockpit.sh 顶部加 ASCII 状态机 + 数据流注释 | Task 8 |
| D6 | 新建 `.ai/dashboard/tests/test_cockpit.sh` + 6 类 fixture（入仓） | Task 8b（新增）|
| D7 | Task 12 加 Step 4b 强制 reviewer 先走 changes_requested 退回路径 | Task 12 |
| D8 | jq 子进程数（8 per task）入复盘观察，不在 MVP 改 | Task 13 §3 |
| D10 (codex C1) | tester bootstrap 补"读 task.md（含验收单）" | Task 12 Step 5 |
| D11 (codex C4) | cockpit 加 ARTIFACTS 列，按 state 检产物（plan/review/handoff）存在 | Task 8 |
| D12 (codex C2) | cockpit 首部加 preflight：检 jq/git 存在，缺则提示 brew | Task 8 |
| D13 (codex C8) | reviewer bootstrap 明示 `git diff HEAD -- README.md` | Task 12 Step 4 |
| D14 (codex C6) | tmuxinator 写死路径保持现状，复盘加"是否社区化"项 | Task 13 §新增 |
| TODO-A1 (codex C5) | dirty tree pre-commit guard → TODOS.md | TODOS.md T-1 |
| TODO-A2 (codex C7) | 破坏性动作 confirm 门控 → TODOS.md | TODOS.md T-2 |

**Cross-model tension（已 ack，spec §11 决策保留）：**
- codex C3：TASK-001 是 README 改动却走 backend，"未验证真 backend 协作"——spec §11 明示"选真任务而非 dummy"，用户接受。
- codex C9：5 角色文件但只跑 4 角色——spec §11 明示"frontend.md 写但 window 不开，schema 一致性 > window 数节省"，用户接受。

**Footnote 修正：** plan header "5 角色" → 应为 "5 角色 schema（4 角色首跑参与）"。

---

## File Structure

按依赖顺序，本计划新建 / 修改如下：

| 文件 | 操作 | 责任 |
|---|---|---|
| `.ai/prompts/status-template.json` | Create | status.json 字段契约 |
| `.ai/prompts/handoff-template.md` | Create | handoff.md 段落契约 |
| `.ai/agents/planner.md` | Rewrite | planner 角色定义（8 段） |
| `.ai/agents/backend.md` | Create | backend 角色定义（8 段） |
| `.ai/agents/frontend.md` | Create | frontend 角色定义（8 段，首跑不参与） |
| `.ai/agents/reviewer.md` | Create | reviewer 角色定义（8 段） |
| `.ai/agents/tester.md` | Create | tester 角色定义（8 段） |
| `.ai/dashboard/cockpit.sh` | Create | 扫 status.json 打印总览（含 preflight / schema lint / artifacts check / awk trunc / ASCII 头）|
| `.ai/dashboard/tests/test_cockpit.sh` | Create | smoke test 入仓（D6）|
| `.ai/dashboard/tests/fixtures/*` | Create | 6 类测试 fixture（happy / 中文 / 损坏 / 缺字段 / 非法枚举 / 空目录）|
| `.tmuxinator/multi-agent.yml` | Modify | 重排 windows，cockpit 单 pane |
| `.ai/tasks/TASK-001/task.md` | Create | 首跑任务描述 |
| `.ai/tasks/TASK-001/status.json` | Create | 初始 TODO 状态 |
| `TODOS.md` | Create | 跨 PR 延后项（T-1 dirty tree / T-2 破坏性 confirm）|
| `docs/superpowers/specs/2026-05-29-multi-agent-cockpit-mvp-retro.md` | Create | 跑完后复盘 |

---

## Task 1: status.json 模板

**Files:**
- Create: `.ai/prompts/status-template.json`

- [ ] **Step 1: 写模板文件**

`.ai/prompts/status-template.json`:

```json
{
  "task_id": "TASK-XXX",
  "state": "TODO",
  "current_owner": "planner",
  "next_owner": null,
  "updated_at": "",
  "blockers": [],
  "notes": ""
}
```

- [ ] **Step 2: 验证 JSON 合法**

Run: `jq . .ai/prompts/status-template.json`
Expected: 输出格式化后的 JSON，无错误。

- [ ] **Step 3: 提交**

```bash
git add ai/prompts/status-template.json
git commit -m "feat(ai): add status.json schema template"
```

---

## Task 2: handoff.md 模板

**Files:**
- Create: `.ai/prompts/handoff-template.md`

- [ ] **Step 1: 写模板文件**

`.ai/prompts/handoff-template.md`:

```md
# Handoff Log

> 每个 agent 完成自己阶段后，**追加**一段到本文件末尾。不要覆盖前一段。

---

## <Agent Name> @ <ISO8601 with timezone, e.g. 2026-05-29T12:00:00+08:00>

### Completed
- ...

### Pending
- ...

### Risks
- ...

### Blockers
- ...

### Next Step
- 下一负责人：<planner|backend|frontend|reviewer|tester>
- 下一动作：...
```

- [ ] **Step 2: 提交**

```bash
git add ai/prompts/handoff-template.md
git commit -m "feat(ai): add handoff log template"
```

---

## Task 3: 重写 planner.md 为 8 段 schema

**Files:**
- Modify: `.ai/agents/planner.md`

- [ ] **Step 1: 覆盖写入 8 段版本**

`.ai/agents/planner.md`（**完全覆盖**当前 5 段内容）:

```md
# Planner

## Role

将用户需求转换为最小可执行任务，选择正确的 workflow，分派给执行 agent，并在任务终态归档。

## Responsibilities

- 解析用户需求，判定任务类型
- 选择对应 `.ai/workflows/<type>.yaml`
- 创建 `.ai/tasks/TASK-NNN/` 任务目录与初始 status.json
- 编写 `task.md`（任务描述）与 `plan.md`（执行计划）
- 在任务终态执行归档
- 不写任何业务代码

## Inputs

- 用户在 planner window 中输入的需求
- `CLAUDE.md` 顶层协议
- `.ai/workflows/*.yaml`
- `.ai/memory/decisions.md`（已批准的决议）
- 历史 `.ai/tasks/` 中相似任务（如有）

## Outputs

- `.ai/tasks/TASK-NNN/task.md`
- `.ai/tasks/TASK-NNN/plan.md`
- `.ai/tasks/TASK-NNN/checklist.md`
- `.ai/tasks/TASK-NNN/status.json`（初始化为 PLANNED，current_owner=planner，next_owner=<下一 agent>）
- `.ai/tasks/TASK-NNN/handoff.md`（追加 planner 段）

## Read Before Start

按顺序：

1. `CLAUDE.md`
2. `.ai/README.md`
3. `.ai/agents/planner.md`（本文件）
4. 选定的 `.ai/workflows/<type>.yaml`
5. `.ai/memory/decisions.md`
6. 用户提供的需求文本

## Workflow Responsibilities

| Workflow Step | Planner 负责内容 |
|---|---|
| planning | 写 task.md / plan.md / checklist.md，初始化 status.json，分派 next_owner |
| done | 检查所有产出物完整后归档（移动到 `.ai/tasks/archive/` 或打标记） |

## Rules

- 执行前必须思考：用户真正要什么 / 用哪个 Workflow / 最小范围是什么 / 哪些不做 / 需要哪些 Agent
- 禁止编写业务代码
- 禁止修改业务代码
- 禁止执行 review 或测试
- 禁止扩大任务范围
- 禁止跳过 workflow
- 必须更新 status.json 的 updated_at（含时区的 ISO8601）

## Handoff

```
planner (planning) → backend / frontend  (implementation)
reviewer (review changes_requested) → planner（如需调整 plan）
tester (testing passed) → planner (done)
```

完成后写 handoff.md 段，明确 next_owner。
```

- [ ] **Step 2: 验证 8 段结构存在**

Run: `grep -E "^## (Role|Responsibilities|Inputs|Outputs|Read Before Start|Workflow Responsibilities|Rules|Handoff)$" .ai/agents/planner.md | wc -l`
Expected: `8`

- [ ] **Step 3: 提交**

```bash
git add ai/agents/planner.md
git commit -m "refactor(ai): rewrite planner.md to 8-section schema"
```

---

## Task 4: 新写 backend.md

**Files:**
- Create: `.ai/agents/backend.md`

- [ ] **Step 1: 写文件**

`.ai/agents/backend.md`:

```md
# Backend

## Role

按 plan.md 实现后端代码、数据库变更、接口实现。

## Responsibilities

- 按 plan.md 实现指定模块
- 写或更新对应单元测试
- 必要时执行数据库迁移
- 完成后提交代码并改 status.json 为 REVIEW

## Inputs

- `.ai/tasks/TASK-NNN/task.md`
- `.ai/tasks/TASK-NNN/plan.md`
- `.ai/tasks/TASK-NNN/handoff.md`（planner 段）
- `.ai/memory/backend.md`（如存在）
- `.ai/memory/api.md`（如存在）
- `.ai/memory/database.md`（如存在）
- `.ai/memory/conventions.md`（如存在）

## Outputs

- 实现代码（按 plan.md 指定路径）
- 单元测试（如 plan 要求）
- `.ai/tasks/TASK-NNN/status.json`（state=REVIEW，current_owner=backend，next_owner=reviewer）
- `.ai/tasks/TASK-NNN/handoff.md`（追加 backend 段）

## Read Before Start

按顺序：

1. `CLAUDE.md`
2. `.ai/agents/backend.md`（本文件）
3. `.ai/tasks/TASK-NNN/task.md`
4. `.ai/tasks/TASK-NNN/plan.md`
5. `.ai/tasks/TASK-NNN/handoff.md`
6. 相关 memory（按需）

## Workflow Responsibilities

| Workflow Step | Backend 负责内容 |
|---|---|
| implementation | 按 plan 实现 + 写测试 + 改 status.json 为 REVIEW |
| blocked | 如卡住，state=BLOCKED + 写 blockers 数组 + 在 handoff.md 注明原因 |
| review (changes_requested) | 按 reviewer 意见修改，再次改 state=REVIEW |
| testing (failed) | 按 tester 意见修复，再次改 state=REVIEW |

## Rules

- 禁止扩大任务范围（plan.md 外的内容不动）
- 禁止修改 task.md / plan.md（如认为 plan 有问题，state=BLOCKED 让 planner 调整）
- 禁止执行 review（不在 review.md 里写"我自己看了 OK"）
- 禁止跑测试后自己宣布通过（tester 的活）
- 禁止写前端代码（frontend 的活）
- 每次改完代码必须更新 status.json 的 updated_at

## Handoff

```
backend (implementation done)  → reviewer
backend (blocked)              → planner（重新规划）
backend (review changes)       → reviewer（修改后）
```

完成后写 handoff.md 段，明确 next_owner。
```

- [ ] **Step 2: 验证 8 段结构**

Run: `grep -E "^## (Role|Responsibilities|Inputs|Outputs|Read Before Start|Workflow Responsibilities|Rules|Handoff)$" .ai/agents/backend.md | wc -l`
Expected: `8`

- [ ] **Step 3: 提交**

```bash
git add ai/agents/backend.md
git commit -m "feat(ai): add backend.md role definition"
```

---

## Task 5: 新写 frontend.md

**Files:**
- Create: `.ai/agents/frontend.md`

- [ ] **Step 1: 写文件**

`.ai/agents/frontend.md`:

```md
# Frontend

## Role

按 plan.md 实现 UI、页面、组件、前端状态管理。

## Responsibilities

- 按 plan.md 实现指定页面/组件
- 写或更新对应组件测试
- 处理前端状态管理
- 完成后改 status.json 为 REVIEW

## Inputs

- `.ai/tasks/TASK-NNN/task.md`
- `.ai/tasks/TASK-NNN/plan.md`
- `.ai/tasks/TASK-NNN/handoff.md`（planner 段）
- `.ai/memory/frontend.md`（如存在）
- `.ai/memory/api.md`（如存在）
- `.ai/memory/conventions.md`（如存在）

## Outputs

- 前端代码（按 plan.md 指定路径）
- 组件测试（如 plan 要求）
- `.ai/tasks/TASK-NNN/status.json`（state=REVIEW，current_owner=frontend，next_owner=reviewer）
- `.ai/tasks/TASK-NNN/handoff.md`（追加 frontend 段）

## Read Before Start

按顺序：

1. `CLAUDE.md`
2. `.ai/agents/frontend.md`（本文件）
3. `.ai/tasks/TASK-NNN/task.md`
4. `.ai/tasks/TASK-NNN/plan.md`
5. `.ai/tasks/TASK-NNN/handoff.md`
6. 相关 memory（按需）

## Workflow Responsibilities

| Workflow Step | Frontend 负责内容 |
|---|---|
| implementation | 按 plan 实现 + 写测试 + 改 status.json 为 REVIEW |
| blocked | 如卡住，state=BLOCKED + 写 blockers 数组 + 在 handoff.md 注明原因 |
| review (changes_requested) | 按 reviewer 意见修改，再次改 state=REVIEW |
| testing (failed) | 按 tester 意见修复，再次改 state=REVIEW |

## Rules

- 禁止扩大任务范围
- 禁止修改 task.md / plan.md
- 禁止执行 review
- 禁止自己宣布测试通过
- 禁止写后端代码（backend 的活）
- 每次改完代码必须更新 status.json 的 updated_at

## Handoff

```
frontend (implementation done)  → reviewer
frontend (blocked)              → planner（重新规划）
frontend (review changes)       → reviewer（修改后）
```

完成后写 handoff.md 段，明确 next_owner。
```

- [ ] **Step 2: 验证 8 段结构**

Run: `grep -E "^## (Role|Responsibilities|Inputs|Outputs|Read Before Start|Workflow Responsibilities|Rules|Handoff)$" .ai/agents/frontend.md | wc -l`
Expected: `8`

- [ ] **Step 3: 提交**

```bash
git add ai/agents/frontend.md
git commit -m "feat(ai): add frontend.md role definition"
```

---

## Task 6: 新写 reviewer.md

**Files:**
- Create: `.ai/agents/reviewer.md`

- [ ] **Step 1: 写文件**

`.ai/agents/reviewer.md`:

```md
# Reviewer

## Role

对实现成果做 code review，判定 approved 或 changes_requested，不亲自修改业务代码。

## Responsibilities

- 阅读 diff 与 plan.md / task.md，判断实现是否完成、是否对齐 plan
- 检查代码风格、命名、安全风险、显著的技术债
- 写 `review.md`，包含明确结论（approved / changes_requested）
- 改 status.json 到 TESTING（approved）或 IN_PROGRESS（changes_requested）

## Inputs

- `.ai/tasks/TASK-NNN/task.md`
- `.ai/tasks/TASK-NNN/plan.md`
- `.ai/tasks/TASK-NNN/handoff.md`（backend / frontend 段）
- 当前 git diff 或最近 commits 的产物
- `.ai/memory/conventions.md`（如存在）

## Outputs

- `.ai/tasks/TASK-NNN/review.md`（含 verdict: approved | changes_requested）
- `.ai/tasks/TASK-NNN/status.json`：
  - approved：state=TESTING，current_owner=reviewer，next_owner=tester
  - changes_requested：state=IN_PROGRESS，current_owner=reviewer，next_owner=backend 或 frontend
- `.ai/tasks/TASK-NNN/handoff.md`（追加 reviewer 段）

## Read Before Start

按顺序：

1. `CLAUDE.md`
2. `.ai/agents/reviewer.md`（本文件）
3. `.ai/tasks/TASK-NNN/task.md`
4. `.ai/tasks/TASK-NNN/plan.md`
5. `.ai/tasks/TASK-NNN/handoff.md`
6. 实际代码 diff

## Workflow Responsibilities

| Workflow Step | Reviewer 负责内容 |
|---|---|
| review | 写 review.md + 判定 approved/changes_requested + 改 status.json |

## Rules

- 禁止亲自修改业务代码
- 禁止跑测试（tester 的活）
- 禁止扩大任务范围
- review.md 必须给出明确 verdict（不允许"我觉得还可以"这种模糊话）
- changes_requested 必须列出具体待改项

## Handoff

```
reviewer (approved)          → tester
reviewer (changes_requested) → backend / frontend
```

完成后写 handoff.md 段，明确 next_owner。
```

- [ ] **Step 2: 验证 8 段结构**

Run: `grep -E "^## (Role|Responsibilities|Inputs|Outputs|Read Before Start|Workflow Responsibilities|Rules|Handoff)$" .ai/agents/reviewer.md | wc -l`
Expected: `8`

- [ ] **Step 3: 提交**

```bash
git add ai/agents/reviewer.md
git commit -m "feat(ai): add reviewer.md role definition"
```

---

## Task 7: 新写 tester.md

**Files:**
- Create: `.ai/agents/tester.md`

- [ ] **Step 1: 写文件**

`.ai/agents/tester.md`:

```md
# Tester

## Role

对已通过 review 的实现做验证与回归，判定 passed 或 failed，不亲自修复业务代码。

## Responsibilities

- 跑单元测试、集成测试、手动验收清单
- 检查 task.md 中"验收"段落是否全部满足
- 改 status.json 到 DONE（passed）或 IN_PROGRESS（failed）

## Inputs

- `.ai/tasks/TASK-NNN/task.md`（验收清单）
- `.ai/tasks/TASK-NNN/plan.md`
- `.ai/tasks/TASK-NNN/review.md`
- `.ai/tasks/TASK-NNN/handoff.md`
- 实际产物（代码 / 文档 / 渲染结果）
- `.ai/memory/testing.md`（如存在）

## Outputs

- 测试运行记录（可写入 handoff.md 的 Completed 段）
- `.ai/tasks/TASK-NNN/status.json`：
  - passed：state=DONE，current_owner=tester，next_owner=null
  - failed：state=IN_PROGRESS，current_owner=tester，next_owner=backend 或 frontend
- `.ai/tasks/TASK-NNN/handoff.md`（追加 tester 段）

## Read Before Start

按顺序：

1. `CLAUDE.md`
2. `.ai/agents/tester.md`（本文件）
3. `.ai/tasks/TASK-NNN/task.md`
4. `.ai/tasks/TASK-NNN/review.md`
5. `.ai/tasks/TASK-NNN/handoff.md`
6. 实际产物

## Workflow Responsibilities

| Workflow Step | Tester 负责内容 |
|---|---|
| testing | 跑测试 + 核对验收 + 改 status.json |

## Rules

- 禁止亲自修复业务代码
- 禁止扩大任务范围
- 禁止跳过 task.md 验收段任何一项
- failed 必须明确指出哪一项验收没过

## Handoff

```
tester (passed) → planner (done)
tester (failed) → backend / frontend
```

完成后写 handoff.md 段，明确 next_owner。
```

- [ ] **Step 2: 验证 8 段结构**

Run: `grep -E "^## (Role|Responsibilities|Inputs|Outputs|Read Before Start|Workflow Responsibilities|Rules|Handoff)$" .ai/agents/tester.md | wc -l`
Expected: `8`

- [ ] **Step 3: 提交**

```bash
git add ai/agents/tester.md
git commit -m "feat(ai): add tester.md role definition"
```

---

## Task 8: 写 cockpit.sh

**Files:**
- Create: `.ai/dashboard/cockpit.sh`
- Test: 临时 fixture（不入仓）

- [ ] **Step 1: 创建空脚本文件**

```bash
mkdir -p ai/dashboard
touch ai/dashboard/cockpit.sh
chmod +x ai/dashboard/cockpit.sh
```

- [ ] **Step 2: 先准备测试 fixture（不入仓）**

```bash
mkdir -p ai/tasks/TEST-001 ai/tasks/TEST-002 ai/tasks/TEST-BROKEN
cat > ai/tasks/TEST-001/status.json <<'EOF'
{
  "task_id": "TEST-001",
  "state": "IN_PROGRESS",
  "current_owner": "backend",
  "next_owner": "reviewer",
  "updated_at": "2026-05-29T10:30:00+08:00",
  "blockers": [],
  "notes": "first test task"
}
EOF
cat > ai/tasks/TEST-002/status.json <<'EOF'
{
  "task_id": "TEST-002",
  "state": "BLOCKED",
  "current_owner": "frontend",
  "next_owner": null,
  "updated_at": "2026-05-29T11:15:00+08:00",
  "blockers": ["waiting for design"],
  "notes": ""
}
EOF
echo "not valid json {{" > ai/tasks/TEST-BROKEN/status.json
```

- [ ] **Step 3: 跑空脚本，确认不爆**

Run: `bash .ai/dashboard/cockpit.sh`
Expected: 退出码 0（脚本为空）。

- [ ] **Step 4: 写完整脚本（含 D2 lint / D4 awk trunc / D5 ASCII 头 / D11 artifacts / D12 preflight）**

`.ai/dashboard/cockpit.sh`:

```bash
#!/usr/bin/env bash
# ai/dashboard/cockpit.sh
#
# === 状态机契约（spec §4.2 §4.3） ============================
#
#   planner  TODO ──► PLANNED ──► (owner=planner, next=backend)
#   backend  PLANNED ──► IN_PROGRESS ──► REVIEW ──► (next=reviewer)
#   reviewer REVIEW ──► TESTING (approved)        ──► (next=tester)
#                  └─► IN_PROGRESS (changes_req)  ──► (next=backend)
#   tester   TESTING ──► DONE (passed)            ──► (next=null)
#                  └─► IN_PROGRESS (failed)       ──► (next=backend)
#   any      ─────────► BLOCKED (blockers[] 写原因)
#
# === 数据流 =================================================
#
#   agent ──写──► ai/tasks/TASK-NNN/status.json
#                              │
#                              ▼
#                  watch -n 2 调用 cockpit.sh
#                              │
#                              ▼
#         扫描所有 task → 校验 → 打印表格 → 终端
#
# 纯 bash + jq。失败要静默（单文件损坏不要让全表崩）。

set -uo pipefail

# ───────────────────────────── preflight (D12) ─────────────────────────────
for tool in jq git; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "ERROR: 缺工具 '$tool'。请安装："
        echo "  brew install $tool   (macOS)"
        exit 127
    fi
done

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TASKS_DIR="$ROOT/.ai/tasks"

# 列宽（终端列位，不是字节）
W_TASK=10 ; W_STATE=10 ; W_OWNER=22 ; W_TIME=8
W_ARTIF=8 ; W_BLOCK=18 ; W_NOTES=28

# 合法枚举（D2 lint）
VALID_STATES="TODO PLANNED IN_PROGRESS REVIEW TESTING DONE BLOCKED"
VALID_OWNERS="planner backend frontend reviewer tester"

# ───────────────────────────── awk trunc (D4) ─────────────────────────────
# 按终端列位（wcwidth）截断：CJK 全角字符占 2 列、ASCII 占 1 列。
# 实现：awk 逐 char 累计 wc-width，超出则截，末加 ellipsis。
trunc() {
    local s="$1"; local n="$2"
    awk -v s="$s" -v n="$n" '
        BEGIN {
            # CJK Unified Ideographs / Hiragana / Katakana / Hangul / 全角符号 → 宽度 2
            # 其余 → 宽度 1
            out=""; w=0
            for (i=1; i<=length(s); ) {
                c = substr(s, i, 1)
                b = and(255, c+0)
                # 通过 char 字节数判断 UTF-8 多字节
                if (substr(s,i,1) ~ /[\x00-\x7F]/) { ch=substr(s,i,1); cw=1; bytes=1 }
                else if (substr(s,i,1) ~ /[\xC0-\xDF]/) { ch=substr(s,i,2); cw=1; bytes=2 }
                else if (substr(s,i,1) ~ /[\xE0-\xEF]/) { ch=substr(s,i,3); cw=2; bytes=3 }  # CJK 主区
                else { ch=substr(s,i,4); cw=2; bytes=4 }
                if (w + cw > n) { out = out "…"; break }
                out = out ch ; w += cw ; i += bytes
            }
            print out
            # 计算实际列位数，用 pad 补齐
            actual = (out ~ /…$/) ? n : w
            for (j=actual; j<n; j++) printf " "
        }
    ' | tr -d '\n'
    echo  # 单行结尾
}

# 列位左对齐打印
pad() { printf "%s " "$(trunc "$1" "$2")"; }

# ───────────────────────────── hhmm ─────────────────────────────
hhmm() {
    local iso="$1"
    if [ -z "$iso" ] || [ "${#iso}" -lt 16 ]; then
        printf '—'
    else
        printf '%s' "${iso:11:5}"
    fi
}

# ───────────────────────────── enum lint (D2) ─────────────────────────────
in_list() {
    local needle="$1"; shift
    for x in $@; do [ "$x" = "$needle" ] && return 0; done
    return 1
}

# ───────────────────────────── artifacts check (D11) ─────────────────────────────
# 按 state 检产物存在：PLANNED 后应有 plan.md，REVIEW 后应有 review.md，DONE 后应有 handoff.md
# 全在 → "ok"，缺 → "⚠ <list>"
check_artifacts() {
    local task_dir="$1"; local state="$2"
    local missing=""
    case "$state" in
        PLANNED|IN_PROGRESS|REVIEW|TESTING|DONE)
            [ -s "$task_dir/plan.md" ] || missing="${missing}plan,"
            ;;
    esac
    case "$state" in
        TESTING|DONE)
            [ -s "$task_dir/review.md" ] || missing="${missing}review,"
            ;;
    esac
    case "$state" in
        PLANNED|IN_PROGRESS|REVIEW|TESTING|DONE)
            [ -s "$task_dir/handoff.md" ] || missing="${missing}handoff,"
            ;;
    esac
    if [ -n "$missing" ]; then
        printf '⚠ %s' "${missing%,}"
    else
        printf 'ok'
    fi
}

# ───────────────────────────── 主流程 ─────────────────────────────
echo "════════════════════════════════════════════════════════════════════════════════════════════════════════════════"
printf "  Multi-Agent Cockpit                                                                          refreshed %s\n" "$(date +%H:%M:%S)"
echo "════════════════════════════════════════════════════════════════════════════════════════════════════════════════"

shopt -s nullglob
files=("$TASKS_DIR"/*/status.json)

if [ "${#files[@]}" -eq 0 ]; then
    echo "(no tasks yet)"
    exit 0
fi

# 表头
pad "TASK" $W_TASK ; pad "STATE" $W_STATE ; pad "OWNER → NEXT" $W_OWNER
pad "UPD" $W_TIME ; pad "ARTIF" $W_ARTIF ; pad "BLOCKERS" $W_BLOCK ; trunc "NOTES" $W_NOTES
pad "----" $W_TASK ; pad "-----" $W_STATE ; pad "------------" $W_OWNER
pad "---" $W_TIME ; pad "-----" $W_ARTIF ; pad "--------" $W_BLOCK ; trunc "-----" $W_NOTES

for f in "${files[@]}"; do
    task_dir=$(dirname "$f")
    task_basename=$(basename "$task_dir")
    if ! jq -e . "$f" >/dev/null 2>&1; then
        pad "$task_basename" $W_TASK ; pad "BROKEN" $W_STATE ; trunc "(invalid json)" 60
        continue
    fi

    task_id=$(jq -r '.task_id // "?"' "$f")
    state=$(jq -r '.state // "?"' "$f")
    cur=$(jq -r '.current_owner // "?"' "$f")
    nxt=$(jq -r '.next_owner // "—"' "$f")
    upd=$(jq -r '.updated_at // ""' "$f")
    blockers=$(jq -r '(.blockers // []) | join(",")' "$f")
    notes=$(jq -r '.notes // ""' "$f")

    # D2 lint：state 与 owner 不在合法枚举 → 用 INVALID 标记
    if ! in_list "$state" $VALID_STATES; then state="INVALID($state)"; fi
    if ! in_list "$cur" $VALID_OWNERS; then cur="INVALID($cur)"; fi
    [ "$nxt" = "—" ] || in_list "$nxt" $VALID_OWNERS || nxt="INVALID($nxt)"

    owner_pair="${cur} → ${nxt}"
    rel=$(hhmm "$upd")
    artif=$(check_artifacts "$task_dir" "$state")

    pad "$task_id" $W_TASK
    pad "$state" $W_STATE
    pad "$owner_pair" $W_OWNER
    pad "$rel" $W_TIME
    pad "$artif" $W_ARTIF
    pad "$blockers" $W_BLOCK
    trunc "$notes" $W_NOTES
done
```

> 注：`status-template.json` 是标准 JSON 不能内嵌注释，字段语义/枚举说明已嵌入 cockpit.sh 顶部注释（D5 决定）。

- [ ] **Step 5: 跑完整脚本，看 fixture 输出**

Run: `bash .ai/dashboard/cockpit.sh`
Expected: 输出包含 `TEST-001`、`TEST-002`、`TEST-BROKEN` 三行（D4 awk 按列位截断，CJK 不乱码）；`TEST-001` 状态 `IN_PROGRESS`、ARTIF 列显 `⚠ plan,handoff`（fixture 没有产物文件）；`TEST-002` notes 含中文不破列；`TEST-BROKEN` 行显 `BROKEN (invalid json)`；脚本退出码 0。如果 jq 缺则在 preflight 阶段就退出 127。

- [ ] **Step 6: 删 fixture，验证空集分支**

```bash
rm -rf ai/tasks/TEST-001 ai/tasks/TEST-002 ai/tasks/TEST-BROKEN
```

Run: `bash .ai/dashboard/cockpit.sh`
Expected: 输出含 `(no tasks yet)`，退出码 0。

- [ ] **Step 7: 提交**

```bash
git add ai/dashboard/cockpit.sh
git commit -m "feat(ai): add cockpit.sh status overview script

含 preflight (jq/git)、schema 枚举 lint、artifacts 一致性检、awk 按列位
截断（CJK 安全）、ASCII 状态机/数据流头注释。"
```

---

## Task 8b: cockpit.sh smoke test 入仓（D6）

**Files:**
- Create: `.ai/dashboard/tests/test_cockpit.sh`
- Create: `.ai/dashboard/tests/fixtures/*/status.json`（6 个 fixture 目录）
- Create: `.ai/dashboard/tests/expected/*.txt`（6 个期望输出）

> 目的：D2 lint / D4 awk trunc / D11 artifacts 是新增逻辑，按 skill IRON RULE 必须有可重跑的回归测试。Phase 4 hook 变动 cockpit 时无回归 = 隐藏 bug。

- [ ] **Step 1: 建目录**

```bash
mkdir -p ai/dashboard/tests/fixtures ai/dashboard/tests/expected
```

- [ ] **Step 2: 写 6 类 fixture**

每个 fixture 在 `.ai/dashboard/tests/fixtures/<name>/status.json`（外加可选 plan.md/review.md/handoff.md 触发 ARTIF 列）：

1. `happy-ascii`：state=IN_PROGRESS、ASCII notes、含 plan.md + handoff.md
2. `cjk-notes`：state=REVIEW、notes="首跑：验证多 agent 协作 + cockpit 链路"、含 plan.md + handoff.md
3. `broken-json`：内容 `not valid {{`
4. `missing-state`：合法 JSON 但无 `state` 字段
5. `bad-enum`：state="REIVEW"（拼错）
6. `done-no-review`：state=DONE 但缺 review.md（触发 ARTIF ⚠）

- [ ] **Step 3: 写 test_cockpit.sh**

`.ai/dashboard/tests/test_cockpit.sh`:

```bash
#!/usr/bin/env bash
# 给 cockpit.sh 跑 6 类 fixture，diff 输出 vs expected。
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COCKPIT="$SCRIPT_DIR/../cockpit.sh"
FIX="$SCRIPT_DIR/fixtures"
EXP="$SCRIPT_DIR/expected"

pass=0; fail=0
for fixture in "$FIX"/*/; do
    name=$(basename "$fixture")
    expected="$EXP/${name}.txt"
    [ -f "$expected" ] || { echo "SKIP $name (no expected)"; continue; }

    # 临时把 TASKS_DIR 指向单一 fixture 跑
    actual=$(TASKS_DIR="$FIX" "$COCKPIT" 2>&1 | grep -F "$name" || true)
    expected_content=$(cat "$expected")

    if [ "$actual" = "$expected_content" ]; then
        echo "✓ $name"
        pass=$((pass+1))
    else
        echo "✗ $name"
        diff <(echo "$actual") <(echo "$expected_content") | head -10
        fail=$((fail+1))
    fi
done

echo "---"
echo "PASS=$pass FAIL=$fail"
[ $fail -eq 0 ]
```

> 注：cockpit.sh 当前用固定 `ROOT/.ai/tasks` 作为扫描路径。若要让测试可注入路径，在 cockpit.sh 改一行：`TASKS_DIR="${TASKS_DIR:-$ROOT/.ai/tasks}"`。这是 1 行 patch，请在 Task 8 Step 4 落地时把硬路径改成 env-overridable 形式。

- [ ] **Step 4: 跑 smoke test**

```bash
chmod +x ai/dashboard/tests/test_cockpit.sh
bash ai/dashboard/tests/test_cockpit.sh
```

Expected: 6 个 fixture 全 ✓，退出码 0。

- [ ] **Step 5: 提交**

```bash
git add ai/dashboard/tests/
git commit -m "test(ai): add cockpit.sh smoke test with 6 fixtures (D6)"
```

---

## Task 9: 改 tmuxinator yaml

**Files:**
- Modify: `.tmuxinator/multi-agent.yml`

- [ ] **Step 1: 覆盖写入新版**

`.tmuxinator/multi-agent.yml`（**完全覆盖**当前内容）:

```yaml
name: multi-agent
root: ~/learn/AI项目/multi-agent-coach

windows:
  - cockpit:
      panes:
        - watch -n 2 'bash ai/dashboard/cockpit.sh'
  - planner:
      panes:
        - claude
  - backend:
      panes:
        - claude
  - reviewer:
      panes:
        - claude
  - tester:
      panes:
        - claude
```

- [ ] **Step 2: 验证 yaml 语法**

Run: `tmuxinator debug multi-agent 2>&1 | head -40`
Expected: 输出生成的 tmux 命令脚本，不报 YAML 解析错。看到 `new-window -t multi-agent:0 -n cockpit`、`:1 -n planner`、`:2 -n backend`、`:3 -n reviewer`、`:4 -n tester` 共 5 个 window。

- [ ] **Step 3: 提交**

```bash
git add .tmuxinator/multi-agent.yml
git commit -m "refactor(tmuxinator): drop scripts-old1 refs, simplify cockpit to single pane, swap frontend for tester window"
```

---

## Task 10: workspace 干跑（无任务）

> **手动验证步骤**——不可用脚本完全自动化。需要一个交互式终端会话。

**Files:** 无新增 / 修改

- [ ] **Step 1: 启动 workspace**

Run: `tmuxinator start multi-agent`
Expected: 进入 tmux session `multi-agent`。

- [ ] **Step 2: 检查 5 个 window 都在**

在 tmux 中按 `Ctrl-b w` 列窗口。
Expected: 看到 cockpit / planner / backend / reviewer / tester 5 个 window。

- [ ] **Step 3: 检查 cockpit 显示**

切到 cockpit window（`Ctrl-b 0`）。
Expected: 屏幕显示 `Multi-Agent Cockpit` 标题 + `(no tasks yet)`，每 2 秒刷新一次。

- [ ] **Step 4: 检查其他 4 个 window 启动了 claude**

依次切到 planner / backend / reviewer / tester（`Ctrl-b 1/2/3/4`）。
Expected: 每个 window 看到 claude code 启动界面。

- [ ] **Step 5: 停掉 session**

在任一 window 跑 `tmux kill-session -t multi-agent`。

- [ ] **Step 6（无需提交）**

本任务无文件改动；如果发现任何 window 配置问题，回到 Task 9 修复后重做本任务。

---

## Task 11: 建 TASK-001 初始文件

**Files:**
- Create: `.ai/tasks/TASK-001/task.md`
- Create: `.ai/tasks/TASK-001/status.json`

- [ ] **Step 1: 创建目录**

```bash
mkdir -p ai/tasks/TASK-001
```

- [ ] **Step 2: 写 task.md**

`.ai/tasks/TASK-001/task.md`:

```md
# TASK-001 给 README 加 5-Phase 当前状态说明

## 背景

multi-agent-coach 项目已经在 `.ai/` 下搭好 Agent OS 框架：

- `agents/` —— 5 个角色定义
- `memory/` —— 长期知识（多数为占位）
- `workflows/` —— 7 个流程定义
- `prompts/` —— 模板（status / handoff 已补，其余占位）
- `tasks/` —— 任务实例
- `dashboard/` —— cockpit.sh 总览脚本

项目演进按 5 个 Phase 走：

1. Workspace（tmux/tmuxinator）
2. Role System + Shared Memory
3. Workflow Automation
4. Hooks
5. Agent Bus / Dashboard

但 `README.md` 尚未反映这套框架的存在与当前推进状态。

## 目标

给 `README.md` 新增一段，说明 5 个 Phase 当前各自的完成度。

## 验收

- [ ] `README.md` 在合适位置新增"Agent OS 5-Phase 状态"段落
- [ ] 段落内容与 `.ai/` 实际目录状态一致（不夸大、不漏报）
- [ ] markdown 渲染无破（`grip README.md` 或 GitHub 预览正常）
- [ ] 不改动 `README.md` 既有段落的语义

## Workflow

`.ai/workflows/feature.yaml`
```

- [ ] **Step 3: 写 status.json**

`.ai/tasks/TASK-001/status.json`:

```json
{
  "task_id": "TASK-001",
  "state": "TODO",
  "current_owner": "planner",
  "next_owner": null,
  "updated_at": "2026-05-29T18:00:00+08:00",
  "blockers": [],
  "notes": "首跑：验证多 agent 协作 + cockpit 链路"
}
```

> 注：`updated_at` 写当前时间即可（粗略）。实施者请把 `18:00:00` 改成实际操作时间，时区保持 `+08:00`。

- [ ] **Step 4: 跑 cockpit 验证 TASK-001 上桌**

```bash
bash ai/dashboard/cockpit.sh
```

Expected: 输出含一行 `TASK-001 / TODO / planner → — / 18:00 / / 首跑：验证...`。

- [ ] **Step 5: 提交**

```bash
git add ai/tasks/TASK-001/
git commit -m "feat(tasks): seed TASK-001 (add 5-phase status to README)"
```

---

## Task 12: 干跑 TASK-001（4 角色）

> **手动验证步骤**——核心目的是观察"哪些步骤必须人介入"，把发现写进 Task 13 复盘。

**Files:** 跑的过程中 4 个 agent 会创建：
- `.ai/tasks/TASK-001/plan.md`（planner）
- `.ai/tasks/TASK-001/checklist.md`（planner）
- `.ai/tasks/TASK-001/handoff.md`（4 段，依次追加）
- `.ai/tasks/TASK-001/review.md`（reviewer）
- `README.md`（backend 修改）

- [ ] **Step 1: 启动 workspace**

```bash
tmuxinator start multi-agent
```

- [ ] **Step 2: 在 planner window 启动并粘 bootstrap**

切到 planner window。在 claude 提示符下粘：

```
你是 planner。读 CLAUDE.md → .ai/README.md → .ai/agents/planner.md →
.ai/workflows/feature.yaml → .ai/tasks/TASK-001/task.md，进入 planning 阶段：
写 .ai/tasks/TASK-001/plan.md 和 checklist.md，
改 status.json 为 PLANNED / next_owner=backend，追加 handoff.md。
```

等待 planner 完成。

Expected: 切回 cockpit window，看到 TASK-001 状态变为 `PLANNED / planner → backend`，`updated_at` 变成最新时间。`.ai/tasks/TASK-001/plan.md`、`checklist.md`、`handoff.md` 已创建。

- [ ] **Step 3: 在 backend window 启动并粘 bootstrap**

切到 backend window。在 claude 提示符下粘：

```
你是 backend。读 CLAUDE.md → .ai/agents/backend.md →
.ai/tasks/TASK-001/{task.md, plan.md, handoff.md}，进入 implementation 阶段：
按 plan.md 改 README.md，改 status.json 为 REVIEW / next_owner=reviewer，追加 handoff.md。
```

等待 backend 完成。

Expected: cockpit 显示 `REVIEW / backend → reviewer`。`README.md` 已含新段落。`handoff.md` 已追加 backend 段。

- [ ] **Step 4: 在 reviewer window 启动并粘 bootstrap（含 D3 + D13）**

切到 reviewer window。在 claude 提示符下粘：

```
你是 reviewer。读 CLAUDE.md → .ai/agents/reviewer.md →
.ai/tasks/TASK-001/{plan.md, handoff.md} + `git diff HEAD -- README.md`，
进入 review 阶段：
1. 看 README.md 改动是否对齐 plan.md；
2. 顺便核对 README 段落与 `.ai/` 实际目录状态是否一致（用 `ls .ai/`、`find .ai/agents .ai/workflows -type f` 核 5 个 Phase 实际完成度）；
3. 写 review.md，必须给 verdict（approved / changes_requested）；
4. 改 status.json 为 TESTING / next_owner=tester（或 IN_PROGRESS 退回 backend），追加 handoff.md。
```

等待 reviewer 完成。

Expected: cockpit 显示 `TESTING / reviewer → tester`（approved 路径）或 `IN_PROGRESS / reviewer → backend`（changes_requested 路径）。`review.md` 已创建。

- [ ] **Step 4b: 强制走一次 changes_requested 退回路径（D7）**

> 目的：spec §2 Q3 hook 决策需要 changes_requested 路径的真实数据。如果 Step 4 reviewer 自然 approved，人为请 reviewer 重做一次按 changes_requested 退回（哪怕只是吹毛求疵 "请补一句 X"）。

切回 reviewer window，粘：

```
请把 review verdict 改为 changes_requested，理由可以是任何小修
（如：希望 5-Phase 列表的某行末尾加一个标点）。改 review.md 末加 verdict_revised 段、
改 status.json 为 IN_PROGRESS / next_owner=backend，追加 handoff.md。
```

切回 backend window，粘：

```
你是 backend。reviewer 给了 changes_requested。读 .ai/tasks/TASK-001/review.md
里的具体待改项，按改 README.md，改 status.json 为 REVIEW / next_owner=reviewer，
追加 handoff.md。
```

再切回 reviewer window，粘：

```
backend 已修改，请重审。读 .ai/tasks/TASK-001/{review.md, handoff.md} 与
`git diff HEAD -- README.md`，给 approved，改 status.json 为 TESTING / next_owner=tester，
追加 handoff.md。
```

Expected: cockpit 路径变迁可见 `REVIEW → IN_PROGRESS → REVIEW → TESTING`，handoff.md 含 6 段以上。

- [ ] **Step 5: 在 tester window 启动并粘 bootstrap（含 D10）**

切到 tester window。在 claude 提示符下粘：

```
你是 tester。读 CLAUDE.md → .ai/agents/tester.md →
.ai/tasks/TASK-001/{task.md, plan.md, review.md, handoff.md} + README.md，进入 testing 阶段：
1. 逐项核 task.md "验收" 段的 4 项是否全中（包括 "与 .ai/ 实际状态一致"）；
2. 渲染检查（grip 或 GitHub 预览）；
3. 链接检查；
4. 改 status.json 为 DONE / next_owner=null，追加 handoff.md。
```

等待 tester 完成。

Expected: cockpit 显示 `DONE / tester → —`。tester handoff.md 段含 4 项验收逐项打钩。

- [ ] **Step 6: 验收清单核对**

逐项打钩：

- [ ] cockpit 启动到 DONE 全程没崩
- [ ] cockpit 每 2 秒刷新一次正常
- [ ] `state` 最终 = `DONE`
- [ ] `current_owner` 最终 = `tester`
- [ ] `next_owner` 最终 = `null`
- [ ] `.ai/tasks/TASK-001/handoff.md` 至少包含 4 段（planner / backend / reviewer / tester），每段含 5 个小节
- [ ] `README.md` 已新增"5-Phase 状态"段落，内容与 `.ai/` 一致
- [ ] `cockpit.sh` 在过程中故意 `echo "broken" > .ai/tasks/TASK-001/status.json` 一次（然后立刻 git checkout 还原）能看到 `BROKEN (invalid json)` 行不崩

- [ ] **Step 7: 提交跑出来的产物**

```bash
git add ai/tasks/TASK-001/ README.md
git commit -m "feat(tasks): TASK-001 done — README now reflects 5-phase status"
```

- [ ] **Step 8: 停 session**

```bash
tmux kill-session -t multi-agent
```

---

## Task 13: 写复盘 spec

**Files:**
- Create: `docs/superpowers/specs/2026-05-29-multi-agent-cockpit-mvp-retro.md`

- [ ] **Step 1: 写复盘文档**

`docs/superpowers/specs/2026-05-29-multi-agent-cockpit-mvp-retro.md`:

```md
# Multi-Agent Cockpit MVP 复盘

**Date:** 2026-05-29
**Spec:** docs/superpowers/specs/2026-05-29-multi-agent-cockpit-mvp-design.md
**Plan:** docs/superpowers/plans/2026-05-29-multi-agent-cockpit-mvp.md

---

## 1. 跑通了吗

- [ ] 是 / 否
- 终态 status.json：
- 总耗时（启 session → DONE）：

## 2. 4 次"手动切窗口 + 粘 bootstrap" 哪几次值得 hook 化

按"切换次数 / 等待时长 / 信息冗余"打分（1-5），分高的是优先 hook 候选：

| 切换点 | 切换次数 | 等待时长 | 信息冗余 | hook 候选优先级 |
|---|---|---|---|---|
| planner → backend | | | | |
| backend → reviewer | | | | |
| reviewer → tester | | | | |
| reviewer → backend（如发生 changes_requested） | | | | |

## 3. cockpit 哪几列信息不够 + 性能与可移植性观察

- [ ] 需要看 git diff 行数
- [ ] 需要看最近修改文件
- [ ] 需要看每段子任务进度
- [ ] 需要看耗时（X 分钟前，而非 HH:MM）
- [ ] 其他：

### 3a. 性能 (D8 决定入复盘观察)

- cockpit.sh 单次 refresh 起的 jq 子进程数（N task × 8 调用）：
- cockpit.sh 单次 refresh 平均耗时（time bash .ai/dashboard/cockpit.sh）：
- watch -n 2 持续运行 5 分钟后，cockpit.sh 累计 CPU：
- 是否需要把 jq 7 次调用合并为 1 次 `jq @tsv`（O(N)→O(1) per task）：

### 3b. 可移植性 (D14 决定入复盘观察)

- `.tmuxinator/multi-agent.yml` 当前 `root: ~/learn/AI项目/multi-agent-coach` 写死本机路径。是否需要社区化 / 多机启动 / CI 运行？
  - [ ] 是 → 改为 ENV 变量 / 动态生成 yaml
  - [ ] 否 → 维持现状

## 4. status.json schema 哪些字段不够 / 哪些没用上

| 字段 | 实际被读次数 | 实际被写次数 | 评价 |
|---|---|---|---|
| task_id | | | |
| state | | | |
| current_owner | | | |
| next_owner | | | |
| updated_at | | | |
| blockers | | | |
| notes | | | |

需要新增字段：
-

## 5. `.ai/workflows/feature.yaml` 在实际跑里被遵守了几条 / 被违反了几条

- 实际状态流转：
- 是否出现 dynamic_owners 场景：
- 是否触发 changes_requested 回退：
- 与 yaml 定义的差异：

## 6. 剩下没补的下一批先补哪些

下批候选（spec §1.2 列）：

- [ ] `.ai/prompts/task-template.md`
- [ ] `.ai/prompts/plan-template.md`
- [ ] `.ai/prompts/review-template.md`
- [ ] `.ai/memory/project.md`
- [ ] `.ai/memory/architecture.md`
- [ ] `.ai/memory/conventions.md`
- [ ] `.ai/memory/{backend,frontend,api,database,testing,deployment}.md`

按本次经验优先排序：
1.
2.
3.

## 7. Phase 4 hook 建议清单

基于第 2 节排序，下一阶段挂哪几个 hook：

1.
2.
3.

## 8. 其他观察
```

- [ ] **Step 2: 实际填表**

> 上面 Task 12 跑完后实施者按真实情况填空。本步骤"完成"的判定 = 7 个章节都不为空白模板。

- [ ] **Step 3: 提交**

```bash
git add docs/superpowers/specs/2026-05-29-multi-agent-cockpit-mvp-retro.md
git commit -m "docs: cockpit MVP retro — observations for Phase 4 scope"
```

---

## Self-Review 结果

**Spec coverage：** spec §1.2 列出的本次必补 6 个文件（4 角色 + 2 模板）由 Task 1/2/3/4/5/6/7 覆盖；§5.1 cockpit.sh 由 Task 8 覆盖；§5.2 tmuxinator 由 Task 9 覆盖；§5.3 TASK-001 文件由 Task 11 覆盖；§6 数据流由 Task 12 验证；§9 复盘由 Task 13 产出。spec §5.8 bootstrap 4 句已嵌入 Task 12 各步骤。

**Placeholder scan：** 无 TBD / TODO；4 个角色文件全部给出完整内容；cockpit.sh 全脚本展开；bootstrap 句子完整；复盘 spec 给出可填模板（填空动作放在 Task 13 step 2 而非"留空"）。

**Type consistency：** 所有 status.json 字段名一致（`task_id` / `state` / `current_owner` / `next_owner` / `updated_at` / `blockers` / `notes`）；所有 agent 文件 8 段标题一致；handoff.md 5 小节命名 (`Completed` / `Pending` / `Risks` / `Blockers` / `Next Step`) 在模板和 Task 12 验收清单中一致。

**已知偏差：** spec §5.1 写"X 分钟前"，plan Task 8 实现为 `HH:MM` 切片；偏差已在 plan header 顶部"已知简化"注明，复盘 Task 13 §3 留了观察条目。

---

## Implementation Tasks（eng-review 衍生）

> 本次 `/plan-eng-review` 的 14 个决定（D2-D17）已直接 inline 编辑到上方各 Task。下表是 audit-trail 索引。

- [ ] **T1 (P1, human: ~10min / CC: ~3min)** — cockpit.sh — schema 枚举 lint
  - Surfaced by: D2 (Architecture)
  - Files: `.ai/dashboard/cockpit.sh`
  - Verify: 跑 fixture `bad-enum` 看到 `INVALID(REIVEW)` 行
- [ ] **T2 (P1, human: ~2min / CC: ~1min)** — reviewer bootstrap — 事实核对
  - Surfaced by: D3 (Architecture)
  - Files: Task 12 Step 4 bootstrap 句
  - Verify: review.md 出现 ".ai/ 实际目录核对" 段
- [ ] **T3 (P1, human: ~15min / CC: ~3min)** — cockpit.sh — awk 列位 trunc
  - Surfaced by: D4 (Code Quality)
  - Files: `.ai/dashboard/cockpit.sh` (trunc 函数)
  - Verify: fixture `cjk-notes` 不乱码不错位
- [ ] **T4 (P2, human: ~10min / CC: ~3min)** — cockpit.sh — ASCII 头注释
  - Surfaced by: D5 (Code Quality)
  - Files: `.ai/dashboard/cockpit.sh`
  - Verify: `head -20 cockpit.sh` 看到状态机 + 数据流图
- [ ] **T5 (P1, human: ~30min / CC: ~5min)** — cockpit smoke test 入仓
  - Surfaced by: D6 (Test) — REGRESSION rule
  - Files: `.ai/dashboard/tests/test_cockpit.sh` + 6 fixtures + 6 expected
  - Verify: `bash test_cockpit.sh` 6 ✓ 退出 0
- [ ] **T6 (P2, human: ~5min / CC: ~2min)** — Task 12 — 强制 changes_requested
  - Surfaced by: D7 (Test)
  - Files: plan Task 12 Step 4b（已添加）
  - Verify: 首跑 handoff.md ≥ 6 段
- [ ] **T7 (P1, human: ~1min / CC: ~30s)** — tester bootstrap — 读 task.md
  - Surfaced by: D10 / codex C1 (Outside Voice)
  - Files: Task 12 Step 5 bootstrap 句
  - Verify: tester handoff.md 含 4 项验收逐项打钩
- [ ] **T8 (P1, human: ~15min / CC: ~5min)** — cockpit.sh — ARTIFACTS 列
  - Surfaced by: D11 / codex C4 (Outside Voice)
  - Files: `.ai/dashboard/cockpit.sh`
  - Verify: fixture `done-no-review` 显 `⚠ review`
- [ ] **T9 (P2, human: ~5min / CC: ~2min)** — cockpit.sh — preflight
  - Surfaced by: D12 / codex C2 (Outside Voice)
  - Files: `.ai/dashboard/cockpit.sh` (顶部)
  - Verify: `PATH=/ bash cockpit.sh` → 报 "缺工具 'jq'" 退出 127
- [ ] **T10 (P1, human: ~1min / CC: ~30s)** — reviewer bootstrap — diff 基准
  - Surfaced by: D13 / codex C8 (Outside Voice)
  - Files: Task 12 Step 4 bootstrap 句
  - Verify: review.md 引用 `git diff HEAD -- README.md`
- [ ] **T11 (P3, human: ~5min)** — 复盘加 D8/D14 观察项
  - Surfaced by: D8 / D14 (Performance / Code Quality)
  - Files: Task 13 §3a §3b（已添加）
- [ ] **T12 (P3, human: ~10min)** — TODOS.md 创建
  - Surfaced by: D15 / D16 (Outside Voice C5 / C7)
  - Files: `TODOS.md`（已创建）

_No new tasks from Performance section（D8 入复盘）._

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | issues_found | 9 findings, 5 promoted to plan revisions (D10-D14), 2 to TODOS.md (T-1/T-2), 2 ack as spec §11 decisions |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | issues_open | 14 decisions (D1-D17 excl. D9 meta), 0 critical gaps, 0 unresolved |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**CODEX:** 9 findings 已全部处理：C1/C4 promoted to P1 plan revisions (D10/D11)，C2/C8 to P2 plan revisions (D12/D13)，C6 ack 入复盘 (D14)，C5/C7 to TODOS.md (T-1/T-2)，C3/C9 spec §11 已决策保留。
**CROSS-MODEL:** Claude review 8 + codex 5 promoted overlap：D2 (lint) 与 codex 隐示一致；D4 (CJK) codex 未提但 Claude 抓到；codex 抓到的 6 个新 finding (C1/C2/C4/C5/C6/C7/C8) Claude 单独 review 未覆盖。
**UNRESOLVED:** 0
**VERDICT:** ENG CLEARED — 14 decisions absorbed, plan revisions inline, ready to implement after sequencing T1-T12.
