# Multi-Agent Cockpit 流程修复设计

**Date:** 2026-05-29
**Status:** Draft
**Scope:** 修复 `multi-agent-coach` 现有 multi-agent 工作流的阻塞性漏洞和一致性漏洞，让流程从"跑不通"到"端到端可用"。

---

## 1. 背景

项目已经定义了完整的 multi-agent 协作框架：

- **`CLAUDE.md`** —— 顶层规范：5 角色、5 状态机、6 文件归属表、Handoff 规则
- **`agents/`** —— 4 个角色（planner / backend / frontend / reviewer）的职责文档
- **`shared/current/`** —— 共享消息板（tasks / status / review / next-action）
- **`shared/decisions/`、`shared/archive/`** —— 长期决策与归档
- **`scripts/`、`scripts-old/`** —— 两套调度脚本（新版精简、老版完整）

5 个 phase 的演进路径：

| Phase | 主题 | 当前状态 |
|---|---|---|
| 1 | Workspace（tmux/tmuxinator/WezTerm） | **未开始** |
| 2 | Role + Shared Memory | 已完成 |
| 3 | Workflow Automation | 部分（agent 自我执行） |
| 4 | Hooks | 部分（review-hook、archive-hook 存在但有职责越界） |
| 5 | Agent Bus + Dashboard | 部分（仪表盘有，但 agent 不会被唤醒） |

## 2. 问题陈述

**核心结论：当前流程跑不通。** 即使把 scripts/ 和 scripts-old/ 拼合也跑不通，因为有 4 类硬伤：

- **🔴 阻塞性漏洞**：agent 不会被唤醒、启动后不知道自己是谁、多 active 任务装不下、blocked 没有 handle 流程
- **🟡 一致性漏洞**：脚本越界替 agent 做事（review-hook 自己判 approved，archive-hook 自动跑），违反 CLAUDE.md 的角色归属
- **🟢 体验性漏洞**：缺死锁防护、缺 task ID 分配、archive 后 review.md 不重置
- **Phase 1 缺失**：`.tmuxinator/multi-agent.yml` 完全没写，无法一键起 workspace

## 3. 设计目标

1. **跑通端到端**：从"人在 planner window 说一句话"→ 自动拆任务 → 自动派活 → 自动测试 → reviewer 自动审查 → planner 自动归档，全程不用人手动切窗口派工
2. **不违反 CLAUDE.md**：脚本只做"机器检查"，所有"语义判断"留给 agent
3. **可观察**：cockpit 仪表盘实时显示当前状态、谁在干活、上一步发生了什么
4. **vendor-neutral 写法（留口子，不做验证）**：当前 5 个 window 全跑 Claude Code。但 `agents/*.md` 内容和调度台 send-keys 的唤醒指令都写成纯文本指令，不依赖 Claude 特有 skill 机制。以后想把某个 window 换成 codex/gemini，只需改 `.tmuxinator/multi-agent.yml` 一行。本次不实测 codex/gemini 兼容性（见 Non-Goals）。

## 4. 架构

### 4.1 Workspace 形态

```
WezTerm 窗口
  └── tmux session: multi-agent
        ├── window 0: cockpit
        │     ├── pane 上（70%）: watch -n 2 './scripts/utils/dashboard.sh'  ← 仪表盘（分段+截断，见 §5.4.6）
        │     └── pane 下（30%）: ./scripts/control-plane.sh                 ← 调度循环
        ├── window 1: planner   $ claude code（启动后立即被 bootstrap）
        ├── window 2: backend   $ claude code
        ├── window 3: frontend  $ claude code
        └── window 4: reviewer  $ claude code
```

启动方式：`mux start multi-agent`，一键起 5 window，每个 agent window 自动启动 Claude Code 并完成身份初始化。

### 4.2 端到端数据流（feature 流程示例）

> 下面的图是 **feature** 流程，bugfix / refactor / test 入口不同，见 §7.1。

```
[人类]                                  [调度台]                        [Agent windows]
  │                                        │                                   │
  │ 在 planner window 打："加一个注册接口"                                       │
  ├──────────────────────────────────────────────────────────────────────────►│
  │                                        │              planner: 拆任务，写  │
  │                                        │              tasks.md（Task-003） │
  │                                        │                                   │
  │                                  每2秒读 tasks.md                          │
  │                                  发现 Task-003 新增、state=pending、       │
  │                                  owner=backend                             │
  │                                  → 写 next-action.md                       │
  │                                  → 跟 .last-dispatched 对比，变了           │
  │                                  → tmux send-keys 唤醒指令 到 backend     │
  │                                        ├──────────────────────────────────►│
  │                                        │                  backend: 读 next-│
  │                                        │                  action / 角色文件│
  │                                        │                  / 写代码 / 跑测试│
  │                                        │                  / 改 state=review│
  │                                        │                                   │
  │                                  下一轮：state=review                       │
  │                                  → 先跑 review-hook.sh（跑测试，结果       │
  │                                    append 到 status.md）                   │
  │                                  → 写 next-action.md (agent=reviewer)      │
  │                                  → send-keys 唤醒 reviewer                 │
  │                                        ├──────────────────────────────────►│
  │                                        │              reviewer: 读测试结果 │
  │                                        │              + diff + 角色文件     │
  │                                        │              → 写 review.md       │
  │                                        │              → 改 state=done 或   │
  │                                        │                state=blocked      │
  │                                        │                                   │
  │                                  下一轮：state=done                         │
  │                                  → send-keys 唤醒 planner                  │
  │                                        ├──────────────────────────────────►│
  │                                        │              planner: 调用        │
  │                                        │              archive-hook.sh 归档 │
  │                                        │              → 重置 current/ 文件 │
  │                                        │                                   │
  │ 你全程在 cockpit 仪表盘看进度                                              │
```

### 4.3 关键边界

| 谁的事 | 具体内容 |
|---|---|
| **调度台脚本** | 只读 tasks.md，不写；只跑机器检查（测试通过/未通过）；只 send-keys 唤醒；不替 agent 做语义判断 |
| **Agent (planner)** | 创建/拆分任务、决定 owner、做架构决策、归档（调用 archive-hook）、处理 blocked |
| **Agent (backend/frontend)** | 改代码、写测试、把 state 改成 review |
| **Agent (reviewer)** | 看 diff + 看测试结果 → 写 review.md → 决定 approved/changes-requested → 改 state |

调度台**永远不改 tasks.md 的 state**。所有 state 转移由 agent 自己按 CLAUDE.md 的归属表执行。

---

## 5. 修复清单

### 5.1 P0 阻塞性漏洞

#### B1. agent 唤醒机制

**问题**：control-plane 只写 next-action.md，没人推 agent。

**解法**：
- 新增 `scripts/send-to-agent.sh <agent>`：封装 `tmux send-keys -t multi-agent:<agent> "<wakeup-prompt>" Enter`
- `scripts/control-plane.sh` 在路由完后调用 `send-to-agent.sh`
- 唤醒指令用自然语言（vendor-neutral）：
  ```
  你被调度台派活了。请按以下顺序执行：
  1. 读 shared/current/next-action.md 看你这次扮演的角色
  2. 读 CLAUDE.md、agents/<你的角色>.md
  3. 读 shared/current/tasks.md、shared/current/status.md、shared/decisions/
  4. 如果你是 reviewer，额外读 shared/current/review.md
  5. 按你角色文件里的职责执行
  6. 完成后更新 status.md 和 tasks.md 的 state
     —— 例外：reviewer 写 Decision: changes-requested 时不改 state（详见 §7 子路由）；
        owner 收到 changes-requested 改完后直接把 state 改回 review（不退到 in-progress）
  ```
- 防重复：调度台维护 `shared/current/.last-dispatched`（一行 JSON），记上次派工的 `(task_id, state, agent)`，没变就不重复 send-keys

#### B2. agent bootstrap

**问题**：Claude Code 启动后是空 session，不知道自己是谁。

**解法**：`.tmuxinator/multi-agent.yml` 里每个 agent window 启动后立刻 send-keys 一段身份初始化：
```
你是 multi-agent-coach 项目的 <角色名> agent。
请读 CLAUDE.md、agents/<角色名>.md 加载你的职责。
进入待命状态，收到调度台的唤醒指令再行动。
不要主动检查 shared/ 文件，等被叫。
```

#### B3. 多 active 任务

**问题**：tasks.md 单任务格式，多个并发任务装不下。

**解法**：
- tasks.md 改为 list 格式，每个任务一段：
  ```
  ### Task-003: 加注册接口
  类型: feature
  状态: in-progress
  负责人: backend
  创建时间: 2026-05-29 12:00

  ### Task-004: 加用户列表页
  类型: feature
  状态: pending
  负责人: frontend
  创建时间: 2026-05-29 12:05
  ```
- status.md 和 review.md 按 `Task-XXX` 分段索引
- control-plane 遍历所有任务，按 (type, state) 路由表给每个非终态任务算 next_agent
- `.last-dispatched` 改为按 task_id 索引的字典：
  ```json
  {"Task-003": {"state": "in-progress", "agent": "backend"},
   "Task-004": {"state": "pending", "agent": "frontend"}}
  ```

#### B4. blocked 处理流程

**问题**：blocked 状态归 planner 处理，但 `agents/planner.md` 没写怎么处理。

**解法**：在 `agents/planner.md` 加一段：
```
当被唤醒处理 blocked 任务时：
1. 读 shared/current/review.md 找 blocker 原因
2. 决定：
   a. 推回 backend/frontend 修：改 tasks.md owner，改 state=pending，加 changes-requested 字段
   b. 取消任务：改 state=cancelled（新增状态？或归到 done + cancelled tag）
   c. 拆子任务：在 tasks.md 加新 task，把原 task 改 state=blocked-on-subtask
3. 在 status.md 记下决策
```

**取消任务的实现**：复用 `done` 状态，在 tasks.md 该任务段加 `cancelled: true` 字段。archive-hook 保留此字段写到归档 metadata。不新增 `cancelled` 状态（保持 CLAUDE.md 5 状态不变）。

#### B5. next-action.md 与 review.md 的多任务分段格式

**问题**：B3 给了 tasks.md 多任务格式，但 next-action.md / review.md「按 task_id 分段」无样本，agent 和脚本会各写一套。

**解法**：

**next-action.md**（control-plane 每轮**整文件覆写**）：

```
# Next Action

## Active dispatches

### Task-003
Agent: backend
Reason: dispatch (in-progress → owner)

### Task-005
Agent: —
Reason: waiting_on Task-003 (current=in-progress, need>=review)

### Task-006
Agent: planner
Reason: dispatch (blocked → planner)

## Agent queues

### backend
Next: Task-003 (feature, priority=normal)
Queue: Task-008 (test, priority=low)

### planner
Next: Task-006 (blocked)

## Dependency graph

Task-003 (in-progress, backend)
  └── Task-005 (pending, frontend) [need state>=review]
Task-006 (blocked, planner-handle)
Task-008 (pending, backend) [no deps]
```

**review.md**（reviewer 增删改自己负责的 task 段，**覆盖式**）：

```
# Reviews

### Task-003 (feature)
**Decision**: approved
**Reviewed at**: 2026-05-29 12:30
**Notes**: API 契约一致，测试覆盖 OK

### Task-005 (bugfix)
**Decision**: changes-requested
**Reviewed at**: 2026-05-29 12:35
**Required changes**:
- evidence 缺第二行（fix-applied 行未 append）
- diff 动了 `auth_service.py`，但 task 描述仅涉及 `login_handler.py`
```

**规则**：
- 文件按 `### Task-NNN` 分段；reviewer 只改自己 review 的段，不动别人的
- 复审同一 task 时**覆盖**该段（不像 status.md 是 append），避免历史 review 堆积
- `Decision` 必填，值 ∈ `{approved, changes-requested, needs-discussion}`：
  - `approved` → reviewer 改 tasks.md state=`done`
  - `changes-requested` → reviewer **不改 state**（保持 `review`），control-plane 子路由唤醒 owner（见 §7）
  - `needs-discussion` → reviewer **不改 state**，control-plane 子路由唤醒 planner 仲裁（见 §7）
- archive-hook 归档时截取 `### Task-NNN` 段写入 `archive/Task-NNN-<slug>/review.md`，并从 `current/review.md` 删除该段

---

### 5.2 P1 一致性漏洞

#### C1. review-hook 退回只跑测试

**问题**：当前 review-hook 自动写 approved 并改 tasks state，绕过 reviewer agent。

**解法**：
- `scripts/hooks/review-hook.sh` 只做：
  ```
  1. 跑测试（run-tests.sh）
  2. 把结果 append 到 status.md：
     [时间] [review-hook] tests for Task-003: passing|failing
  ```
- **不写 review.md，不改 tasks state**
- control-plane 在 state=review 时：先调 review-hook → 再 send-keys 唤醒 reviewer
- reviewer agent 读 status.md 里的测试结果 + 看 diff → 自己写 review.md → 自己改 state

#### C2. archive-hook 改为 planner 手动调用

**问题**：state=done 时 control-plane 自动跑 archive-hook，违反"仅 planner 可归档"。

**解法**：
- control-plane 在 state=done 时**不再自动跑** archive-hook
- 只 send-keys 唤醒 planner
- planner 被唤醒后在自己的执行里 `bash scripts/hooks/archive-hook.sh <task_id>`
- `agents/planner.md` 加一段 done 状态处理流程

#### C3. status.md 改 append-only

**问题**：所有脚本都 `cat > status.md` 覆盖，多 agent 写会丢消息。

**解法**：
- status.md 改为时间线格式：
  ```
  # Status Log

  [2026-05-29 12:00] [planner] Created Task-003: 加注册接口
  [2026-05-29 12:01] [backend] Started Task-003
  [2026-05-29 12:15] [backend] Finished implementation, tests passing
  [2026-05-29 12:15] [backend] State → review
  [2026-05-29 12:15] [review-hook] tests for Task-003: passing
  [2026-05-29 12:16] [reviewer] Started review for Task-003
  ...
  ```
- 所有脚本和 agent 用 `>>` append，不用 `>`
- 文件过长时（>500 行）归档到 `shared/archive/status-log-<date>.md`，current 重置

#### C4. decisions 激活

**问题**：CLAUDE.md 说 planner 必要时写 decisions，但没说什么时候。

**解法**：在 `agents/planner.md` 加触发条件：
```
任何下列情况必须在 shared/decisions/ 写一份决策文档：
- 新增/移除一个模块、目录、子系统
- 选择某个库/框架/数据库（含版本）
- 改变现有 API/数据契约
- 任何"这个为什么这么做"3 个月后会被问到的事
```

#### C5. agent 路径越界检查（CODEOWNERS）

**问题**：`agents/backend.md` / `frontend.md` 的「禁止」目前只是文字约束（"禁止：随意修改 frontend"），缺机器可验证的归属边界。多 agent 改动落在重叠区（如根目录共享配置）时无标准答案，reviewer 也可能漏看。

**解法**：

1. **项目根加 `CODEOWNERS`**（Git 原生格式，零额外工具，GitHub/GitLab 也认识）：
   ```
   # backend agent
   backend/                    @backend
   backend/tests/              @backend

   # frontend agent
   html/                       @frontend
   frontend/                   @frontend

   # planner（共享配置 + 治理文件）
   CLAUDE.md                   @planner
   alembic.ini                 @planner
   agents/                     @planner
   shared/decisions/           @planner
   scripts/                    @planner
   .tmuxinator/                @planner
   CODEOWNERS                  @planner

   # reviewer
   shared/current/review.md    @reviewer
   ```
   多人共拥用空格分隔：`backend/schemas/ @backend @frontend`

2. **`review-hook.sh` 加 ownership check**（在 C1 跑测试之后追加一步）：
   - 用 `parse-task.sh Task-NNN owner` 拿到 owner
   - `git diff --name-only main...HEAD` 拿改动文件
   - 对每个文件查 CODEOWNERS（longest-prefix match），判断是否包含 owner
   - 任一不在 → status.md append：
     ```
     [time] [review-hook] ⚠ ownership violation: Task-NNN owned by backend touched html/register.html (per CODEOWNERS owner=frontend)
     ```
   - review-hook 自身**退出码仍 0**（不替 reviewer 判决），但 reviewer 必须在 review.md 标 `changes-requested` 并把 violation 列入 Required changes

3. **`agents/reviewer.md` 触发条件新增**：「review-hook 输出含 `ownership violation` 时**必须** changes-requested」

**与 C1 的关系**：C5 是 review-hook 的扩展，跟 C1 同期改同一个文件，合并实施一次重写。

---

### 5.3 P2 体验性漏洞

#### U1. task ID 自动分配

`agents/planner.md` 加一段：
```
创建新任务时，task_id 计算方式：
1. ls shared/archive/ 找 Task-NNN 最大编号 N_max
2. cat shared/current/tasks.md 找 Task-NNN 最大编号 N_cur
3. 新 task_id = max(N_max, N_cur) + 1，三位数 zero-pad（Task-001、Task-042、Task-128）
```

#### U2. archive 重置 review.md

`scripts/hooks/archive-hook.sh` 修改：归档完成后除了重置 tasks.md / status.md，也重置 review.md。

#### U3. control-plane 死锁防护

`scripts/control-plane.sh` 加：
- 任务 state 不在 5 个合法值之内 → echo 警告 + 不派工（不退出）
- 同一任务连续 N 次循环（默认 10）next_agent 不变 → 暂停该任务派工 + 报警
- 这些状态记到 `shared/current/.cockpit-health.md`

#### U4. .tmuxinator/multi-agent.yml（Phase 1 交付物）

新增 `.tmuxinator/multi-agent.yml`：
```yaml
name: multi-agent
root: ~/learn/AI项目/multi-agent-coach   # 实施期填实际项目路径

windows:
  - cockpit:
      layout: main-horizontal
      panes:
        - watch -n 2 'cat shared-1/current/next-action.md; echo "---"; cat shared-1/current/tasks.md; echo "---"; cat shared-1/current/status.md; echo "---"; cat shared-1/current/review.md'
        - ./scripts-old1/control-plane.sh
  - planner:
      panes:
        - claude code
        # 之后 control-plane 第一次跑会 send-keys bootstrap，或在这里手动 sleep+send-keys
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

bootstrap 实现方式（二选一，实施期定）：
- 方式 A：tmuxinator yaml 里 `pre` hook 写 send-keys（复杂）
- 方式 B：control-plane 启动时检测 agent window，如果还没 bootstrap 就 send-keys 一次身份指令（推荐，逻辑集中）

---

#### U5. 多任务依赖与优先级

**问题**：B3 让 tasks.md 装得下多任务，但实际项目里任务间通常有依赖与优先级关系：
- **硬依赖**：Task-004 必须等 Task-003 done（schema 改完才能用）
- **软依赖**：Task-005 调用 Task-003 的新接口，只需等 Task-003 进入 review（API 契约稳定）
- **优先级**：生产 bugfix 应抢在已经 in-progress 的 feature 之前被派工

**解法**：

1. **tasks.md schema 扩展两字段**（在 B3 格式之上）：
   ```
   ### Task-005: 前端接入注册接口
   类型: feature
   状态: pending
   负责人: frontend
   创建时间: 2026-05-29 13:00
   depends_on: Task-003 (state>=review)        # 软依赖；无状态限定符默认 >=done
   priority: normal                            # high | normal | low，默认 normal
   ```
   - 多依赖逗号分隔：`depends_on: Task-003 (state>=done), Task-004`
   - 缺字段视为：无依赖、priority=normal

2. **路由前依赖检查**（在 `scripts/utils/route.sh` 里）：
   - 对每个非终态任务，解析 depends_on，逐个查上游当前 state
   - 任一不满足 → 跳过派工，next-action.md 标 `Task-NNN waiting on: Task-XXX (current=in-progress, need>=review)`
   - 全部满足 → 按原路由表给出 next_agent

3. **同 agent 多任务时按优先级排序**：
   - 一个 agent 同轮被多任务命中（例如 backend 有 3 个 pending），按 `priority desc + 创建时间 asc` 选当前最优，只发一次唤醒
   - next-action.md 列出队列让 cockpit 可见：
     ```
     Agent: backend
     Next: Task-006 (bugfix, priority=high)
     Queue: Task-003 (feature, priority=normal), Task-005 (test, priority=low)
     ```

4. **循环依赖检测**：control-plane 每轮路由前跑拓扑排序，检测到环 → `.cockpit-health.md` 报警 `circular dependency: Task-003 → Task-004 → Task-003`，暂停涉及任务派工（与 U3 死锁防护共用报警文件）。

5. **planner 与 owner 的职责增量**（落到 agents/*.md）：
   - planner 创建任务时必须填 priority（默认 normal）；判断有上游依赖时主动填 depends_on
   - owner 在执行任务时如果发现新依赖（例如 in-progress 中才意识到要等 Task-XXX），可自行在 tasks.md 加 depends_on 字段并把 state 改成 `blocked`，进 B4 流程交 planner 决定（拆子任务 / 等待 / 推回）

**U5 ↔ B4 协同**（owner 自标 blocked 后 planner 处置 depends_on）：
- owner 在 in-progress 中发现新依赖 → tasks.md 加 `depends_on: Task-XXX` + state=`blocked` + status.md 写阻塞原因（U5 第 5 条 + B4）
- control-plane 路由到 planner（按 blocked 行）
- planner 三选一：
  - **等待**：保留 `depends_on` + state=`blocked` → 上游进入满足态时由 owner 自解（state→in-progress）或 planner 二次唤醒推回
  - **推回**：删 `depends_on` + state=`pending` + 附 `changes-requested: 用替代方案绕开依赖`
  - **拆子任务**：保留 `depends_on`（指向新建子任务 Task-YYY）+ state=`blocked` 不变 → 子任务 done 后再恢复
- planner 决策必须 append 到 status.md，owner 二次唤醒时看清楚走哪条路

**不在 P2 实现的**（明确保留为未来期）：
- **抢占**：高优先级任务进来时强制中断 owner 当前任务并保存进度，需要状态机扩展（如 `interrupted` 子状态）和 agent 端的 checkpoint 协议
- **跨 agent 依赖预热**：例如 backend 的 Task-003 进 review 后立刻预热 frontend 的 Task-005——目前 cockpit 下一轮自然会检测到，无需特殊优化

#### U6. task-commit 前缀关联（多任务并发 review 的 diff 解耦）

**问题**：U5 让无依赖任务可以并发后，reviewer 在 Task-003（backend）和 Task-007（frontend）同时 in review 时看 `git diff main...HEAD` 会看到**混合改动**，无法分辨哪行属于哪 task。

**解法**：

1. **commit 前缀约定**（落到 `agents/backend.md` / `frontend.md` / `reviewer.md`）：完成 task 前的所有 commit 必须以 `[Task-NNN]` 开头：
   ```
   [Task-003] add /api/register endpoint
   [Task-003] add unit tests for register flow
   [Task-007] update register page layout
   ```

2. **`review-hook.sh` 增强**：跑完测试后追加一行 commit 范围：
   ```
   [time] [review-hook] commits for Task-003: 3a4b5c6..f7e8d9a (3 commits)
   ```
   实现：`git log --grep="\[Task-003\]" --format=%H main..HEAD` 取首尾 hash + 计数

3. **新增 `scripts/utils/task-diff.sh`**：reviewer 看 task 隔离 diff 的快捷入口：
   - 调用：`task-diff.sh <task_id>`
   - 输出：`git diff <first_commit>^..<last_commit>` —— 仅本 task 的 commit 改动
   - `agents/reviewer.md` 新增："**看 task diff 必须用 `bash scripts/utils/task-diff.sh Task-NNN`，禁用全局 `git diff main...HEAD`**"

4. **反向检查（缺前缀报警）**：commit 缺 `[Task-NNN]` 前缀 → review-hook append：
   ```
   [time] [review-hook] ⚠ commit prefix missing: <hash> (<subject>)
   ```
   reviewer 必须打回（同 C5 触发机制）

5. **与 §5.4.3 archive-hook 协同**：归档时 `task.md` 补 `commits: <range>` 字段，方便事后回查

**与 U5 的关系**：U5 让并发可行，U6 让并发可被审查。合并实施收益最大。

---

### 5.4 脚本契约与运行模式

> 实施第 1 期开工前必须固定，否则各脚本互相对接会乱写。

#### 5.4.1 脚本接口签名

| 脚本 | 调用 | 输入 | stdout | 退出码 | 副作用 |
|---|---|---|---|---|---|
| `scripts/utils/parse-task.sh` | `parse-task.sh <task_id> [field]` | task_id 必填；field ∈ {state, type, owner, depends_on, priority, cancelled} 可选 | 缺 field → 完整 JSON；带 field → 单值 | 0 ok / 1 task 不存在 / 2 格式错（缺必填字段） | 无 |
| `scripts/utils/route.sh` | `route.sh` | 无（全表扫描 tasks.md） | 多行：`<task_id> <next_agent> <reason>`，reason ∈ {`dispatch`, `waiting_on:Task-XXX`, `skipped:invalid_state`, `skipped:circular`} | 0 ok | 无 |
| `scripts/utils/run-tests.sh` | `run-tests.sh <task_id>` | task_id 用于决定测试范围 | 单行：`failed=<N> added=<M>`（M 为本任务新增测试文件数） | 0 一律返回（失败用 stdout 表达） / 1 仅环境错（pytest/venv 不存在等） | 无 |
| `scripts/hooks/review-hook.sh` | `review-hook.sh <task_id>` | task_id | 无 | 0 ok / 1 task_id 无效 | append 一行到 `shared/current/status.md` |
| `scripts/hooks/archive-hook.sh` | `archive-hook.sh <task_id>` | task_id | 无 | 0 ok / 1 task 不存在 / 2 state≠done / 3 archive 目录已存 | 见 §5.4.3 |
| `scripts/send-to-agent.sh` | `send-to-agent.sh <agent> <prompt_file>` | agent ∈ {planner, backend, frontend, reviewer}；prompt 从**文件**读避免 shell 转义 | 无 | 0 ok / 1 window 不存在 / 2 window 非 idle（capture-pane 末行非 prompt 符号） | `tmux send-keys` |

#### 5.4.2 run-tests.sh 细节

- **cwd**：项目根 `~/learn/AI项目/multi-agent-coach`
- **后端**：`cd backend && source .venv/bin/activate && pytest -q --tb=no`，解析尾行 `N failed, M passed`
- **前端**：仅当 `git diff --name-only main...HEAD` 涉及 `html/` 时跑（具体命令实施期补；当前项目无前端测试栈）
- **`added` 计数**：`git diff --name-only --diff-filter=A main...HEAD -- 'backend/tests/**' 'tests/**' | wc -l`
- **venv 缺失**：退出码 1，stderr 提示，control-plane 视作环境错并 append `.cockpit-health.md`

#### 5.4.3 archive-hook.sh 归档物

归档目录 `shared/archive/Task-NNN-<slug>/`，含：

```
Task-NNN-<slug>/
├── task.md          # 从 tasks.md 截取该 Task 段（含所有字段，包括 cancelled、cancelled_reason）
├── status.md        # 从 status.md 过滤所有含 `Task-NNN` 的行
├── review.md        # 从 review.md 截取 `### Task-NNN` 段
└── decisions.txt    # 列出该 Task 在 status.md 里引用的 decisions/*.md 文件名（仅引用，不拷贝）
```

归档完成后重置 current/：
- `tasks.md`：删除该任务段，保留其余任务
- `status.md`：**保留全文**（append-only 时间线整体 >500 行时按 C3 滚动归档到 `archive/status-log-<date>.md`）
- `review.md`：删除该任务段
- `next-action.md`：删除该任务段

#### 5.4.4 control-plane.sh 运行模式

- **运行方式**：守护进程 `while true; do route+dispatch; sleep 2; done`
- **PID 锁**：启动写 `shared/current/.cockpit.pid`，已存在且进程仍活 → 拒绝启动并报错；进程已死则覆盖
- **退出信号**：`trap SIGINT SIGTERM` → 清 `.cockpit.pid` + 在 status.md append `[time] [cockpit] stopped`
- **崩溃自愈**：cockpit 下 pane 用 `until ./scripts/control-plane.sh; do sleep 5; done` 包裹，自动重启
- **日志**：stdout 直出到 cockpit pane；致命错另 append 到 `.cockpit-health.md`
- **首次启动 vs 重连**：启动时对 4 个 agent window 各跑一次"是否已 bootstrap"检测——`tmux capture-pane -p` 取末屏，若不含"我是 X 角色"则调用 `send-to-agent.sh` 发 B2 模板；含则跳过

#### 5.4.5 异常处理与恢复

**tasks.md 格式损坏**：
- `parse-task.sh` 退出码 2 时（缺必填字段、type 不在 7 个合法值、state 不在 5 个合法值），control-plane **跳过该 task 派工**，在 `.cockpit-health.md` append：
  ```
  [time] [cockpit] ⚠ task parse error: Task-NNN field=<field> error=<missing|invalid>
  ```
- planner 在 §7.4「看汇总」时统一处理 health 报警，统一在 planner window 修复

**archive 中途崩溃（原子化归档）**：
- `archive-hook.sh` 必须**原子操作**：先 `cp -r` 到 `archive/Task-NNN-<slug>.tmp/`，所有文件就位后 `mv` 去掉 `.tmp` 后缀，最后清理 current/
- 异常退出残留 `.tmp` 目录：control-plane 启动扫描 `archive/*.tmp/` → append health 报警 → 由 planner 决定（手工删 / 重试）

**tmux window 不存在 / 被关闭**：
- `send-to-agent.sh` 退出码 1（window 不存在）→ control-plane append `.cockpit-health.md` 后**跳过派工，不退出**
- bootstrap 阶段同样检测：缺 window 提示人启动 `mux start multi-agent`，不强制自动重起

**.last-dispatched 文件损坏**：
- JSON 解析失败 → 默认 dispatch 一次 + 备份原文件到 `.last-dispatched.broken-<timestamp>` + 写空 `{}` 重新开始

**status.md 写入竞态**：
- macOS / Linux `>>` 单行 append <PIPE_BUF (4096B) 是原子的（§10 已述）；超长行（罕见）必须拆成多行 append

**人/agent 并发改 tasks.md**：见 §10 风险表与协议约束

#### 5.4.6 仪表盘渲染（dashboard.sh）

cockpit 上 pane 用 `watch -n 2 ./scripts/utils/dashboard.sh` 替代直接 `cat shared/current/*.md`，避免 status.md 上百行滚屏看不过来。dashboard.sh 输出分段 + 截断：

```
═══ next-action ═══
（next-action.md 全文）

═══ tasks (active) ═══
（grep 非 done 的 Task-NNN 段，每段保留：标题 + 类型 + 状态 + 负责人 + priority + depends_on）

═══ status (last 15) ═══
（tail -15 status.md）

═══ review (current) ═══
（review.md 全文，已按 task 分段、归档时删除完结段，体积可控）

═══ health (last 5) ═══
（tail -5 .cockpit-health.md，无文件则显示 "(no warnings)"）

═══ dependency graph ═══
（route.sh --graph 输出，复用 §5.1 B5 next-action.md 里的 Dependency graph 段格式）
```

实现要点：
- 用 `printf` 分段标题（带分隔线），`grep` / `tail` 抽取内容
- 全部读操作，不写文件，不依赖 root
- 单屏渲染 >80 行时按 `head -80` 截断 + 显示 `... (truncated, 见 shared/current/<file>)`

---

## 6. 文件结构（修复后）

```
multi-agent-coach/
├── CLAUDE.md                          # 不变
├── CODEOWNERS                         # 新增（C5）：路径 → owner 映射，供 review-hook 越界检查
├── .tmuxinator/
│   └── multi-agent.yml                # 新增（U4）
├── agents/
│   ├── planner.md                     # 改：加 blocked 处理、done/archive、task ID 分配、decisions 触发
│   ├── backend.md                     # 改：状态转移更明确
│   ├── frontend.md                    # 同上
│   └── reviewer.md                    # 改：补 review.md 格式 + decision 边界
├── shared/
│   ├── current/
│   │   ├── tasks.md                   # 改：list 格式
│   │   ├── status.md                  # 改：append-only 时间线
│   │   ├── review.md                  # 改：按 task_id 分段
│   │   ├── next-action.md             # 改：按 task_id 分段
│   │   ├── .last-dispatched           # 新增：JSON 防重复派工
│   │   └── .cockpit-health.md         # 新增：调度台健康日志
│   ├── decisions/
│   └── archive/
├── scripts/                           # 所有脚本契约见 §5.4
│   ├── control-plane.sh               # 守护进程：(type, state) 路由 + send-keys + 防重复 + 死锁防护（运行模式见 §5.4.4）
│   ├── send-to-agent.sh               # tmux send-keys 封装（接口见 §5.4.1）
│   ├── hooks/
│   │   ├── review-hook.sh             # 只跑测试 + append status.md（接口见 §5.4.1）
│   │   └── archive-hook.sh            # planner 手动调用 + 重置 current/（归档物见 §5.4.3）
│   └── utils/
│       ├── parse-task.sh              # 解析 tasks.md 各字段（接口见 §5.4.1）
│       ├── route.sh                   # (type, state) → next_agent + 依赖检查 + 优先级排序（接口见 §5.4.1，U5）
│       ├── run-tests.sh               # 测试执行（细节见 §5.4.2）
│       ├── task-diff.sh               # 新增（U6）：单 task commit 范围 diff
│       └── dashboard.sh               # 新增：cockpit 仪表盘分段渲染（见 §5.4.6）
└── scripts-old/                       # 删除（git rm，老脚本通过 git history 仍可追溯）
```

---

## 7. 任务类型路由表

| state \ type | feature | refactor | bugfix | test | trivial | investigate | spike |
|---|---|---|---|---|---|---|---|
| pending | planner | planner | owner | owner | owner | reviewer | owner |
| in-progress | owner | owner | owner | owner | owner | reviewer | owner |
| review (无 decision) | reviewer | reviewer | reviewer | reviewer | — | — | — |
| review (changes-requested) | owner | owner | owner | owner | — | — | — |
| review (needs-discussion) | planner | planner | planner | planner | — | — | — |
| blocked | planner | planner | planner | planner | planner | planner | planner |
| done | planner | planner | planner | planner | planner | planner | planner |

**说明：**
- `trivial / investigate / spike` 类型**不会进入 review 状态** —— owner（或 reviewer，对 investigate）在 in-progress 阶段完成后**直接把 state 改为 done**，跳过 review。表格中标 `—` 表示这个组合不会出现。
- agent 文件里要明确这条规则，避免 owner 误把 state 改成 review。
- 任务取消：复用 `done` 状态 + 在 tasks.md 该任务段加一行 `cancelled: true`，由 planner 决定，archive 时保留这个字段作为元数据。**不新增 `cancelled` 状态**。
- **review 子路由（changes-requested）**：reviewer 在 review.md 写 `Decision: changes-requested` 时**不改 state**（保持 `review`）。control-plane 检测到 review.md 该字段后路由到 owner，唤醒 owner 二次实现；owner 改完后**把 state 改回 `review`**（不退到 in-progress），触发 reviewer 复审。这是 CLAUDE.md 5 状态机的**子状态扩展**——state 仍是 `review`，只是按 review.md 的 decision 字段细分派工对象，不破坏 State Ownership 归属表。
- **review 子路由（needs-discussion）**：reviewer 看不准时（架构歧义、设计 trade-off 需拍板）写 `Decision: needs-discussion` + 在 review.md 该段写问题清单 + **不改 state**。control-plane 路由到 planner 仲裁。planner 阅读后三选一：
  - **转化为 changes-requested**：planner 改 review.md 字段为 `changes-requested` + 附决策依据 → owner 二次唤醒
  - **直接 approved**：planner 改 review.md 字段为 `approved` + 改 state=`done` → archive
  - **拆子任务**：planner 在 tasks.md 新建子 Task-YYY，原 task state=`blocked` + `depends_on` 新子任务（走 B4 + U5）
- **owner 自标 blocked 的两条退出路径**（按 CLAUDE.md "任意 Agent 可标 blocked" 落地）：
  - **推回**：planner 介入后改 tasks.md state=`pending`，附 `changes-requested` 字段，owner 重新接手
  - **自解**：owner 自身能解除（如等待外部资源就绪）时，由 owner 直接把 state 改回 `in-progress`，control-plane 路由表自动唤醒 owner，无需 planner 介入

---

### 7.1 任务入口规则

路由表只回答"谁干"，不回答"谁创建任务、type 谁标"。补齐规则：**人在 pending 状态的 next_agent 对应的 window 说话**。

| type | 入口 window | tasks.md 由谁写入 | type 谁标 | owner 谁定 | 是否经 planner 拆分 |
|---|---|---|---|---|---|
| feature | planner | planner | planner | planner | 是 |
| refactor | planner | planner | planner | planner | 是 |
| bugfix | backend / frontend | owner | 人输入时显式标注 | 自己（owner） | 否 |
| test | backend / frontend | owner | 人输入时显式标注 | 自己（owner） | 否 |
| trivial | backend / frontend | owner | 人输入时显式标注 | 自己（owner） | 否 |
| investigate | reviewer | reviewer | 人输入时显式标注 | 自己（reviewer） | 否 |
| spike | backend / frontend | owner | 人输入时显式标注 | 自己（owner） | 否 |

**人类口语示例**：
- feature: 在 planner window 打 "加一个注册接口"
- bugfix: 在 backend window 打 "修一下登录接口 500 报错（bugfix）"
- refactor: 在 planner window 打 "把 auth 模块拆成 service + repo 两层（refactor）"
- test: 在 backend window 打 "给 OrderService 补单元测试（test）"

**type 兜底**：
- 人没标 type → 接收 window 的 agent 默认按 `feature` 处理，但**首条响应必须在 status.md append 一行** `[time] [agent] Task-NNN type confirmed: <type>`，再开始写 tasks.md
- type 不在 7 个合法值内 → control-plane 视作 `feature`，在 `.cockpit-health.md` 报警

---

### 7.2 各 type 的执行差异

路由表只决定"谁干"，type 还影响"怎么干"。下表列出 owner 和 reviewer 在不同 type 下的关键差异，**需要落到对应 `agents/*.md`**：

| type | owner 侧重 | reviewer 检查点 | 是否进 review |
|---|---|---|---|
| feature | 设计 → 实现 → 单测 + 集测 | diff 符合需求、测试覆盖、API 契约一致 | 是 |
| refactor | 不改行为只改结构；现有测试零失败；原则上不新增测试 | **行为等价**：现有测试零失败 + diff 无新公开符号 / 新分支语义 | 是 |
| bugfix | **先写一个能稳定复现的失败测试**，再让它 pass | status.md 含 evidence 两行（见下）+ diff 只动必要文件 | 是 |
| test | 只动测试 / 测试夹具，不改业务代码 | diff 仅在测试树内；新测试有意义（非 mock-only 套娃） | 是 |
| trivial | 完成即标 done，跳 review | — | 否 |
| investigate | 调查、结论写 status.md，不改代码 | — | 否（reviewer 自己 owner + done） |
| spike | 实验性代码、不强制测试覆盖、结论写 status.md | — | 否 |

**bugfix 的强制 evidence**：owner 完成时 status.md 必须包含两行，缺一就 reviewer 直接 `changes-requested`：

```
[time] [backend] Task-NNN regression test added: <test_id> (failing on base commit)
[time] [backend] Task-NNN fix applied, regression test now passing
```

**review-hook.sh 按 type 走不同断言**：

| type | 通过条件 |
|---|---|
| refactor | 0 failed **且** 0 added |
| test | 0 failed **且** ≥ 1 added |
| 其它 | 0 failed |

review-hook 把 type 与计数一并 append：

```
[time] [review-hook] tests for Task-NNN (type=refactor): 0 failed, 0 added → ok
```

---

### 7.3 agents/*.md 需要新增的章节

| 文件 | 新增章节 |
|---|---|
| `agents/planner.md` | 「被唤醒的标准动作」（顺序读 CLAUDE.md → planner.md → tasks.md → status.md → shared/decisions/） + 「任务入口职责」（feature / refactor 入口） + 「type 兜底确认」 + 「blocked 处理流程」（已在 §5.1 B4 给出，需照搬到 planner.md） |
| `agents/backend.md` | 「被唤醒的标准动作」（同 planner，角色文件换 backend.md） + 「任务入口职责」 + 「bugfix evidence 要求」 + 「refactor 行为等价要求」 + 「test 类型边界」 + **「in-progress 阶段自标 blocked 的动作」**（state→blocked + 在 status.md append 三行：阻塞原因 / 所需协助 / 下一步行动） + **「自解阻塞回 in-progress 的条件」** + **「收到 changes-requested 后改完直接把 state 改回 review，不退 in-progress」** |
| `agents/frontend.md` | 同 backend（按前端边界裁剪） |
| `agents/reviewer.md` | 「被唤醒的标准动作」（额外读 shared/current/review.md） + 「按 type 走的检查点」 + 「investigate 入口职责」 + 「changes-requested 的强制触发条件」 + **「写 changes-requested 时保持 state=review 不变，由 control-plane 子路由唤醒 owner」** |

**C5 / U6 在 agents/*.md 的增量**（与上表合并实施）：
- `backend.md` / `frontend.md` 加「**完成 task 前所有 commit 必须以 `[Task-NNN]` 开头**」（U6）
- `reviewer.md` 加「**看 task diff 必须用 `bash scripts/utils/task-diff.sh Task-NNN`，禁用全局 `git diff main...HEAD`**」（U6）
- `reviewer.md` 加「**review-hook 输出含 `ownership violation` 时必须 changes-requested**」（C5）
- `reviewer.md` 加「**review-hook 输出含 `commit prefix missing` 时必须 changes-requested**」（U6）

---

### 7.4 人手动干预入口

人的非派工动作（取消、改 type、改优先级、强制重派、加/解依赖、看汇总）统一在 **planner window** 说，planner 兼任「人机指令翻译」。这样人只需要记一个口子，不再被迫切窗。

| 人想做什么 | 在哪个 window 说 | 怎么说（自然语言） | planner 的动作 |
|---|---|---|---|
| 取消任务 | planner | "取消 Task-NNN（原因：...）" | tasks.md 该段 state=`done` + `cancelled: true` + `cancelled_reason: ...`；append status.md |
| 改 type | planner | "把 Task-NNN type 改成 refactor" | 改 tasks.md type 字段；若已过 in-progress，append status.md 历史 type 说明；review-hook 下一轮按新 type 走断言 |
| 改优先级 | planner | "把 Task-NNN priority 改成 high" | 改 tasks.md priority；下一轮 route.sh 自动重排 |
| 强制重派 | planner | "强推 Task-NNN" | 删 `.last-dispatched` 中该 task 条目，触发 control-plane 重新派工 |
| 加依赖 | planner | "Task-005 要等 Task-003 done" | Task-005 段加 `depends_on: Task-003 (state>=done)`；append status.md |
| 解依赖 | planner | "解除 Task-005 的依赖" | Task-005 段删 `depends_on` 字段 |
| 看汇总 | planner | "现在还有什么任务" | 读 tasks.md + next-action.md 口头总结；**不改任何文件** |

**为什么统一在 planner 窗口**：
- 这些动作都是「任务管理」语义，归 planner 职责（CLAUDE.md State Ownership 表）
- 人只需记一个口子，不必再思考"该去哪"——核心目标"少切窗"的最后一公里
- 不破坏路由表：人在 planner 窗口说话本身不会触发派工；是 planner 改 tasks.md 后，control-plane 下一轮检测变化再走标准流程

**例外（保留 §7.1 不变）**：bugfix / test / trivial / spike / investigate 的**新建任务**仍在各 owner window 说——属于"派工流"而非"管理流"。

**反向验收**：人在 backend window 说"取消 Task-003" → backend agent 应回复"任务管理请去 planner window"并**不改任何文件**；若 backend 自行改 tasks.md 取消任务，reviewer 在最终 review 时标 `changes-requested` 指出越权。

---

## 8. 验收条件

修完之后，下面 **三个** 端到端场景必须都能跑通。全程你只在 cockpit 看，**不需要手动切窗口派工**。

### 8.1 Feature 流程验收

1. 启动：`mux start multi-agent` → 5 个 window 起来，每个 agent window 显示"我是 X 角色，等待派活"
2. 你在 planner window 打："加一个 GET /api/health 接口"
3. planner agent 自动：
   - 在 status.md append `[time] [planner] Task-NNN type confirmed: feature`
   - 在 tasks.md 新增 Task-NNN（类型 feature、状态 pending、负责人 backend）
   - 在 status.md append `[time] [planner] Created Task-NNN`
4. cockpit 仪表盘下一轮（2 秒内）：
   - 显示 Task-NNN，state=pending
   - next-action.md 显示 "Agent: backend"
   - 调度台 pane 输出 "send-keys to backend"
5. backend window 自动出现唤醒指令 + 唤醒后开始写代码 + 跑测试 + 把 state 改成 review
6. cockpit 显示 review-hook 自动跑 + 测试 `0 failed → ok`
7. reviewer window 自动被唤醒 + 写 review.md (approved) + state 改为 done
8. planner window 自动被唤醒 + 跑 archive-hook + Task-NNN 移到 archive/
9. cockpit 仪表盘清空当前任务，等下一个

**反向验收（必须能被挡住）**：
- reviewer 写 `Decision: changes-requested` 且**不改 tasks.md state**（保持 `review`）→ 下一轮调度台 pane 输出 "send-keys to backend"（按 review 子路由）→ backend window 自动收到唤醒指令 → backend 改完代码后**把 state 改回 `review`**（不进 in-progress）→ reviewer 二次唤醒 → review.md 改写为 `approved` → state=done → planner 自动归档。**全程不切窗口**。
- 故意让 reviewer 把 state 改成 `in-progress` 而不是用 changes-requested 子路由 → control-plane 在 `.cockpit-health.md` 报警「非法 state 转移：review → in-progress」，不派工，等人介入。
- 故意让 owner 收到 changes-requested 后把 state 改成 `in-progress` 而不是直接改回 `review` → control-plane 同上报警「review 子路由违规：owner 应改回 review 而非 in-progress」。

### 8.2 Bugfix 流程验收

1. 你在 backend window 打："修一下 `/api/login` 在邮箱含 `+` 号时返回 500（bugfix）"
2. backend agent 自动：
   - 在 status.md append `[time] [backend] Task-NNN type confirmed: bugfix`
   - 在 tasks.md 新增 Task-NNN（类型 bugfix、状态 in-progress、负责人 backend）—— pending 跳过
   - 写一个能复现的失败测试 `test_login_email_with_plus`
   - 在 status.md append `[time] [backend] Task-NNN regression test added: test_login_email_with_plus (failing on base commit)`
   - 改代码让该测试 pass
   - 在 status.md append `[time] [backend] Task-NNN fix applied, regression test now passing`
   - state 改为 review
3. review-hook 跑测试，status.md 出现 `tests for Task-NNN (type=bugfix): 0 failed → ok`
4. reviewer window 被唤醒 → 在 status.md 找到 evidence 两行 → review.md approved → state=done
5. planner window 被唤醒 → archive

**反向验收（必须能被挡住）**：
- 故意删掉 evidence 两行其中一行 → reviewer 必须输出 `changes-requested`
- 故意不先写回归测试就改代码 → reviewer 在 diff 中看不到新测试文件，必须 `changes-requested`

### 8.3 Refactor 流程验收

1. 你在 planner window 打："把 `auth_service.py` 里的 `validate_token` 拆成 `parse` + `verify` 两个纯函数（refactor）"
2. planner agent 自动：
   - 在 status.md append `[time] [planner] Task-NNN type confirmed: refactor`
   - 在 tasks.md 新增 Task-NNN（类型 refactor、状态 pending、负责人 backend）
   - 在 status.md append `[time] [planner] Created Task-NNN`
3. backend window 被唤醒 → 改代码（不动行为）→ 跑现有测试集 → 不新增测试 → state 改 review
4. review-hook 跑测试，status.md 出现 `tests for Task-NNN (type=refactor): 0 failed, 0 added → ok`
5. reviewer window 被唤醒：
   - 看 diff：确认无新公开符号、无新条件分支语义
   - 看 status.md 测试结果
   - review.md approved → state=done
6. planner window 被唤醒 → archive

**反向验收（必须能被挡住）**：
- 现有测试集出现 ≥ 1 失败 → reviewer `changes-requested`
- diff 引入新公开符号或新分支 → reviewer 标 `changes-requested` 或要求 planner 把 type 改成 feature 重走流程

---

### 8.4 Blocked 流程验收

覆盖 CLAUDE.md「任意 Agent 可标 blocked」+ 两条退出路径。

**Case A — owner 在 in-progress 中标 blocked，planner 推回**：

1. 你在 planner window 打："加一个支付回调接口（feature）"（feature 是为了走 planner 拆任务；现实里 bugfix/test 也可由 owner 直接遇到阻塞）
2. planner 创建 Task-NNN（feature/pending/backend）
3. backend 被唤醒，state → in-progress；中途发现依赖 `payment_gateway_sdk` 未引入
4. backend 自动：
   - tasks.md Task-NNN state → `blocked`
   - status.md append 三行：
     ```
     [time] [backend] Task-NNN blocked: payment_gateway_sdk 未引入
     [time] [backend] Task-NNN needs: planner 决定引入哪个 SDK 与版本
     [time] [backend] Task-NNN next: 等待 planner 唤醒
     ```
5. cockpit 下一轮（2 秒内）：next-action.md 显示 "Agent: planner"，调度台 pane 输出 "send-keys to planner"
6. planner window 自动被唤醒 → 读 status.md 找 blocker → 在 `shared/decisions/` 写一份决策（选 SDK X 版本 Y）→ tasks.md Task-NNN state 改回 `pending`，附 `changes-requested: 使用 SDK X` 字段
7. cockpit 下一轮：next-action.md 切回 backend → backend 二次唤醒 → 看 changes-requested 字段 → 引入 SDK → state → `in-progress` → 完成 → state → `review`
8. 后续走标准 review → done → archive

**Case B — owner 自解阻塞**：

1. 同 Case A 步骤 1-4，backend 阻塞原因写"等待外部接口联调（预计 1 小时内可用）"
2. planner 被唤醒 → 读 status.md → 决定**不介入**，只 append `[time] [planner] Task-NNN: 等待外部依赖，由 backend 自行恢复`，**不动 tasks.md state**
3. 1 小时后外部接口就绪，人在 backend window 输入"外部接口已可用"
4. backend 自动：tasks.md state 改回 `in-progress`，status.md append `[time] [backend] Task-NNN unblocked, resume`
5. cockpit 下一轮：调度台按 in-progress 路由唤醒 backend → 继续到 review → done

**反向验收（必须能被挡住）**：
- backend 标 blocked 但 status.md 缺三行 evidence（原因 / 所需协助 / 下一步行动）→ planner 必须 append `[time] [planner] Task-NNN blocker 信息不全，要求 backend 补全`，并把 state 改回 `in-progress` 让 backend 重写阻塞说明
- planner 在 Case B 下擅自改 state（明明 backend 说自解，却改成 pending 推回）→ control-plane 不报警（无机器规则可挡），但 reviewer 在最终 review 阶段可在 review.md 指出"planner 越权干预自解流程"
- planner 处理 blocked 时直接改 state=`done` 且任务无 `cancelled: true` 字段 → archive-hook 检测到 state 流转跳过 review，在 `.cockpit-health.md` 报警并拒绝归档

---

### 8.5 跳过 review 的 type 验收（trivial / investigate / spike）

覆盖 §7.2「不进 review」三类，验证 owner 在 in-progress 完成后**直接改 state=done**，control-plane 跳过 reviewer 直接唤醒 planner archive。

**Case A — trivial**：

1. 你在 backend window 打："把 `config.py` 里的注释错别字改一下（trivial）"
2. backend agent 自动：
   - status.md append `[time] [backend] Task-NNN type confirmed: trivial`
   - tasks.md 新增 Task-NNN（trivial / in-progress / backend）—— pending 跳过
   - 改完代码 + commit `[Task-NNN] fix typo in config.py comment`
   - **直接** state → `done`（不进 review）
   - status.md append `[time] [backend] Task-NNN done (trivial, skip review)`
3. cockpit 下一轮：next-action.md 显示 "Agent: planner"
4. planner 被唤醒 → 跑 archive-hook → Task-NNN 归档

**Case B — investigate**（owner 是 reviewer 的特殊路径）：

1. 你在 reviewer window 打："调查最近 prod 报的 X 错误是不是数据库连接池满（investigate）"
2. reviewer agent 自动：
   - status.md append `[time] [reviewer] Task-NNN type confirmed: investigate`
   - tasks.md 新增 Task-NNN（investigate / in-progress / **reviewer**）—— owner 是自己
   - 看日志 + 跑诊断查询 + **不改业务代码**
   - 结论写 status.md：`[time] [reviewer] Task-NNN findings: 连接池上限 50，prod 峰值 47，未到上限。真因是慢查询导致连接持有时间长。建议 follow-up: 加慢查询监控`
   - state → `done`
3. planner 被唤醒 → archive；如有 follow-up 建议，planner 在 archive 后**新建** Task-MMM（type=feature/bugfix 按 finding 决定）

**Case C — spike**：

1. 你在 backend window 打："试试用 SSE 替代 WebSocket 推送，看可行性（spike）"
2. backend agent 自动：
   - status.md append `[time] [backend] Task-NNN type confirmed: spike`
   - tasks.md 新增 Task-NNN（spike / in-progress / backend）
   - 写实验代码 + **不强制测试覆盖**
   - 结论写 status.md：`[time] [backend] Task-NNN spike conclusion: SSE 可行但 Nginx 需关 buffering，推荐方案 A...`
   - state → `done`
3. planner 被唤醒 → archive；planner 决定是否基于 spike 结论新建后续 feature task

**反向验收（必须能被挡住）**：
- 三个 type 中任一 owner 把 state 改成 `review`（违反 §7.2 表）→ control-plane 在 `.cockpit-health.md` 报警「invalid state transition: <type> 不应进 review」并跳过派工
- investigate 任务 owner 不是 reviewer（人错放到 backend window）→ planner 在兜底确认时纠正 owner 为 reviewer，或在 status.md 拒绝创建并请人改去 reviewer window
- spike 任务的 commit 改了业务代码但 status.md 无 `spike conclusion` 行 → planner archive 时拒绝（`.cockpit-health.md` append 警告，等 owner 补结论）

---

## 9. Non-Goals

- 不在本次修复里做：多 CLI 混搭（codex/gemini），先全 Claude Code
- 不做：任务**抢占**（高优先级强制中断 owner 当前任务）与**跨 agent 依赖预热**——基础依赖语义与优先级排序见 §5.3 U5
- 不做：跨 git worktree 的 multi-branch 协同
- 不做：把 scripts-old/ 内容迁移成新框架的"参考实现"，直接 git rm 删除（git history 仍可追溯）

---

## 10. 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| tmux send-keys 在 Claude Code TUI 里被识别成键盘输入冲突（agent 正在输入时被打断） | 唤醒失败或输入串台 | 在 send-keys 前检查 agent window 是否 idle（通过 tmux capture-pane 看最后一行是不是 prompt 符号）；不 idle 就跳过本轮，下一轮重试 |
| 多 agent 同时 append status.md | 极小概率的写入交错 | macOS 上 `>>` 是原子的（小于 PIPE_BUF 4096 字节），单行写入安全 |
| **人在某 agent window 输入指令时，该 agent 正在写 tasks.md / status.md** | 文件中途状态 + agent 收到打断 | 协议级：agent 写共享文件只用单次 `>>` 或一次 `Edit` 调用完成（缩短时窗）；人优先级高可直接打断；被打断的 agent 在下一轮唤醒时**先读 status.md 与 tasks.md 当前状态**，与中断前预期对比，决定续做 / 重做 / 放弃 |
| Claude Code session 跑久了 context 爆 | 影响 agent 长期可用 | agent 完成任务后 `/clear`，下次被唤醒重新加载上下文（成本：每轮重读角色文件） |
| .last-dispatched 文件损坏 | 调度台无法判断重复 | 损坏时默认 dispatch 一次 + 备份 + 报警（见 §5.4.5） |
| **archive-hook 中途崩溃残留 .tmp 目录** | 归档不完整 | 原子化：先 `cp -r` 到 `archive/Task-NNN-<slug>.tmp/`，再 `mv` 改名；control-plane 启动扫描残留 `.tmp` 让 planner 决定（见 §5.4.5） |

---

## 11. 实施分期

| 期 | 内容 | 期望产出 |
|---|---|---|
| **第 1 期 (P0)** | B1（含唤醒模板补 `shared/decisions/` + reviewer 额外读 `review.md` + state 改写例外说明）+ B2+B3+B4+**B5（next-action / review 分段格式）** + U4 + **§5.4 脚本契约与运行模式 + §7 路由表 changes-requested 子路由 + owner 自标 blocked 双路径 + §7.3 中 planner/backend/frontend/reviewer 的「被唤醒标准动作」「blocked 处理」「changes-requested 处理」章节（提前到此期） + §7.1 入口规则 + §7.4 人手动干预入口 + §8.1 Feature 验收（含 changes-requested 反向） + §8.4 Blocked 双路径验收** | 流程能从 0 跑到 done，处理 **changes-requested 回退**与 **blocked 双退出路径**；脚本契约固定，人在 planner 窗口完成所有管理动作；feature 单任务 + blocked demo 可过 |
| **第 2 期 (P1)** | C1+C2+C3+C4+**C5（CODEOWNERS 越界检查，与 C1 合并实施）** + **§7.2/7.3 其余各 type 执行差异 + §8.2/8.3 Bugfix/Refactor 验收** | 流程不再违反 CLAUDE.md，reviewer 真正参与，**bugfix / refactor / test 流程可用**；agent 越界改动可被机器检测 |
| **第 3 期 (P2)** | U1+U2+U3+U5+**U6（task-commit 前缀关联，与 U5 合并实施）** | 日常可用，**任务依赖 + 优先级排序 + 循环依赖检测 + 多任务并发 review 的 diff 解耦**，死锁防护 |

第 1 期结束就能 demo（feature），第 2 期结束 bugfix / refactor / test 也能跑通，第 3 期结束就能日常用。
