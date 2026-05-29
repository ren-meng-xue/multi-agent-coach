# Multi-Agent Workflow

定义智能体在 Multi-Agent Cockpit 架构下的协作与执行工作流。

## Workflow Authority

在多智能体协同处理任务时，规则与上下文文件的权威优先级如下（数字越小优先级越高）：

|  优先级  | 文件 / 目录                    | 冲突处理原则                |
| :---: | :------------------------- | :-------------------- |
| **1** | `CLAUDE.md`                | 最高准则，所有 Agent 必须无条件遵守 |
| **2** | `agents/*.md`              | 各 Agent 的角色定义与专属行为规范  |
| **3** | `shared/decisions/*`       | 长期有效的架构与流程决策          |
| **4** | `shared/current/tasks.md`  | 当前活跃任务清单              |
| **5** | `shared/current/status.md` | 当前执行状态                |
| **6** | `shared/current/review.md` | Reviewer 的评审与 QA 反馈   |

当各文件内容发生冲突时，必须按上述优先级执行。

---

## Required Context

所有 Agent 在开始任何任务前，必须读取：

* `CLAUDE.md`
* 对应 Agent 文件
* `shared/current/tasks.md`
* `shared/current/status.md`
* `shared/decisions/*`

Reviewer 额外读取：

* `shared/current/review.md`

---

## Workflow Lifecycle

标准协作流程：

```txt
Human
↓
Planner
↓
Backend / Frontend
↓
Reviewer
↓
Planner
```

### Planner

负责：

* 创建任务
* 拆解任务
* 维护架构一致性
* 更新 decisions
* 分配任务
* 关闭任务
* 执行归档

### Backend / Frontend

负责：

* 读取任务
* 更新状态
* 完成实现
* 编写测试
* 执行验证

### Reviewer

负责：

* Review
* QA
* 风险检查
* 更新 review.md

---

## Task States

统一状态名称：

* `pending`
* `in-progress`
* `review`
* `blocked`
* `done`

禁止 Agent 自行创造新的状态名称。

---

## State Ownership

任务状态只能按以下职责更新：

| 状态          | Owner              |
| ----------- | ------------------ |
| pending     | Planner            |
| in-progress | Backend / Frontend |
| review      | Reviewer           |
| blocked     | 当前执行 Agent         |
| done        | Planner            |

### 状态流转规则

* Planner 创建任务时设置为 `pending`
* Backend / Frontend 开始执行任务后更新为 `in-progress`
* Reviewer 开始 Review 或 QA 后更新为 `review`
* 任意 Agent 遇到阻塞时可更新为 `blocked`
* Reviewer 在 `shared/current/review.md` 中给出 `approved` 结论后，由 Planner 更新为 `done`
* 只有 Planner 可以关闭任务并执行归档

### 状态修改原则

* Agent 只能修改自己负责的状态
* 禁止跳过状态流转
* 禁止自行创造新的状态名称
* 所有状态变更必须同步更新 `shared/current/status.md`
* `blocked` 状态必须附带阻塞原因
* `done` 状态必须满足任务完成标准与 Review 通过条件

### 标准状态流转

```txt
pending
↓
in-progress
↓
review
↓
done
```

发生阻塞：

```txt
pending
↓
in-progress
↓
blocked
↓
in-progress
↓
review
↓
done
```

---

## File Ownership

| 文件                         | Owner    | 权限               |
| -------------------------- | -------- | ---------------- |
| `shared/current/tasks.md`  | Planner  | 仅 Planner 可修改    |
| `shared/current/status.md` | Shared   | 所有 Agent 可更新自身状态 |
| `shared/current/review.md` | Reviewer | 仅 Reviewer 可修改   |
| `shared/decisions/*`       | Planner  | 仅 Planner 可修改    |

---

## Handoff Rules

### Planner → Backend / Frontend

条件：

```txt
Task State = pending
```

Planner：

* 创建任务
* 分配任务

Backend / Frontend：

* 开始执行
* 更新状态为 `in-progress`

---

### Backend / Frontend → Reviewer

条件：

```txt
Task State = in-progress
```

Backend / Frontend：

* 完成实现
* 完成测试
* 更新状态

Reviewer：

* 开始 Review
* 更新状态为 `review`

---

### Reviewer → Planner

条件：

```txt
review.md
Decision = approved
```

Planner：

* 标记任务完成
* 更新状态为 `done`
* 执行归档

---

### Blocked Flow

任意 Agent：

```txt
Task State = blocked
```

必须记录：

* 阻塞原因
* 所需协助
* 下一步行动

阻塞解除后恢复：

```txt
in-progress
```
