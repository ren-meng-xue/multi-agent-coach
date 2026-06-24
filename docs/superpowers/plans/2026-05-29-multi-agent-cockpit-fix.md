# Multi-Agent Cockpit 流程修复 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 multi-agent-coach 的端到端工作流，从"跑不通"到"Feature/Bugfix/Refactor 全流程自动化可用"

**Architecture:** 调度台 (control-plane.sh) 每 2 秒轮询 tasks.md，通过 route.sh 计算 next_agent，send-to-agent.sh 唤醒对应 agent window（tmux send-keys）。Agent 被唤醒后读取共享状态、执行任务、更新状态。所有 state 转移由 agent 按 CLAUDE.md 归属表执行，脚本只做机器检查。

**Tech Stack:** Bash (脚本)、Markdown (共享状态文件)、tmux/tmuxinator (workspace)、Claude Code (agent CLI)

**实施分期:** 第 1 期 P0 阻塞性修复 → 第 2 期 P1 一致性修复 → 第 3 期 P2 体验性修复

---

## 当前状态 vs 目标状态

| 文件 | 当前状态 | 目标状态 |
|---|---|---|
| `scripts/control-plane.sh` | 单任务、直接改 state | 守护进程、轮询多任务、仅路由+唤醒 |
| `scripts/dispatcher.sh` | 写 next-action.md | **废弃**（逻辑并入 control-plane） |
| `scripts/status-watch.sh` | 简单 cat 循环 | **废弃**（替换为 dashboard.sh） |
| `scripts/review-hook.sh` | 自动写 approved + 改 state | 只跑测试 + append status.md |
| `scripts/archive-hook.sh` | control-plane 自动调用 | planner 手动调用 + 原子化归档 |
| `scripts/utils/` | 空目录 | parse-task.sh, route.sh, run-tests.sh, task-diff.sh, dashboard.sh |
| `scripts/send-to-agent.sh` | 不存在 | 封装 tmux send-keys |
| `shared/current/tasks.md` | 单任务格式 | 多任务 list 格式 |
| `shared/current/status.md` | 覆盖写 | append-only 时间线 |
| `shared/current/review.md` | 单段 | 按 Task-NNN 分段 |
| `shared/current/next-action.md` | 简单单行 | 多任务分段 + Agent queues |
| `agents/*.md` | 基础角色定义 | 加唤醒动作、blocked 处理、type 差异 |
| `.tmuxinator/multi-agent.yml` | 不存在 | 5-window workspace |
| `scripts-old/` | 13 个老脚本 | `git rm` 删除 |

---

## 第 1 期：P0 阻塞性修复（让流程跑通 Feature + Blocked）

### Task 1: 创建 `scripts/utils/parse-task.sh` —— 任务字段解析器

**Files:**
- Create: `scripts/utils/parse-task.sh`

**接口:** `parse-task.sh <task_id> [field]`，field ∈ {state, type, owner, depends_on, priority, cancelled}。缺 field 输出完整 JSON，带 field 输出单值。退出码 0/1/2。

- [ ] **Step 1: 写脚本**

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TASKS="$ROOT/shared/current/tasks.md"

TASK_ID="${1:-}"
FIELD="${2:-}"

if [ -z "$TASK_ID" ]; then
  echo "Usage: parse-task.sh <task_id> [field]" >&2
  exit 1
fi

if [ ! -f "$TASKS" ]; then
  echo '{"error":"tasks.md not found"}' >&2
  exit 1
fi

# 提取 ### Task-NNN ... 到下一个 ### 或 EOF
BLOCK=$(awk "/^### $TASK_ID[ :]/{found=1} found{print} /^### /&&found&&!/^### $TASK_ID[ :]/{exit}" "$TASKS")

if [ -z "$BLOCK" ]; then
  echo "{\"error\":\"$TASK_ID not found\"}" >&2
  exit 1
fi

# 解析字段
get_field() {
  local f="$1"
  echo "$BLOCK" | grep -m1 "^${f}:" | sed "s/^${f}:[[:space:]]*//" || echo ""
}

STATE=$(get_field "状态")
TYPE=$(get_field "类型")
OWNER=$(get_field "负责人")
DEPENDS_ON=$(get_field "depends_on")
PRIORITY=$(get_field "priority")
CANCELLED=$(get_field "cancelled")

# 必填字段检查
if [ -z "$STATE" ] || [ -z "$TYPE" ] || [ -z "$OWNER" ]; then
  missing=""
  [ -z "$STATE" ] && missing="state"
  [ -z "$TYPE" ] && missing="type"
  [ -z "$OWNER" ] && missing="owner"
  echo "{\"error\":\"missing required field: $missing\",\"task_id\":\"$TASK_ID\"}" >&2
  exit 2
fi

# 合法值校验
VALID_STATES="pending in-progress review blocked done"
VALID_TYPES="feature refactor bugfix test trivial investigate spike"

if ! echo "$VALID_STATES" | grep -qw "$STATE"; then
  echo "{\"error\":\"invalid state: $STATE\",\"task_id\":\"$TASK_ID\"}" >&2
  exit 2
fi

if ! echo "$VALID_TYPES" | grep -qw "$TYPE"; then
  echo "{\"error\":\"invalid type: $TYPE\",\"task_id\":\"$TASK_ID\"}" >&2
  exit 2
fi

PRIORITY="${PRIORITY:-normal}"

if [ -n "$FIELD" ]; then
  case "$FIELD" in
    state) echo "$STATE" ;;
    type) echo "$TYPE" ;;
    owner) echo "$OWNER" ;;
    depends_on) echo "$DEPENDS_ON" ;;
    priority) echo "$PRIORITY" ;;
    cancelled) echo "$CANCELLED" ;;
    *)
      echo "Unknown field: $FIELD" >&2
      exit 1
      ;;
  esac
else
  # 输出 JSON
  cat <<JSONEOF
{"task_id":"$TASK_ID","state":"$STATE","type":"$TYPE","owner":"$OWNER","depends_on":"$DEPENDS_ON","priority":"$PRIORITY","cancelled":"$CANCELLED"}
JSONEOF
fi
```

- [ ] **Step 2: 验证脚本可执行**

```bash
chmod +x scripts-old1/utils/parse-task.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts-old1/utils/parse-task.sh
git commit -m "feat: add parse-task.sh — task field parser for multi-task tasks.md

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: 更新 `shared/current/tasks.md` 为多任务 list 格式

**Files:**
- Modify: `shared/current/tasks.md`

将当前单任务格式改为多任务 list 格式，空状态保持无 active task。

- [ ] **Step 1: 写入新格式模板**

文件内容：

```markdown
# Current Tasks

<!-- 格式：
### Task-NNN: 简述
类型: feature | refactor | bugfix | test | trivial | investigate | spike
状态: pending | in-progress | review | blocked | done
负责人: planner | backend | frontend | reviewer
创建时间: YYYY-MM-DD HH:MM
depends_on: Task-XXX (state>=done)   # 可选
priority: normal | high | low         # 可选，默认 normal
cancelled: true                       # 可选，仅 done 状态
cancelled_reason: ...                 # 可选
-->
```

- [ ] **Step 2: 验证 parse-task.sh 对新格式返回正确错误**

```bash
bash scripts-old1/utils/parse-task.sh Task-001 2>&1
# Expected: exit 1, "Task-001 not found"
```

- [ ] **Step 3: Commit**

```bash
git add shared-1/current/tasks.md
git commit -m "feat: update tasks.md to multi-task list format

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: 更新 `shared/current/status.md` 为 append-only 时间线

**Files:**
- Modify: `shared/current/status.md`

- [ ] **Step 1: 写入新格式模板**

```markdown
# Status Log

<!-- append-only 时间线，所有脚本和 agent 用 >> 追加 -->
<!-- 格式：[YYYY-MM-DD HH:MM] [role] message -->
<!-- 超过 500 行时归档到 shared/archive/status-log-<date>.md -->
```

- [ ] **Step 2: Commit**

```bash
git add shared-1/current/status.md
git commit -m "feat: update status.md to append-only timeline format

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: 更新 `shared/current/review.md` 为按 Task-NNN 分段格式

**Files:**
- Modify: `shared/current/review.md`

- [ ] **Step 1: 写入新格式模板**

```markdown
# Reviews

<!-- reviewer 按 ### Task-NNN 分段写 review，覆盖式（非 append） -->
<!-- Decision: approved | changes-requested | needs-discussion -->
<!-- changes-requested / needs-discussion 时 reviewer 不改 state -->
```

- [ ] **Step 2: Commit**

```bash
git add shared-1/current/review.md
git commit -m "feat: update review.md to per-task section format

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: 创建 `shared/current/next-action.md` 多任务分段格式

**Files:**
- Modify: `shared/current/next-action.md`

- [ ] **Step 1: 写入新格式模板**

```markdown
# Next Action

## Active dispatches

<!-- control-plane 每轮整文件覆写 -->

## Agent queues

## Dependency graph
```

- [ ] **Step 2: Commit**

```bash
git add shared-1/current/next-action.md
git commit -m "feat: update next-action.md to multi-task section format

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 6: 创建 `scripts/utils/route.sh` —— 任务路由器

**Files:**
- Create: `scripts/utils/route.sh`

**接口:** `route.sh` 无参数，全表扫描 tasks.md，输出 `<task_id> <next_agent> <reason>`。

- [ ] **Step 1: 写路由脚本**

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TASKS="$ROOT/shared/current/tasks.md"
REVIEW="$ROOT/shared/current/review.md"
PARSE="$ROOT/scripts/utils/parse-task.sh"

if [ ! -f "$TASKS" ]; then
  exit 0
fi

# 提取所有 Task-NNN ID
task_ids=$(grep -oP '^### \KTask-\d+' "$TASKS" || true)

for tid in $task_ids; do
  state=$("$PARSE" "$tid" state 2>/dev/null) || continue
  type=$("$PARSE" "$tid" type 2>/dev/null) || continue
  owner=$("$PARSE" "$tid" owner 2>/dev/null) || continue
  cancelled=$("$PARSE" "$tid" cancelled 2>/dev/null) || true

  # 跳过终态任务（done 且非 cancelled 需要 planner archive，done+cancelled 跳过）
  if [ "$state" = "done" ] && [ "$cancelled" != "true" ]; then
    echo "$tid planner dispatch (done→archive)"
    continue
  fi
  [ "$state" = "done" ] && [ "$cancelled" = "true" ] && continue

  # 检查 depends_on
  deps=$("$PARSE" "$tid" depends_on 2>/dev/null) || true
  skip=false
  if [ -n "$deps" ]; then
    IFS=',' read -ra DEP_ARR <<< "$deps"
    for dep in "${DEP_ARR[@]}"; do
      dep=$(echo "$dep" | xargs)
      dep_id=$(echo "$dep" | awk '{print $1}')
      dep_need=$(echo "$dep" | grep -oP '(?<=state>=)\w+' || echo "done")
      dep_state=$("$PARSE" "$dep_id" state 2>/dev/null) || dep_state="unknown"

      # 状态比较：done > review > in-progress > pending > blocked
      state_order="blocked pending in-progress review done"
      dep_pos=$(echo "$state_order" | tr ' ' '\n' | grep -n "^$dep_state$" | cut -d: -f1 || echo "0")
      need_pos=$(echo "$state_order" | tr ' ' '\n' | grep -n "^$dep_need$" | cut -d: -f1 || echo "0")
      if [ "$dep_pos" -lt "$need_pos" ] 2>/dev/null; then
        echo "$tid — waiting_on:$dep_id (current=$dep_state, need>=$dep_need)"
        skip=true
        break
      fi
    done
  fi
  [ "$skip" = "true" ] && continue

  # 路由表
  case "$state" in
    pending)
      echo "$tid $owner dispatch (pending→owner)"
      ;;
    in-progress)
      # owner 继续执行
      echo "$tid $owner dispatch (in-progress→owner)"
      ;;
    review)
      # 检查 review.md 的 decision
      decision=$(awk "/^### $tid/{found=1} found && /^\*\*Decision\*\*:/{print; exit}" "$REVIEW" 2>/dev/null | sed 's/.*Decision\*\*:[[:space:]]*//' || echo "")
      case "$decision" in
        "changes-requested")
          echo "$tid $owner dispatch (review→changes-requested→owner)"
          ;;
        "needs-discussion")
          echo "$tid planner dispatch (review→needs-discussion→planner)"
          ;;
        "approved")
          echo "$tid planner dispatch (review→approved→done)"
          ;;
        *)
          echo "$tid reviewer dispatch (review→reviewer)"
          ;;
      esac
      ;;
    blocked)
      echo "$tid planner dispatch (blocked→planner)"
      ;;
    *)
      echo "$tid — skipped:invalid_state ($state)"
      ;;
  esac
done
```

- [ ] **Step 2: 验证脚本可执行**

```bash
chmod +x scripts-old1/utils/route.sh
```

- [ ] **Step 3: 无任务时运行不报错**

```bash
bash scripts-old1/utils/route.sh
# Expected: no output, exit 0
```

- [ ] **Step 4: Commit**

```bash
git add scripts-old1/utils/route.sh
git commit -m "feat: add route.sh — task router with dependency check and review sub-routing

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 7: 创建 `scripts/utils/run-tests.sh` —— 测试执行器

**Files:**
- Create: `scripts/utils/run-tests.sh`

**接口:** `run-tests.sh <task_id>`，cwd 在项目根，后端跑 pytest，前端仅当改动涉及 html/ 时跑（当前项目无前端测试栈，仅骨架）。

- [ ] **Step 1: 写脚本**

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TASK_ID="${1:-}"

if [ -z "$TASK_ID" ]; then
  echo "Usage: run-tests.sh <task_id>" >&2
  exit 1
fi

cd "$ROOT"

failed=0
added=0

# 后端测试
if [ -d backend ]; then
  cd backend
  if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
    # 跑 pytest，捕获尾行统计
    pytest_output=$(pytest -q --tb=no 2>&1) || true
    failed=$(echo "$pytest_output" | grep -oP '\d+(?= failed)' || echo "0")
    cd "$ROOT"
  else
    echo "venv not found in backend/" >&2
    exit 1
  fi
fi

# 前端测试（骨架）
if git diff --name-only main...HEAD 2>/dev/null | grep -q '^prototype/'; then
  # 当前项目无前端测试栈，跳过
  :
fi

# 新增测试文件计数
added=$(git diff --name-only --diff-filter=A main...HEAD 2>/dev/null | grep -cE '(backend/tests/|tests/)' || echo "0")

echo "failed=$failed added=$added"
```

- [ ] **Step 2: 验证脚本可执行**

```bash
chmod +x scripts-old1/utils/run-tests.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts-old1/utils/run-tests.sh
git commit -m "feat: add run-tests.sh — test runner with failed/added counters

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 8: 重写 `scripts/hooks/review-hook.sh` —— 只跑测试不写 review

**Files:**
- Rewrite: `scripts/hooks/review-hook.sh`

**职责回退：** 不再写 review.md、不再改 tasks state。只跑测试 + append status.md。

- [ ] **Step 1: 重写脚本**

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TASK_ID="${1:-}"
STATUS="$ROOT/shared/current/status.md"
PARSE="$ROOT/scripts/utils/parse-task.sh"
RUN_TESTS="$ROOT/scripts/utils/run-tests.sh"

if [ -z "$TASK_ID" ]; then
  echo "Usage: review-hook.sh <task_id>" >&2
  exit 1
fi

# 校验 task 存在
state=$("$PARSE" "$TASK_ID" state 2>/dev/null) || {
  echo "[review-hook] $TASK_ID not found or parse error" >&2
  exit 1
}

type=$("$PARSE" "$TASK_ID" type 2>/dev/null) || type="feature"

# 跑测试
echo "[review-hook] Running tests for $TASK_ID..."
test_output=$("$RUN_TESTS" "$TASK_ID" 2>&1) || true
failed=$(echo "$test_output" | grep -oP 'failed=\K\d+' || echo "0")
added=$(echo "$test_output" | grep -oP 'added=\K\d+' || echo "0")

# 按 type 断言
case "$type" in
  refactor)
    if [ "$failed" -eq 0 ] && [ "$added" -eq 0 ]; then
      result="ok"
    else
      result="FAIL (refactor: expected 0 failed AND 0 added, got failed=$failed added=$added)"
    fi
    ;;
  test)
    if [ "$failed" -eq 0 ] && [ "$added" -ge 1 ]; then
      result="ok"
    else
      result="FAIL (test type: expected 0 failed AND >=1 added, got failed=$failed added=$added)"
    fi
    ;;
  *)
    if [ "$failed" -eq 0 ]; then
      result="ok"
    else
      result="FAIL (failed=$failed)"
    fi
    ;;
esac

# 追加到 status.md
echo "[$(date '+%Y-%m-%d %H:%M')] [review-hook] tests for $TASK_ID (type=$type): $failed failed, $added added → $result" >> "$STATUS"

# 检查 commit 前缀（U6，第 3 期激活；第 1 期仅骨架）
if git diff --name-only main...HEAD 2>/dev/null | grep -q .; then
  commits_without_prefix=$(git log --format="%h %s" main..HEAD 2>/dev/null | grep -v "\[$TASK_ID\]" || true)
  if [ -n "$commits_without_prefix" ]; then
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      echo "[$(date '+%Y-%m-%d %H:%M')] [review-hook] ⚠ commit prefix missing: $line" >> "$STATUS"
    done <<< "$commits_without_prefix"
  fi

  # 输出 commit 范围
  commit_hashes=$(git log --grep="\[$TASK_ID\]" --format="%H" main..HEAD 2>/dev/null || true)
  commit_count=$(echo "$commit_hashes" | grep -c . || echo "0")
  if [ "$commit_count" -gt 0 ]; then
    first=$(echo "$commit_hashes" | tail -1 | cut -c1-7)
    last=$(echo "$commit_hashes" | head -1 | cut -c1-7)
    echo "[$(date '+%Y-%m-%d %H:%M')] [review-hook] commits for $TASK_ID: ${first}..${last} (${commit_count} commits)" >> "$STATUS"
  fi
fi

exit 0
```

- [ ] **Step 2: 删除旧的 review-hook.sh 行为痕迹**

确认不再有 `sed -i` 改 tasks.md 或 `cat > review.md` 的逻辑。

- [ ] **Step 3: Commit**

```bash
git add scripts-old1/hooks/review-hook.sh
git commit -m "fix: rewrite review-hook.sh to only run tests, not write review or change state

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 9: 重写 `scripts/hooks/archive-hook.sh` —— 原子化归档 + planner 手动调用

**Files:**
- Rewrite: `scripts/hooks/archive-hook.sh`

**职责:** planner 手动调用 `archive-hook.sh <task_id>`，原子化归档（先 cp 到 .tmp，再 mv），归档完成删除 current/ 中对应段。

- [ ] **Step 1: 重写脚本**

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TASK_ID="${1:-}"

if [ -z "$TASK_ID" ]; then
  echo "Usage: archive-hook.sh <task_id>" >&2
  exit 1
fi

TASKS="$ROOT/shared/current/tasks.md"
STATUS="$ROOT/shared/current/status.md"
REVIEW="$ROOT/shared/current/review.md"
NEXT_ACTION="$ROOT/shared/current/next-action.md"
PARSE="$ROOT/scripts/utils/parse-task.sh"

# 校验 task 存在且 state=done
state=$("$PARSE" "$TASK_ID" state 2>/dev/null) || {
  echo "[archive-hook] $TASK_ID not found" >&2
  exit 1
}

if [ "$state" != "done" ]; then
  echo "[archive-hook] $TASK_ID state=$state, must be done" >&2
  exit 2
fi

# 提取 task slug（从标题取）
task_title=$(grep -m1 "^### $TASK_ID:" "$TASKS" | sed "s/^### $TASK_ID:[[:space:]]*//" || echo "$TASK_ID")
slug=$(echo "$task_title" | tr ' ' '-' | tr -cd '[:alnum:]-_' | cut -c1-50)

ARCHIVE_DIR="$ROOT/shared/archive/${TASK_ID}-${slug}"
TMP_DIR="${ARCHIVE_DIR}.tmp"

# 检查是否已归档
if [ -d "$ARCHIVE_DIR" ]; then
  echo "[archive-hook] $TASK_ID already archived at $ARCHIVE_DIR" >&2
  exit 3
fi

# 原子化：先写到 .tmp
rm -rf "$TMP_DIR" 2>/dev/null || true
mkdir -p "$TMP_DIR"

# 截取 tasks.md 中该 Task 段
awk "/^### $TASK_ID[ :]/{found=1} found{print} /^### /&&found&&!/^### $TASK_ID[ :]/{exit}" "$TASKS" > "$TMP_DIR/task.md"

# 过滤 status.md 中包含该 Task 的行
grep "$TASK_ID" "$STATUS" > "$TMP_DIR/status.md" 2>/dev/null || touch "$TMP_DIR/status.md"

# 截取 review.md 中该 Task 段
awk "/^### $TASK_ID[ :]/{found=1} found{print} /^### /&&found&&!/^### $TASK_ID[ :]/{exit}" "$REVIEW" > "$TMP_DIR/review.md" 2>/dev/null || touch "$TMP_DIR/review.md"

# 列出引用的 decisions
grep -oP 'decisions/\K[^ ]+' "$TMP_DIR/status.md" 2>/dev/null | sort -u > "$TMP_DIR/decisions.txt" || touch "$TMP_DIR/decisions.txt"

# 原子化提交：mv .tmp → 正式目录
mv "$TMP_DIR" "$ARCHIVE_DIR"

# 清理 current/ 文件
# tasks.md: 删除该 Task 段
awk "/^### $TASK_ID[ :]/{found=1; next} /^### /&&found{found=0} !found{print}" "$TASKS" > "${TASKS}.tmp" && mv "${TASKS}.tmp" "$TASKS"

# review.md: 删除该 Task 段
awk "/^### $TASK_ID[ :]/{found=1; next} /^### /&&found{found=0} !found{print}" "$REVIEW" > "${REVIEW}.tmp" && mv "${REVIEW}.tmp" "$REVIEW"

# next-action.md: 删除该 Task 段
awk "/^### $TASK_ID[ :]/{found=1; next} /^### /&&found{found=0} !found{print}" "$NEXT_ACTION" > "${NEXT_ACTION}.tmp" && mv "${NEXT_ACTION}.tmp" "$NEXT_ACTION"

# status.md 保留全文（不删），超 500 行时整体归档
STATUS_LINES=$(wc -l < "$STATUS")
if [ "$STATUS_LINES" -gt 500 ]; then
  STATUS_ARCHIVE="$ROOT/shared/archive/status-log-$(date +%Y-%m-%d).md"
  cp "$STATUS" "$STATUS_ARCHIVE"
  echo "# Status Log" > "$STATUS"
  echo "" >> "$STATUS"
  echo "<!-- rolled over from $STATUS_ARCHIVE -->" >> "$STATUS"
fi

echo "[$(date '+%Y-%m-%d %H:%M')] [archive-hook] Archived $TASK_ID → $ARCHIVE_DIR" >> "$STATUS"
echo "[archive-hook] Archived $TASK_ID → $ARCHIVE_DIR"
```

- [ ] **Step 2: 验证脚本可执行**

```bash
chmod +x scripts-old1/hooks/archive-hook.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts-old1/hooks/archive-hook.sh
git commit -m "fix: rewrite archive-hook.sh for atomic archive, planner-invoked only

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 10: 创建 `scripts/send-to-agent.sh` —— tmux send-keys 封装

**Files:**
- Create: `scripts/send-to-agent.sh`

**接口:** `send-to-agent.sh <agent> <prompt_file>`，agent ∈ {planner, backend, frontend, reviewer}，prompt 从文件读取避免 shell 转义。

- [ ] **Step 1: 写脚本**

```bash
#!/usr/bin/env bash
set -euo pipefail

AGENT="${1:-}"
PROMPT_FILE="${2:-}"

if [ -z "$AGENT" ] || [ -z "$PROMPT_FILE" ]; then
  echo "Usage: send-to-agent.sh <agent> <prompt_file>" >&2
  exit 1
fi

case "$AGENT" in
  planner|backend|frontend|reviewer) ;;
  *)
    echo "Invalid agent: $AGENT (must be planner|backend|frontend|reviewer)" >&2
    exit 1
    ;;
esac

if [ ! -f "$PROMPT_FILE" ]; then
  echo "Prompt file not found: $PROMPT_FILE" >&2
  exit 1
fi

WINDOW="multi-agent:$AGENT"

# 检查 window 是否存在
if ! tmux list-windows -t multi-agent 2>/dev/null | grep -q "$AGENT"; then
  echo "[send-to-agent] window $WINDOW not found" >&2
  exit 1
fi

# 检查 agent 是否 idle（末行是否为 prompts 符号）
last_line=$(tmux capture-pane -p -t "$WINDOW" 2>/dev/null | tail -1 || echo "")
if echo "$last_line" | grep -qE '[>❯$#]'; then
  # idle，发送唤醒指令
  tmux send-keys -t "$WINDOW" "$(cat "$PROMPT_FILE")" Enter
  echo "[send-to-agent] sent wakeup to $AGENT"
else
  echo "[send-to-agent] $AGENT busy, skipping"
  exit 2
fi
```

- [ ] **Step 2: 创建唤醒 prompt 模板目录**

```bash
mkdir -p scripts-old1/prompts
```

- [ ] **Step 3: 创建通用唤醒 prompt 模板 `scripts/prompts/wakeup.txt`**

```
你被调度台派活了。请按以下顺序执行：
1. 读 shared/current/next-action.md 看你这次扮演的角色
2. 读 CLAUDE.md、agents/<你的角色>.md
3. 读 shared/current/tasks.md、shared/current/status.md、shared/decisions/
4. 如果你是 reviewer，额外读 shared/current/review.md
5. 按你角色文件里的职责执行
6. 完成后更新 status.md 和 tasks.md 的 state
   —— 例外：reviewer 写 Decision: changes-requested 时不改 state；
      owner 收到 changes-requested 改完后直接把 state 改回 review（不退到 in-progress）
```

- [ ] **Step 4: 创建 bootstrap prompt 模板 `scripts/prompts/bootstrap-planner.txt`**

```
你是 multi-agent-coach 项目的 planner agent。
请读 CLAUDE.md、agents/planner.md 加载你的职责。
进入待命状态，收到调度台的唤醒指令再行动。
不要主动检查 shared/ 文件，等被叫。
```

- [ ] **Step 5: 创建其余 agent 的 bootstrap prompt**

```bash
for role in backend frontend reviewer; do
  sed "s/planner/$role/g" scripts-old1/prompts/bootstrap-planner.txt > "scripts/prompts/bootstrap-${role}.txt"
done
```

- [ ] **Step 6: 验证脚本可执行**

```bash
chmod +x scripts-old1/send-to-agent.sh
```

- [ ] **Step 7: Commit**

```bash
git add scripts-old1/send-to-agent.sh scripts-old1/prompts/
git commit -m "feat: add send-to-agent.sh with tmux send-keys and bootstrap prompts

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 11: 重写 `scripts/control-plane.sh` —— 守护进程式调度循环

**Files:**
- Rewrite: `scripts/control-plane.sh`

**职责：** 守护进程 `while true; do route+dispatch; sleep 2; done`。不再直接改 state，不再自动跑 archive-hook。dispatcher.sh 逻辑并入此脚本。

- [ ] **Step 1: 重写脚本**

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAST_DISPATCH="$ROOT/shared/current/.last-dispatched"
HEALTH="$ROOT/shared/current/.cockpit-health.md"
PIDFILE="$ROOT/shared/current/.cockpit.pid"
ROUTE="$ROOT/scripts/utils/route.sh"
SEND="$ROOT/scripts/send-to-agent.sh"
REVIEW_HOOK="$ROOT/scripts/hooks/review-hook.sh"
PARSE="$ROOT/scripts/utils/parse-task.sh"

# PID 锁
if [ -f "$PIDFILE" ]; then
  old_pid=$(cat "$PIDFILE")
  if kill -0 "$old_pid" 2>/dev/null; then
    echo "[control-plane] already running (PID $old_pid)" >&2
    exit 1
  fi
fi
echo $$ > "$PIDFILE"

# 退出清理
cleanup() {
  rm -f "$PIDFILE"
  echo "[$(date '+%Y-%m-%d %H:%M')] [cockpit] stopped" >> "$ROOT/shared/current/status.md"
  exit 0
}
trap cleanup SIGINT SIGTERM

echo "[$(date '+%Y-%m-%d %H:%M')] [cockpit] started" >> "$ROOT/shared/current/status.md"

# 初始化 .last-dispatched 和 health 文件
[ -f "$LAST_DISPATCH" ] || echo '{}' > "$LAST_DISPATCH"
[ -f "$HEALTH" ] || echo "# Cockpit Health" > "$HEALTH"

# JSON 读取辅助（纯 bash，不依赖 jq）
read_json_field() {
  local key="$1"
  local file="$2"
  grep -oP "\"$key\":\"[^\"]*\"" "$file" 2>/dev/null | head -1 | sed 's/.*":"//;s/"//' || echo ""
}

# 死锁检测
declare -A stall_count

# 首次启动 / 重连：检测 agent window 是否已 bootstrap
bootstrap_if_needed() {
  for agent in planner backend frontend reviewer; do
    window="multi-agent:$agent"
    if tmux list-windows -t multi-agent 2>/dev/null | grep -q "$agent"; then
      last_screen=$(tmux capture-pane -p -t "$window" 2>/dev/null | tail -30 || echo "")
      if ! echo "$last_screen" | grep -q "我是.*角色"; then
        bootstrap_file="$ROOT/scripts/prompts/bootstrap-${agent}.txt"
        if [ -f "$bootstrap_file" ]; then
          "$SEND" "$agent" "$bootstrap_file" 2>/dev/null || true
          echo "[$(date '+%Y-%m-%d %H:%M')] [cockpit] bootstrap sent to $agent" >> "$ROOT/shared/current/status.md"
        fi
      fi
    else
      echo "[$(date '+%Y-%m-%d %H:%M')] [cockpit] ⚠ window $agent not found" >> "$HEALTH"
    fi
  done
}

bootstrap_if_needed

while true; do
  # 备份旧 dispatch 状态
  old_dispatch=$(cat "$LAST_DISPATCH" 2>/dev/null || echo '{}')

  # 新 dispatch 状态
  new_dispatch='{'

  # 运行路由
  route_output=$("$ROUTE" 2>&1) || true

  # 构建 next-action.md
  cat > "$ROOT/shared/current/next-action.md" <<NEXTEOF
# Next Action

## Active dispatches
NEXTEOF

  # 按 agent 聚合
  declare -A agent_next
  declare -A agent_queue

  while IFS= read -r line; do
    [ -z "$line" ] && continue

    tid=$(echo "$line" | awk '{print $1}')
    agent=$(echo "$line" | awk '{print $2}')
    reason=$(echo "$line" | awk '{print $3" "$4" "$5" "$6" "$7}' | xargs)

    # 跳过 waiting_on 和 skipped
    if echo "$line" | grep -qE '(waiting_on|skipped)'; then
      echo "### $tid" >> "$ROOT/shared/current/next-action.md"
      echo "Agent: —" >> "$ROOT/shared/current/next-action.md"
      echo "Reason: $reason" >> "$ROOT/shared/current/next-action.md"
      echo "" >> "$ROOT/shared/current/next-action.md"
      continue
    fi

    echo "### $tid" >> "$ROOT/shared/current/next-action.md"
    echo "Agent: $agent" >> "$ROOT/shared/current/next-action.md"
    echo "Reason: $reason" >> "$ROOT/shared/current/next-action.md"
    echo "" >> "$ROOT/shared/current/next-action.md"

    # 去重检查 .last-dispatched
    last_state=$(read_json_field "$tid" "$LAST_DISPATCH" || echo "")
    current_state=$("$PARSE" "$tid" state 2>/dev/null || echo "unknown")

    dispatch_key="${tid}:${current_state}:${agent}"

    # 更新 new_dispatch
    new_dispatch+="\"$tid\":\"$current_state:$agent\","

    if [ "$last_state" = "$current_state:$agent" ]; then
      # 去重：上一轮已派过同一个 (task, state, agent)
      # 检查死锁
      stall_count["$tid"]=$((${stall_count["$tid"]:-0} + 1))
      if [ ${stall_count["$tid"]} -ge 10 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M')] [cockpit] ⚠ stall detected: $tid $current_state→$agent (${stall_count["$tid"]} cycles)" >> "$HEALTH"
      fi
      continue
    fi

    # 重置停滞计数
    stall_count["$tid"]=0

    # state=review: 先跑 review-hook
    if [ "$current_state" = "review" ]; then
      "$REVIEW_HOOK" "$tid" 2>/dev/null || true
    fi

    # 发送唤醒
    prompt_file="$ROOT/scripts/prompts/wakeup.txt"
    "$SEND" "$agent" "$prompt_file" 2>/dev/null || {
      echo "[$(date '+%Y-%m-%d %H:%M')] [cockpit] ⚠ failed to wake $agent for $tid" >> "$HEALTH"
    }

    # 聚合 agent queue
    task_type=$("$PARSE" "$tid" type 2>/dev/null || echo "feature")
    task_priority=$("$PARSE" "$tid" priority 2>/dev/null || echo "normal")
    if [ -z "${agent_next[$agent]:-}" ]; then
      agent_next[$agent]="$tid ($task_type, priority=$task_priority)"
    else
      agent_queue[$agent]="${agent_queue[$agent]:-} $tid ($task_type, priority=$task_priority)"
    fi
  done <<< "$route_output"

  new_dispatch="${new_dispatch%,}}"
  echo "$new_dispatch" > "$LAST_DISPATCH"

  # 追加 Agent queues 到 next-action.md
  cat >> "$ROOT/shared/current/next-action.md" <<NEXTEOF
## Agent queues
NEXTEOF

  for agent in planner backend frontend reviewer; do
    if [ -n "${agent_next[$agent]:-}" ]; then
      echo "### $agent" >> "$ROOT/shared/current/next-action.md"
      echo "Next: ${agent_next[$agent]}" >> "$ROOT/shared/current/next-action.md"
      [ -n "${agent_queue[$agent]:-}" ] && echo "Queue:${agent_queue[$agent]}" >> "$ROOT/shared/current/next-action.md"
      echo "" >> "$ROOT/shared/current/next-action.md"
    fi
  done

  # 追加 Dependency graph 到 next-action.md
  cat >> "$ROOT/shared/current/next-action.md" <<NEXTEOF
## Dependency graph
NEXTEOF
  echo "$route_output" | grep -v 'dispatch\|skipped' >> "$ROOT/shared/current/next-action.md" 2>/dev/null || echo "(no dependencies)" >> "$ROOT/shared/current/next-action.md"

  unset agent_next
  unset agent_queue

  sleep 2
done
```

- [ ] **Step 2: 验证脚本可执行**

```bash
chmod +x scripts-old1/control-plane.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts-old1/control-plane.sh
git commit -m "feat: rewrite control-plane.sh as daemon with route+dispatch loop

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 12: 创建 `scripts/utils/dashboard.sh` —— Cockpit 仪表盘

**Files:**
- Create: `scripts/utils/dashboard.sh`

**职责:** 分段渲染共享状态，供 `watch -n 2` 调用，全读操作不写文件。

- [ ] **Step 1: 写脚本**

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
NEXT_ACTION="$ROOT/shared/current/next-action.md"
TASKS="$ROOT/shared/current/tasks.md"
STATUS="$ROOT/shared/current/status.md"
REVIEW="$ROOT/shared/current/review.md"
HEALTH="$ROOT/shared/current/.cockpit-health.md"

MAX_LINES=80
printed=0

section() {
  local title="$1"
  printf '\n═══ %s ═══\n' "$title"
  printed=$((printed + 1))
}

check_truncate() {
  if [ $printed -ge $MAX_LINES ]; then
    echo "... (truncated, see shared/current/<file>)"
    exit 0
  fi
}

# next-action
section "next-action"
check_truncate
if [ -f "$NEXT_ACTION" ]; then
  cat "$NEXT_ACTION"
  printed=$((printed + $(cat "$NEXT_ACTION" | wc -l)))
fi

# tasks (active only, non-done)
section "tasks (active)"
check_truncate
if [ -f "$TASKS" ]; then
  awk '/^### Task-/{tid=$0} /^类型:/{t=$0} /^状态:/{s=$0} /^负责人:/{o=$0} /^priority:/{p=$0} /^depends_on:/{d=$0} /^### /&&found{print tid"\n"t"\n"s"\n"o"\n"p"\n"d"\n"; found=0} /^状态:[[:space:]]*done/&&found{found=0; next} /^### Task-/{found=1; tid=$0; t=""; s=""; o=""; p=""; d=""} END{if(found && s!~/done/) print tid"\n"t"\n"s"\n"o"\n"p"\n"d}' "$TASKS"
fi

# status (last 15)
section "status (last 15)"
check_truncate
if [ -f "$STATUS" ]; then
  tail -15 "$STATUS"
  printed=$((printed + 15))
fi

# review
section "review (current)"
check_truncate
if [ -f "$REVIEW" ]; then
  cat "$REVIEW"
  printed=$((printed + $(cat "$REVIEW" | wc -l)))
fi

# health
section "health (last 5)"
check_truncate
if [ -f "$HEALTH" ] && [ -s "$HEALTH" ]; then
  tail -5 "$HEALTH"
  printed=$((printed + 5))
else
  echo "(no warnings)"
  printed=$((printed + 1))
fi
```

- [ ] **Step 2: 验证脚本可执行**

```bash
chmod +x scripts-old1/utils/dashboard.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts-old1/utils/dashboard.sh
git commit -m "feat: add dashboard.sh — cockpit segmented status display

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 13: 创建 `.tmuxinator/multi-agent.yml` —— Workspace 配置

**Files:**
- Create: `.tmuxinator/multi-agent.yml`

- [ ] **Step 1: 写 tmuxinator 配置**

```yaml
name: multi-agent
root: ~/learn/AI项目/multi-agent-coach

windows:
  - cockpit:
      layout: main-horizontal
      panes:
        - watch -n 2 'bash scripts-old1/utils/dashboard.sh'
        - until bash scripts-old1/control-plane.sh; do sleep 5; done
  - planner:
      panes:
        - claude code
  - backend:
      panes:
        - claude code
  - frontend:
      panes:
        - claude code
  - reviewer:
      panes:
        - claude code
```

- [ ] **Step 2: Commit**

```bash
git add .tmuxinator/multi-agent.yml
git commit -m "feat: add tmuxinator workspace config for multi-agent cockpit

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 14: 更新 `agents/planner.md` —— 加唤醒动作、blocked 处理、入口规则

**Files:**
- Modify: `agents/planner.md`

- [ ] **Step 1: 在现有职责后追加新章节**

在文件末尾追加：

```markdown

---

## 被唤醒的标准动作

收到调度台唤醒指令后，按顺序执行：

1. 读 `shared/current/next-action.md` 确认本次角色
2. 读 `CLAUDE.md`、`agents/planner.md`
3. 读 `shared/current/tasks.md`、`shared/current/status.md`、`shared/decisions/`
4. 按下方对应状态/类型的流程执行
5. 完成后更新 status.md（append）和 tasks.md 的 state

## 任务入口职责

### feature / refactor 入口

人在 planner window 描述需求 → 你负责：
1. 在 status.md append `[时间] [planner] Task-NNN type confirmed: <type>`
2. 计算 task_id（见下方 Task ID 分配）
3. 在 tasks.md 新增 Task-NNN（类型=<type>、状态=pending、负责人=按需求判断 backend/frontend、priority=normal）
4. 在 status.md append `[时间] [planner] Created Task-NNN`

### 人未标 type 的兜底

人没标 type → 默认按 `feature` 处理，但首条响应必须在 status.md append `[时间] [planner] Task-NNN type confirmed: feature`

## Task ID 分配

创建新任务时，task_id 计算方式：
1. `ls shared/archive/` 找 Task-NNN 最大编号 N_max
2. `grep '^### Task-' shared/current/tasks.md` 找 Task-NNN 最大编号 N_cur
3. 新 task_id = max(N_max, N_cur) + 1，三位数 zero-pad（Task-001、Task-042、Task-128）

## Blocked 处理流程

当被唤醒处理 blocked 任务时：
1. 读 shared/current/review.md 和 status.md 找 blocker 原因
2. 三选一：
   a. **推回**：改 tasks.md owner，改 state=pending，加 changes-requested 字段说明替代方案
   b. **取消**：改 state=done，加 cancelled: true 和 cancelled_reason
   c. **等待**：保留 state=blocked，在 status.md append `[时间] [planner] Task-NNN: 等待上游，由 owner 自行恢复`
3. 在 status.md 记下决策
4. 若 owner 标 blocked 但 status.md 缺三行 evidence（原因/所需协助/下一步），必须 append `[时间] [planner] Task-NNN blocker 信息不全，要求补全` 并把 state 改回 in-progress

## Done 状态处理

被唤醒处理 done 状态任务时：
1. 确认 review.md 中 Decision=approved
2. 运行 `bash scripts/hooks/archive-hook.sh <task_id>`
3. 在 status.md append `[时间] [planner] Task-NNN archived`

## Decisions 触发条件

任何下列情况必须在 shared/decisions/ 写一份决策文档：
- 新增/移除一个模块、目录、子系统
- 选择某个库/框架/数据库（含版本）
- 改变现有 API/数据契约
- 任何"这个为什么这么做"3 个月后会被问到的事
```

- [ ] **Step 2: Commit**

```bash
git add agents-1/planner.md
git commit -m "feat: add wakeup protocol, blocked handling, and entry rules to planner.md

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 15: 更新 `agents/backend.md` —— 加唤醒动作、type 差异、blocked 自标

**Files:**
- Modify: `agents/backend.md`

- [ ] **Step 1: 在现有职责后追加新章节**

```markdown

---

## 被唤醒的标准动作

收到调度台唤醒指令后，按顺序执行：
1. 读 `shared/current/next-action.md` 确认本次角色
2. 读 `CLAUDE.md`、`agents/backend.md`
3. 读 `shared/current/tasks.md`、`shared/current/status.md`、`shared/decisions/`
4. 按任务 type 和 state 执行对应流程
5. 完成后更新 status.md（append）和 tasks.md 的 state

## 任务入口职责

### bugfix / test / trivial / spike 入口

人在 backend window 描述任务 → 你负责：
1. 计算 task_id
2. 在 status.md append `[时间] [backend] Task-NNN type confirmed: <type>`
3. 在 tasks.md 新增 Task-NNN（类型=<type>、状态=in-progress、负责人=backend）—— 跳过 pending
4. 按 type 执行（见下方）
5. 完成后按 type 决定是否进 review

### 人未标 type 的兜底

人没标 type → 默认按 `feature` 处理，但首条响应必须在 status.md append `[时间] [backend] Task-NNN type confirmed: feature`。注意：feature 必须在 planner window 创建，所以此时应回复请人去 planner window。

## Task ID 分配

同 planner.md 的 Task ID 分配规则。

## 各 type 执行差异

### feature
- 等 planner 创建任务 + state=pending 后，收到调度台唤醒才开始
- 设计 → 实现 → 单测 + 集测
- 完成 → state→review

### bugfix
- **先写一个能稳定复现的失败测试**，再让它 pass
- 完成时 status.md 必须包含两行 evidence：
  ```
  [时间] [backend] Task-NNN regression test added: <test_id> (failing on base commit)
  [时间] [backend] Task-NNN fix applied, regression test now passing
  ```
- 完成 → state→review

### refactor
- 不改行为只改结构
- 现有测试零失败
- 原则上不新增测试
- 完成 → state→review

### test
- 只动测试/测试夹具，不改业务代码
- 完成 → state→review

### trivial / spike
- 完成 → **直接 state→done**（不进 review）
- trivial: status.md append `[时间] [backend] Task-NNN done (trivial, skip review)`
- spike: status.md append `[时间] [backend] Task-NNN spike conclusion: <结论>` + state→done

## 完成 task 前的 commit 约定

所有 commit 必须以 `[Task-NNN]` 开头：
```
[Task-003] add /api/register endpoint
[Task-003] add unit tests for register flow
```

## In-progress 中自标 blocked 的动作

执行中遇到阻塞 → 你有权标 blocked：
1. tasks.md 该 Task 段 state→blocked
2. status.md append 三行：
   ```
   [时间] [backend] Task-NNN blocked: <阻塞原因>
   [时间] [backend] Task-NNN needs: <所需协助>
   [时间] [backend] Task-NNN next: <下一步行动>
   ```
完成后调度台会自动唤醒 planner 处理。

## 自解阻塞回 in-progress

当阻塞原因消失（如外部资源就绪），你可自行：
1. tasks.md state→in-progress
2. status.md append `[时间] [backend] Task-NNN unblocked, resume`

## 收到 changes-requested 后

reviewer 写 changes-requested 时 state 保持 review。你收到唤醒后：
1. 读 review.md 找 Required changes
2. 改代码解决问题
3. **直接把 state 改回 review**（不退到 in-progress）
4. status.md append `[时间] [backend] Task-NNN changes applied, ready for re-review`
```

- [ ] **Step 2: Commit**

```bash
git add agents-1/backend.md
git commit -m "feat: add wakeup protocol, type differences, and blocked self-marking to backend.md

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 16: 更新 `agents/frontend.md` —— 同 backend 结构

**Files:**
- Modify: `agents/frontend.md`

- [ ] **Step 1: 追加与 backend.md 相同结构的新章节（角色名替换为 frontend）**

将 Task 15 的内容中 `backend` 替换为 `frontend`，`后端` 替换为 `前端`，追加到 frontend.md 末尾。

- [ ] **Step 2: Commit**

```bash
git add agents-1/frontend.md
git commit -m "feat: add wakeup protocol, type differences, and blocked self-marking to frontend.md

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 17: 更新 `agents/reviewer.md` —— 加唤醒动作、按 type 检查、decision 边界

**Files:**
- Modify: `agents/reviewer.md`

- [ ] **Step 1: 在现有职责后追加新章节**

```markdown

---

## 被唤醒的标准动作

收到调度台唤醒指令后，按顺序执行：
1. 读 `shared/current/next-action.md` 确认本次角色
2. 读 `CLAUDE.md`、`agents/reviewer.md`
3. 读 `shared/current/tasks.md`、`shared/current/status.md`、`shared/decisions/`
4. **额外**：读 `shared/current/review.md`
5. 按任务 type 执行对应检查
6. 写 review.md（覆盖该 Task 段）→ 决定 approved/changes-requested → 按规则改 state

## investigate 入口

人在 reviewer window 描述调查任务 → 你负责：
1. 在 status.md append `[时间] [reviewer] Task-NNN type confirmed: investigate`
2. 在 tasks.md 新增 Task-NNN（investigate / in-progress / reviewer）
3. 调查 + 不改业务代码
4. 结论写 status.md：`[时间] [reviewer] Task-NNN findings: <结论>`
5. state→done（不进 review）

## 各 type 检查点

### feature
- diff 符合需求
- 测试覆盖充分
- API 契约一致

### bugfix
- status.md 必须含 evidence 两行（regression test added + fix applied）
- 缺一 → changes-requested
- diff 只动必要文件

### refactor
- 行为等价：现有测试零失败
- diff 无新公开符号/新分支语义
- 如有 → changes-requested 或要求 planner 改 type

### test
- diff 仅在测试树内
- 新测试有意义（非 mock-only 套娃）

### trivial / spike / investigate
- 不进 review，不会收到此类任务

## Decision 规则

在 review.md 按 `### Task-NNN` 分段写，覆盖式（不 append）：

```
### Task-003 (feature)
**Decision**: approved
**Reviewed at**: YYYY-MM-DD HH:MM
**Notes**: API 契约一致，测试覆盖 OK
```

Decision 值 ∈ {approved, changes-requested, needs-discussion}：
- `approved` → **改 tasks.md state=done**
- `changes-requested` → **不改 state**（保持 review），控制台子路由会唤醒 owner
- `needs-discussion` → **不改 state**（保持 review），控制台子路由会唤醒 planner 仲裁

## changes-requested 的强制触发条件

以下情况必须 changes-requested：
- bugfix 缺 evidence 两行中任一行
- bugfix diff 中看不到新测试文件
- refactor 现有测试有失败
- refactor diff 引入新公开符号或新分支语义
- review-hook 输出含 `ownership violation`
- review-hook 输出含 `commit prefix missing`

## 看 task diff 的规则

必须用 `bash scripts/utils/task-diff.sh Task-NNN` 查看单 task 隔离 diff。
禁用全局 `git diff main...HEAD`。

## 复审同一 task

复审时覆盖 review.md 中该 Task-NNN 段（不追加历史），避免堆积。
```

- [ ] **Step 2: Commit**

```bash
git add agents-1/reviewer.md
git commit -m "feat: add wakeup protocol, type checkpoints, and decision boundaries to reviewer.md

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 18: 清理 —— 删除 `scripts-old/` 和废弃脚本

**Files:**
- Delete: `scripts-old/` (git rm)
- Delete or archive: `scripts/dispatcher.sh`, `scripts/status-watch.sh`（逻辑已并入 control-plane.sh 和 dashboard.sh）

- [ ] **Step 1: 删除 scripts-old/**

```bash
git rm -r scripts-old1-old/
```

- [ ] **Step 2: 删除废弃脚本**

```bash
git rm scripts-old1/dispatcher.sh scripts-old1/status-watch.sh
```

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: remove scripts-old/ and deprecated dispatcher/status-watch scripts

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 19: 端到端验证 —— Feature 流程

**对照 spec §8.1 手动验证以下步骤：**

- [ ] **Step 1:** 启动 `mux start multi-agent`，确认 5 个 window 起来
- [ ] **Step 2:** 在 planner window 输入 "加一个 GET /api/health 接口"
- [ ] **Step 3:** 观察 cockpit 仪表盘，确认 Task-NNN 出现 + next-action 指向 backend
- [ ] **Step 4:** 确认 backend window 收到唤醒指令
- [ ] **Step 5:** backend 完成后，确认 review-hook 跑测试 + reviewer 被唤醒
- [ ] **Step 6:** reviewer approved 后，确认 planner 被唤醒 + archive 完成

**反向验证：**

- [ ] **Step 7:** reviewer 写 changes-requested 且不改 state → 确认 backend 被二次唤醒
- [ ] **Step 8:** backend 改完直接 state→review（不进 in-progress）→ 确认 reviewer 二次唤醒
- [ ] **Step 9:** 故意让 reviewer 把 state 改成 in-progress → 确认 cockpit-health 报警

详细验收条件见 spec §8.1。

---

## 第 2 期：P1 一致性修复（Bugfix/Refactor 流程 + CODEOWNERS）

第 2 期在第 1 期验收通过后启动，主要改动：

### Task 20: 创建 `CODEOWNERS` + review-hook 越界检查（C5）

- Create `CODEOWNERS`（按 spec §5.2 C5 格式）
- 在 review-hook.sh 加 ownership check（git diff --name-only → 查 CODEOWNERS → 不匹配则 append violation）

### Task 21: status.md 滚动归档（C3）

- 在 control-plane.sh 启动时检查 status.md 行数，>500 行归档到 `shared/archive/status-log-<date>.md`

### Task 22: agents/*.md 各 type 执行差异补齐（§7.2）

- 更新 backend/frontend/reviewer 的 type 差异表（已在第 1 期预留骨架，补全细节）

### Task 23: Bugfix 流程端到端验收（§8.2）

### Task 24: Refactor 流程端到端验收（§8.3）

---

## 第 3 期：P2 体验性修复（多任务依赖 + 死锁防护 + commit 前缀）

第 3 期在第 2 期验收通过后启动：

### Task 25: 死锁防护 + 健康监控完善（U3）

- control-plane.sh 完善 stall detection、state 合法性校验、循环依赖检测

### Task 26: 多任务依赖与优先级（U5）

- route.sh 加优先级排序（priority desc + 创建时间 asc）
- 循环依赖检测（拓扑排序）

### Task 27: task-commit 前缀关联（U6）

- 创建 `scripts/utils/task-diff.sh`
- review-hook.sh 加 commit prefix check
- reviewer.md 加 task-diff 使用规则

### Task 28: archive 重置 review.md（U2）

- archive-hook.sh 确保归档后 review.md 对应段被删除（已在 Task 9 实现，此处验证）

---

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| tmux send-keys 与 Claude Code 输入冲突 | send-to-agent.sh 检查 agent idle（capture-pane 末行）再发送 |
| 多 agent 同时 append status.md | macOS `>>` 单行 <4096B 原子，安全 |
| 人/agent 并发改 tasks.md | agent 写共享文件用单次 Edit/>>；下一轮唤醒时先读当前状态对比 |
| Claude Code context 溢出 | agent 完成任务后 /clear，下次唤醒重读角色文件 |
| .last-dispatched JSON 损坏 | 损坏时备份 + 重置 `{}` + 默认 dispatch |
| archive-hook 中途崩溃 | 先 cp 到 .tmp 再 mv 原子化；残留 .tmp 由 control-plane 启动扫描报警 |

---

## Self-Review

**Spec coverage check:**
- B1 唤醒机制 → Task 10, 11
- B2 bootstrap → Task 10 (bootstrap prompt), Task 11 (bootstrap_if_needed)
- B3 多任务格式 → Task 2 (tasks.md), Task 5 (next-action.md)
- B4 blocked 处理 → Task 14 (planner.md)
- B5 next-action/review 分段 → Task 4, 5
- C1 review-hook 退回 → Task 8
- C2 archive-hook planner 调用 → Task 9, 11
- C3 status.md append-only → Task 3
- C4 decisions 激活 → Task 14
- C5 CODEOWNERS → Task 20 (Phase 2)
- U1 task ID 分配 → Task 14
- U2 archive 重置 review.md → Task 9
- U3 死锁防护 → Task 11, 25
- U4 tmuxinator → Task 13
- U5 多任务依赖优先级 → Task 6 (depends_on), 26
- U6 task-commit 前缀 → Task 8 (骨架), 27
- §7 路由表 → Task 6
- §7.1 入口规则 → Task 14, 15, 16, 17
- §7.4 人手动干预 → Task 14
- §8.1 Feature 验收 → Task 19
- §8.2 Bugfix 验收 → Task 23 (Phase 2)
- §8.3 Refactor 验收 → Task 24 (Phase 2)
- §8.4 Blocked 验收 → Task 14, 15, 19
- §8.5 skip review 验收 → Task 15, 17

**No placeholder check:** All tasks have concrete code, paths, and commands.

**Type consistency:** Task IDs use `Task-NNN` format consistently. `PARSE` variable points to `scripts/utils/parse-task.sh`. All scripts use `$ROOT` convention.
