# Multi-Agent Cockpit MVP 设计

**Date:** 2026-05-29
**Status:** Draft
**Scope:** 在 `.ai/` 框架下补齐首跑所必需的最小文件集，跑通一次端到端任务，验证 5 角色协作 + status.json 同步 + cockpit 只读总览。不挂任何 hook、不上 bus、不复用 `scripts-old1/`。

---

## 1. 背景与现状（已核对每个文件的字节数）

### 1.1 有内容的（可直接用）

| 文件 | 行数 |
|---|---|
| `CLAUDE.md` | 完整，含 Agent 运行协议 |
| `.ai/README.md` | 8821 字符，系统总览 |
| `.ai/agents/README.md` | 138 行，定义 Agent 8 段 schema |
| `.ai/agents/planner.md` | 66 行，但用的是 5 段而非 8 段（**需重写**，见 §5.5） |
| `.ai/memory/decisions.md` | 64 行 |
| `.ai/workflows/README.md` + 7 个 yaml | 113 + 35-54 行/个 |

### 1.2 空文件（0 字节，必须补或明确缓补）

| 文件 | 首跑必需？ | 处理 |
|---|---|---|
| `.ai/agents/backend.md` | 是 | 本次补 |
| `.ai/agents/frontend.md` | 否（TASK-001 不用） | 本次补（schema 一致性） |
| `.ai/agents/reviewer.md` | 是 | 本次补 |
| `.ai/agents/tester.md` | 是 | 本次补 |
| `.ai/prompts/status-template.json` | 是 | 本次补 |
| `.ai/prompts/handoff-template.md` | 是 | 本次补 |
| `.ai/prompts/task-template.md` | 否 | 首跑后复盘再补 |
| `.ai/prompts/plan-template.md` | 否 | 首跑后复盘再补 |
| `.ai/prompts/review-template.md` | 否 | 首跑后复盘再补 |
| `.ai/memory/project.md` 等 9 个 | 否（按 CLAUDE.md 加载矩阵 TASK-001 不触发任何 memory） | 复盘后按需补 |

### 1.3 待清理 / 替换

| 路径 | 状态 |
|---|---|
| `.tmuxinator/multi-agent.yml` cockpit window 引用 `scripts-old1/` | 必须重写 |
| `scripts-old1/` 旧调度脚本 | **本次完全不复用**，不参考、不调用 |

## 2. 设计目标

跑通一次端到端任务，回答三个问题：

1. **5 角色 + status.json 这套约定能不能真的串起来？**
2. **cockpit 只读总览（不挂 hook）能解决多少切换痛？**
3. **下一步该把 hook 挂在哪几个状态点？**

## 3. Non-Goals

- 不挂任何 hook（Phase 4 是下一步）
- 不做 agent 间自动通信 / bus（Phase 5）
- 不写 workflow 自动驱动引擎（人按 `.ai/workflows/feature.yaml` 走）
- 不补 `.ai/prompts/{task,plan,review}-template.*`
- 不补 `.ai/memory/*`（保留空文件占位）
- 不复用 `scripts-old1/` 任何脚本
- frontend window / frontend.md 内容写但首跑不参与（TASK-001 不涉及 UI）

## 4. 架构

### 4.1 Workspace 形态

```
WezTerm 窗口
  └── tmux session: multi-agent
        ├── window 0: cockpit
        │     └── 单 pane: watch -n 2 .ai/dashboard/cockpit.sh
        ├── window 1: planner    $ claude
        ├── window 2: backend    $ claude
        ├── window 3: reviewer   $ claude
        └── window 4: tester     $ claude
```

变化点（相对当前 `.tmuxinator/multi-agent.yml`）：

- cockpit 的 3 个 pane（含 `dashboard.sh`、`cockpit-input.sh`、`control-plane.sh`）全删，换成 1 个 pane 跑 `watch -n 2 .ai/dashboard/cockpit.sh`
- frontend window 删除（首跑不需要，文件留着）
- 新增 tester window

### 4.2 同步契约

`.ai/tasks/TASK-XXX/status.json` 是 5 个角色之间**唯一**的同步源。其他文件（`plan.md` / `checklist.md` / `review.md` / `handoff.md`）是产出物，不参与状态同步。

**最小 schema：**

```json
{
  "task_id": "TASK-001",
  "state": "TODO",
  "current_owner": "planner",
  "next_owner": null,
  "updated_at": "2026-05-29T12:00:00+08:00",
  "blockers": [],
  "notes": ""
}
```

字段约定：

| 字段 | 类型 | 取值 |
|---|---|---|
| `task_id` | string | `TASK-NNN` 三位数字 |
| `state` | enum | `TODO` / `PLANNED` / `IN_PROGRESS` / `REVIEW` / `TESTING` / `DONE` / `BLOCKED` |
| `current_owner` | enum | `planner` / `backend` / `frontend` / `reviewer` / `tester` |
| `next_owner` | enum 或 null | 同上，`DONE` 时为 null |
| `updated_at` | string | ISO8601，含时区 |
| `blockers` | string[] | 阻塞原因列表，空数组表示无阻塞 |
| `notes` | string | 自由文本，给 cockpit 显示用 |

每个角色干完自己那段后：

1. 改 `status.json`（state / current_owner / next_owner / updated_at）
2. 追加 `handoff.md`（按 `.ai/prompts/handoff-template.md` 格式）

**不在最小 schema 里**：进度百分比、子任务列表、机器可读的事件流。首跑后复盘再决定要不要加。

### 4.3 状态流转（首跑路径）

```
planner: TODO → PLANNED (current=planner, next=backend)
backend: PLANNED → IN_PROGRESS → REVIEW (current=backend, next=reviewer)
reviewer: REVIEW → TESTING (current=reviewer, next=tester)
tester:  TESTING → DONE (current=tester, next=null)
```

异常分支（BLOCKED）暂不在首跑路径内——如果首跑过程中真的卡住了，手动改 state=BLOCKED + 写 blockers 数组，但不专门设计回滚流程。

## 5. 组件

### 5.1 `.ai/dashboard/cockpit.sh`

**职责：** 扫所有 task 的 status.json，打印一张表。

**输入：** `.ai/tasks/*/status.json`

**输出：** stdout 一张文本表格

**约束：**

- 纯 bash + `jq`，不依赖任何 Python / Node
- 失败要静默（某个 status.json 损坏不要让整个表崩）
- 表格列固定：`TASK | STATE | OWNER → NEXT | UPDATED | BLOCKERS | NOTES`
- 时间显示成"X 分钟前"而不是 ISO 时间戳
- 没有任何 task 时打印 `(no tasks yet)`

**约 30 行**，单文件。新写，不参考 `scripts-old1/utils/dashboard.sh`。

### 5.2 `.tmuxinator/multi-agent.yml`（改）

替换 cockpit window 的 3 pane 配置为单 pane；删除 frontend window；新增 tester window。其余不动。

### 5.3 `.ai/tasks/TASK-001/`

**任务内容：** 给项目根 `README.md` 加一段"当前 5-Phase 系统状态说明"。

**为什么选这个：**

- 真产出，跑完留下东西
- 4 个角色都有真活：planner 拆段落结构 / backend 写正文 / reviewer 核事实是否与 `.ai/` 现状一致 / tester 检查 markdown 渲染和链接
- 不涉及 UI，frontend 不参与
- 风险低（只改 README），跑挂了不伤主代码

**初始文件（planner 进 window 前）：**

- `task.md` —— 由 spec 作者人工写一版（无模板，照 §5.3.1 骨架）
- `status.json` —— 按 §4.2 schema 初始化为 `TODO` / `current_owner=planner`

`plan.md` / `checklist.md` / `review.md` / `handoff.md` 由各 agent 在自己阶段创建。

**§5.3.1 task.md 骨架：**

```md
# TASK-001 给 README 加 5-Phase 当前状态说明

## 背景
（描述 multi-agent-coach 已有 .ai/ 框架的现状）

## 目标
给 README.md 新增一段，说明 5 个 Phase 当前各自的完成度。

## 验收
- README.md 顶部或合适位置新增段落
- 段落内容与 .ai/ 实际目录状态一致
- markdown 渲染无破

## Workflow
.ai/workflows/feature.yaml
```

### 5.4 `.ai/agents/{backend,frontend,reviewer,tester}.md`（新写）

全部按 `.ai/agents/README.md` 第 9-30 行定义的 **8 段 schema**：

```
# <Agent Name>

## Role
## Responsibilities
## Inputs
## Outputs
## Read Before Start
## Workflow Responsibilities
## Rules
## Handoff
```

每个文件目标长度：30-60 行。不展开示例，由实施阶段一次写完。

### 5.5 `.ai/agents/planner.md`（重写）

当前 planner.md 用的是 5 段（Mission / Think First / Output / Never / Handoff），与 README.md 的 8 段不一致。**重写为 8 段**，内容保留（5 段实际上是 8 段的子集，能映射）。

### 5.6 `.ai/prompts/status-template.json`（新写）

内容就是 §4.2 的最小 schema 的占位版：

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

### 5.7 `.ai/prompts/handoff-template.md`（新写）

固定 5 段，给所有角色用：

```md
## <Agent> @ <ISO8601>

### Completed
- ...

### Pending
- ...

### Risks
- ...

### Blockers
- ...

### Next Step
- 下一负责人：<agent>
- 下一动作：...
```

handoff.md 是追加的——每个 agent 在文件末尾加一段。

### 5.8 Bootstrap 句子（不入文件，spec 内嵌）

首跑时用户在每个 window 启 claude 后，粘贴对应句子。**4 句固定文本如下**：

**planner window：**
```
你是 planner。读 CLAUDE.md → .ai/README.md → .ai/agents/planner.md →
.ai/workflows/feature.yaml → .ai/tasks/TASK-001/task.md，进入 planning 阶段：
写 .ai/tasks/TASK-001/plan.md 和 checklist.md，
改 status.json 为 PLANNED / next_owner=backend，追加 handoff.md。
```

**backend window：**
```
你是 backend。读 CLAUDE.md → .ai/agents/backend.md →
.ai/tasks/TASK-001/{task.md, plan.md, handoff.md}，进入 implementation 阶段：
按 plan.md 改 README.md，改 status.json 为 REVIEW / next_owner=reviewer，追加 handoff.md。
```

**reviewer window：**
```
你是 reviewer。读 CLAUDE.md → .ai/agents/reviewer.md →
.ai/tasks/TASK-001/{plan.md, handoff.md} + README.md 的 diff，进入 review 阶段：
写 review.md，改 status.json 为 TESTING / next_owner=tester（或 IN_PROGRESS 退回 backend），
追加 handoff.md。
```

**tester window：**
```
你是 tester。读 CLAUDE.md → .ai/agents/tester.md →
.ai/tasks/TASK-001/{plan.md, review.md, handoff.md} + README.md，进入 testing 阶段：
渲染检查 + 链接检查，改 status.json 为 DONE / next_owner=null，追加 handoff.md。
```

首跑后复盘时决定要不要把这 4 句固化成 `.ai/tools/bootstrap-*.txt` 或自动 send-keys。

## 6. 数据流

```
用户在 planner window 粘 bootstrap 句子
        ↓
planner 读上下文 → 写 plan.md / checklist.md → 改 status.json → 追加 handoff.md
        ↓
cockpit 2 秒后刷新出 PLANNED
        ↓
用户切到 backend window，粘 bootstrap 句子
        ↓
backend 读 plan.md / handoff.md → 改 README.md → 改 status.json → 追加 handoff.md
        ↓
cockpit 刷新出 REVIEW
        ↓
用户切到 reviewer window，粘 bootstrap 句子
        ↓
reviewer 读 diff → 写 review.md → 改 status.json → 追加 handoff.md
        ↓
cockpit 刷新出 TESTING
        ↓
用户切到 tester window，粘 bootstrap 句子
        ↓
tester 渲染检查 → 改 status.json (DONE) → 追加 handoff.md
        ↓
cockpit 刷新出 DONE
```

**人介入点（也是 hook 候选）：** 4 次"用户手动切窗口 + 粘 bootstrap 句子"。

## 7. 错误处理

| 场景 | 处理 |
|---|---|
| `status.json` 损坏 / 字段缺失 | cockpit 跳过这个 task，不让整张表崩 |
| 某 agent 改完代码但忘了改 `status.json` | cockpit 显示 `updated_at` 不变，用户看出"卡住"后手动到那个 window 提醒 |
| 多个 agent 同时改同一 `status.json` | 首跑串行不会发生；如果真撞了，git 兜底，复盘时记录 |
| `BLOCKED` 状态 | 任意 agent 手动改 state=BLOCKED，blockers 数组写原因，cockpit 高亮显示 |
| Agent 进 window 后发现自己角色文件还是空 | 实施阶段已保证 4 个角色文件都写完才进入首跑；如真发生，回滚到实施 §5.4 |

不做：文件锁、事件队列、冲突合并。

## 8. 测试 / 验证

**手动验收清单（跑通 TASK-001 后逐项核）：**

- [ ] `mux start multi-agent` 启动后 5 个 window（cockpit/planner/backend/reviewer/tester）全部就绪
- [ ] cockpit 启动时显示 TASK-001 初始状态（TODO / planner）
- [ ] cockpit 每 2 秒刷新一次，时间戳"X 分钟前"正确
- [ ] 4 个角色依次跑完后，最终 `state=DONE` / `current_owner=tester` / `next_owner=null`
- [ ] `.ai/tasks/TASK-001/handoff.md` 含 4 段 handoff 记录
- [ ] README.md 已新增"5-Phase 系统状态"段落
- [ ] `cockpit.sh` 在故意损坏的 `status.json` 下不崩溃

**不做自动化测试**：本次切片产物全是 bash + markdown + json，没有可单元化的逻辑。

## 9. 复盘（跑完后必做，作为 Phase 4 输入）

跑完 TASK-001 后产出 `docs/superpowers/specs/2026-05-29-multi-agent-cockpit-mvp-retro.md`，回答：

1. 4 次"手动切窗口 + 粘 bootstrap"里，哪几次值得做成 hook 自动派工？
2. cockpit 哪几列信息不够、需要扩（git diff 行数 / 最近修改文件 / etc）？
3. status.json schema 哪些字段不够用、哪些字段从未被读过？
4. `.ai/workflows/feature.yaml` 在实际跑的时候被遵守了几条、被违反了几条？
5. 剩下没补的（3 个 prompt 模板 + 9 个 memory 文件）按本次经验，下一批先补哪些？

复盘产出会驱动 Phase 4（hooks）的 scope 决定 + 下一批 memory/prompts 补全顺序。

## 10. 实施顺序（高层，给 writing-plans 用）

按依赖正序：

1. **补底层文件**（agent 不依赖 cockpit，cockpit 依赖 schema）：
   - 1.1 写 `.ai/prompts/status-template.json`
   - 1.2 写 `.ai/prompts/handoff-template.md`
   - 1.3 重写 `.ai/agents/planner.md` 为 8 段
   - 1.4 新写 `.ai/agents/backend.md` / `frontend.md` / `reviewer.md` / `tester.md`
2. **写 cockpit**：`.ai/dashboard/cockpit.sh`
3. **改 tmuxinator**：`.tmuxinator/multi-agent.yml`
4. **本地干跑**：`mux start multi-agent` → cockpit 显示 `(no tasks yet)`
5. **建 TASK-001**：`task.md` + `status.json`（按 §5.3.1 骨架）
6. **干跑 TASK-001**：4 角色依序粘 bootstrap，跑到 DONE
7. **写复盘 spec**

每一步都可独立验证、可独立回滚。

## 11. 决策记录

| 决策 | 理由 |
|---|---|
| 选真任务而非 dummy | dummy 跑完就忘，真任务有产出动力 |
| 首跑不挂 hook | 没跑过的流程瞎挂 hook 是浪费；hook 候选要从复盘得出 |
| status.json 是唯一同步源 | 一个契约够用，多个契约一次性铺太厚 |
| 不复用 scripts-old1 | 用户明确要求；旧版逻辑与 `.ai/` 框架对不齐，重写比改更快 |
| frontend.md 写但 window 不开 | schema 一致性比 window 数节省更重要；未来真任务用得到 frontend 时直接加 window |
| cockpit 用 bash + jq | 项目里没有新运行时；30 行能写完 |
| Agent schema 选 8 段（不是 5 段） | README.md 的 8 段含 Inputs/Outputs，未来 cockpit / hook 可机械检查 outputs；planner.md 5 段需重写 |
| Prompts 只补 status + handoff | 这两个被读频次最高（cockpit 读 status，每次交接读 handoff）；其余 3 个一次性写、即兴写不影响首跑 |
| Memory 首跑不补 | TASK-001 按 CLAUDE.md 加载矩阵不触发任何 memory；空文件不阻塞 |
| Bootstrap 句子写在 spec、不入 .ai/ | 首跑要看清"哪一步必须人介入"；句子固化成文件 = 提前优化 |
