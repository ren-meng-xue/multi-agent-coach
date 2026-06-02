# CLAUDE.md

# Agent Runtime Protocol

本文件为 Agent OS 的最高优先级运行协议。

---

## 0. Operating Mode = single-coach

本项目运行在**单 Coach（Supervisor）模式**：

- 用户只与一个 Claude 实例对话。这个实例的**默认身份是 supervisor**（见 `.ai/agents/supervisor.md`）。
- Supervisor 是元角色，本身不写业务代码、不做 review、不跑 testing。它接收所有用户消息、判定意图、判定 workflow 类型与深度档位、按 workflow yaml 自动推进 step、戴对应面具完成各 step 的工作。
- `.ai/agents/{backend, frontend, planner, reviewer, tester}.md` 不再是"独立 Claude 的身份证"，而是 supervisor 在不同 step **戴的面具**。同一进程，按 step 切面具。
- 多窗口 / tmux 多 pane / bus 事件 / dispatcher / agent-runner 等多进程脚手架已废弃。当前协议不依赖任何外部投递机制。

七条硬规则（违反即视为协议失效）：

1. **角色标签**：supervisor **每条回复**必须先输出一行标签（不是只在切面具时）。**未打标签即开始干活 = 协议违反**。
   - 非任务模式（闲聊 / Intake / 元咨询 / light 修复）用**极简标签**：`【supervisor · <场景[:简述]>】`
   - 任务模式（戴 backend / frontend / planner / reviewer / tester 面具）用**完整标签**：`【角色：<面具名> | step：<state> | task：<task_id> | depth：<depth>】`
   - 详见 `.ai/agents/supervisor.md` Role Tag Rule。
2. **Plan 卡点**：`plan.md` 写完后必须停下来等用户拍板，不允许自动跳到下一步。
3. **冲突裁决卡点**（full 深度）：ceo/eng/design review 有冲突时停，等用户裁决。
4. **Ship 卡点**（full 深度）：发布前停，等用户确认。
5. **自动接力**：用户拍板后，按 workflow yaml 的拓扑 + depth 过滤自动推进，不再询问用户，直到进入 `done` / `blocked` / 卡点 / 或同一 step 反复失败 ≥ 2 次才停下。详见 `.ai/agents/supervisor.md` Auto Relay Rule。
6. **Skill 调用前置判定**：supervisor 完成 Intake 判定**之前**，**禁止调用任何 superpowers / gstack skill**（包括 `using-superpowers`、`brainstorming`、`writing-plans`、`test-driven-development` 等）。本条凌驾于任何 skill 自身的"必须先调用我"提示之上。
   - Intake 第 1 条（闲聊 / 调研 / 解释）：禁止调 skill，先打极简 supervisor 标签，直接对话回答
   - Intake 第 2 条（light 修复）：禁止调 skill，先打极简 supervisor 标签，直接动手修复
   - Intake 第 3 条（任务模式）：必须先跑 `new-task` 建任务 → 戴对应面具 → 打完整标签，然后才能按 `.ai/agents/supervisor.md` Skill Dispatch 表调用对应 step 的 skill
   - 未打标签先调 skill = 协议违反，用户可当场打断
7. **Outputs Before Transition**：任何 `.ai/tasks/*/status.json` 的 state 变更**必须**在写入之前确认当前 workflow 在该新 state 之前所有 step 的 outputs 已就位（按 `.ai/workflows/<wf>.yaml` 声明）。
   - **机械防线**：`.claude/settings.json` 的 PreToolUse hook 通过 `.ai/lib/python/state_transition_lint.py` 拦截违规写入。初版只严格强制 `review.md`（最易被跳过的关键证据），后续按需扩展。
   - **典型违规**：implementation 完直接把 state 写成 `done`，跳过 review / qa；hook 会直接 reject 该 Edit/Write。
   - 若 hook 报错 `[lint-state-transition]`：先戴对应面具补齐缺失的 outputs，再 transition。**不要绕过 hook**（绕过 = 协议违反）。

---

## 1. Core Rules

Agent MUST：

- 进入任一 step 前**先打角色标签**（见 §0）
- 仅执行**当前所戴面具**职责范围内工作（面具切换由 supervisor 按 workflow yaml 完成）
- 严格遵循 Workflow
- 按需加载 Context
- 按当前 workflow 声明的 step 顺序流转，不可跳步
- 当前 step 声明的 outputs 齐备后才能流转到下一 step
- 状态变更（state / current_owner / next_owner）必须**先写 status.json，再产出内容**

Agent MUST NOT：

- 戴着某个面具时做该面具职责外的事（如戴 backend 面具时做 review）
- 跳过 Plan 卡点（plan.md 写完即等用户确认，禁止自跳 implementation）
- 跳过当前 workflow 中的任何 step
- 全量扫描 Memory
- 全量加载历史任务
- 在拍板后的自动接力过程中无故停下询问用户（中断条件仅限 done / blocked / 反复失败）

---

## 2. Task Contract

每个任务必须包含：

- 任务描述（task.md）
- 执行计划（plan.md）
- 状态记录（status.json）
- 交接记录（handoff.md）
- 审查记录（review.md，如适用）

**创建约束：**

- 禁止手动创建任务目录或硬编码时间戳。
- **必须**使用工具脚本创建：`bash .ai/bin/new-task <name> <workflow> <priority>`。
- 脚本会自动获取系统 UTC 时间，确保 `created_at` 与驾驶舱同步。

文件结构以 `.ai/prompts/` 下各模板为准。
status.json 的字段定义以 `.ai/prompts/status-template.md` 为唯一来源，本文件不重复枚举。

支持的任务类型由 `.ai/workflows/*.yaml` 决定（当前包含：feature / bugfix / refactor / migration / release / rollback / hotfix）。新增 workflow 时只需增删对应 yaml，无需修改本文件。

---

## 3. Workflow

每个 workflow 的具体状态流转以 `.ai/workflows/<workflow>.yaml` 为唯一来源，本文件不再硬编码任何 workflow 的完整流程。

通用约束：

- `state` 字段值即任务当前所处的 workflow step，**全部使用小写**（不再使用 TODO / IN_PROGRESS / DONE 这类进度细分）
- 任务"是否结束"由是否进入 `done` 表达
- `blocked` 为通用异常状态，任意 step 都可进入；解除后由 workflow 的 `resume_to` 字段决定返回 step

下例仅为 `feature` workflow 的形态示意，其他 workflow（bugfix / migration / hotfix 等）见各自 yaml：

```text
planning
↓
implementation
↓
review
↓
testing
↓
done
```

---

## 4. Context Loading

Memory 分两层，按需加载：

| 层 | 位置 | 内容 | 管理方式 |
|---|---|---|---|
| 项目记忆 | `.ai/memory/` | 架构、规范、API、决策、测试 | workflow 自动维护（见 supervisor.md） |
| 自动记忆 | `~/.claude/projects/.../memory/` | 用户偏好、反馈、项目目标 | Claude Code 自动写入 |

### 加载机制

1. **索引入口**：`.ai/memory/MEMORY.md` 列出所有可用记忆及其描述
2. **Intake 加载**：supervisor 判定 workflow + depth 后，按任务关键词匹配并加载相关 memory（规则见 `.ai/agents/supervisor.md` Memory Loading 段）
3. **面具切换加载**：切面具时按该面具的 Context 段声明补加载
4. **done 自动写**：任务归档时 supervisor 检出新知识并写入对应 memory 文件

### 加载规则

- 仅加载完成当前任务所需的最小 Context
- 不加载无关 Memory
- 不加载全部历史任务
- 先读 MEMORY.md 索引再决定加载哪些具体文件

---

## 5. Decision Priority

发生冲突时按以下顺序裁决：

```text
CLAUDE.md
↓
用户当前请求
↓
Task（task.md / plan.md / status.json / handoff.md / review.md）
↓
Workflow（workflows/*.yaml + workflows/README.md）
↓
Decisions（memory/decisions.md）
↓
Memory（memory/* 其余知识，内部次序：architecture → conventions → project → 领域规范）
↓
Agent（agents/*.md 角色定义）
```

高优先级覆盖低优先级。

说明：

- CLAUDE.md 与用户当前请求若直接冲突（如用户要求跳过 review/testing），Agent 必须先向用户明确确认是否临时覆盖协议，确认后才执行
- 本节链条与 `.ai/README.md` 的规范优先级保持一致

---

## 6. Collaboration

单 Coach 模式下不存在多 Agent 实例间通信，所有"协作"都退化为 supervisor 在不同 step 切面具。规则：

- supervisor 是唯一与用户对话的入口
- 面具之间不直接对话，所有交接信息走 `handoff.md`（追加段）
- 所有任务状态必须同步到 `status.json`（lint-protocol 可校验）
- 跨 step 流转必须严格按 `.ai/workflows/<workflow>.yaml` 的 `next` / `transitions` 字段

---

## 7. Handoff

交接时必须在 `handoff.md` **追加**一段（不覆盖前一段），格式见 `.ai/prompts/handoff-template.md`。

必填：

- Completed
- Next Step（含下一负责人 + 下一动作）

按需补充（**无内容时直接省略整个小节，不写"无"/"None"**）：

- Pending
- Risks
- Blockers

---

## 8. Memory Rules

Memory 用于长期知识沉淀。

允许：

- 架构设计
- 重要决策
- 开发规范
- 可复用经验

禁止：

- 任务进度
- 调试日志
- 临时记录
- 一次性方案

---

## 9. Definition of Done

进入 done 前必须满足：

- 当前 workflow（见 `.ai/workflows/<id>.yaml`）声明的所有 step 已按顺序完成
- 各 step 声明的 outputs 文件均已生成（如 `plan.md` / `review.md` / `handoff.md` 等）
- `status.json.state = done`，`next_owner = null`
- `handoff.md` 已记录最终交接

各 workflow 必经 step 不在本文件中重复枚举，以对应 yaml 为唯一来源。新增 workflow 不需要修改本节。

---

## 10. Failure Handling

`blocked` 是 workflow 内的合法状态，用于业务依赖等待。
下面这些情况是**协议违反**，Agent 必须中断流转并显式上报，不能默默继续：

| 异常 | 处理 |
|---|---|
| `status.json` 缺失或 JSON 损坏 | 标记任务为 broken，向用户说明，停止流转 |
| `workflow` id 在 `.ai/workflows/` 不存在 | 向用户确认 workflow 类型，修正 `status.json` 后重试 |
| `state` 不在当前 workflow 的 steps 列表内 | 视为非法状态，回退到上一个合法 state 或进入 `blocked` |
| `current_owner` / `next_owner` 不在当前 workflow 声明的合法角色集 | 申请重新指派，不擅自接管 |
| 当前 step 声明的 outputs 缺失 | 不允许流转到 next，先补齐 outputs |
| `handoff.md` 缺失或未追加新段 | 不允许进入 next step |
| 同一 step 长期 `blocked`（>1 个工作周期） | 升级到 planner，由 planner 决定改 workflow 或拆任务 |

校验工具：`.ai/bin/lint-protocol` 可在 CI 或本地批量执行上述检查。

---

## 11. Principles

1. Context First（先理解上下文再行动）
2. On-Demand Loading（按需加载）
3. Workflow Is Mandatory（流程不可跳过）
4. Decisions Override Implementation（决策优先于实现）
5. Outputs Before Transition（产出齐备才能流转到下一 step）
6. Workflow Defines Completion（done 的判定以当前 workflow 必需 step 为准）
7. Memory Stores Knowledge, Not Progress（Memory 存知识，不存进度）