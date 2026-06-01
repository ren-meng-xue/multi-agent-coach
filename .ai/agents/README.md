# Agent Specification

本目录定义 Agent OS 中各 Agent 的职责、结构与协作边界。

所有运行时规则、状态机、任务状态、Handoff 规范、Checklist 规范、任务目录规范等，统一以 `CLAUDE.md` 为准。

---

## 1. Agent Schema

所有 Agent 文件统一使用以下结构：

```text
# Agent Name

## Role                       (必填)

## Responsibilities           (必填)

## Workflow Responsibilities  (必填)

## Role-specific Rules        (必填)

## Handoff                    (必填)

## Inputs                     (可选)

## Outputs                    (可选)

## Required Context           (可选)
```

可选 section 默认由 workflow yaml 与 `CLAUDE.md §4 Context Loading` 推断：

- `Inputs` / `Outputs`：默认参考所属 step 的 `outputs` 字段与上一 step 的产出
- `Required Context`：默认按 `CLAUDE.md §4` 的按需加载规则

仅当 Agent 在某个流程中需要偏离默认行为时，才在文件中显式写出对应可选 section。

---

## 2. Section Definition

| Section                   | 必填 | 说明             |
| ------------------------- | :-: | -------------- |
| Role                      | ✓  | Agent 身份定位     |
| Responsibilities          | ✓  | 核心职责           |
| Workflow Responsibilities | ✓  | Workflow 中负责内容 |
| Role-specific Rules       | ✓  | 当前角色专属约束       |
| Handoff                   | ✓  | 下一责任 Agent     |
| Inputs                    | ○  | 执行所需输入（默认从 workflow yaml 推断）|
| Outputs                   | ○  | 执行产出（默认从 workflow yaml 推断）|
| Required Context          | ○  | 当前 Agent 所需上下文（默认按 CLAUDE.md §4 加载）|

---

## 3. Agent List

下表为**当前已实现**的 Agent。
角色不是协议硬编码：新增 Agent（如 architect / devops / security / dba）只需

1. 新建 `.ai/agents/<role>.md`
2. 在对应 `.ai/workflows/*.yaml` 的 step `owner` / `owners` 字段引用

无需修改 `CLAUDE.md`。

| Agent    | 职责                |
| -------- | ----------------- |
| Planner  | 需求分析、任务拆解、计划制定、归档 |
| Backend  | 后端开发、数据库变更、接口实现   |
| Frontend | 页面开发、组件实现、状态管理    |
| Reviewer | Review、风险检查、质量评估  |
| Tester   | 测试、验证、回归检查        |

---

## 4. Workflow Ownership

| Workflow Step         | Owner              |
| --------------------- | ------------------ |
| office-hours          | Planner            |
| spec                  | Planner            |
| plan                  | Planner            |
| eng-review            | Reviewer           |
| ceo-review            | Reviewer           |
| design-review         | Reviewer           |
| conflict-resolution   | Planner            |
| investigation         | Backend / Frontend |
| implementation        | Backend / Frontend |
| migration             | Backend            |
| review                | Reviewer           |
| qa                    | Tester             |
| testing               | Tester             |
| verification          | Tester             |
| release               | Planner            |
| rollback              | Backend / Frontend |
| restored              | Planner            |
| ship                  | Planner            |
| done                  | Planner            |
| restored       | Planner            |
| done           | Planner            |

---

## 5. Responsibility Boundary

本目录下的每个 `.md` 文件（排除 `README.md`）即代表一个合法的 Agent。系统通过扫描文件名自动注册 Agent。

下表为各角色职责的详细定义：

| Agent    | 允许执行             |
| -------- | ---------------- |
| Planner  | 创建任务、制定计划、归档     |
| Backend  | 后端开发、数据库变更、接口实现  |
| Frontend | UI、页面、状态管理       |
| Reviewer | Review、质量评估、风险分析 |
| Tester   | 测试、验证、回归检查       |

---

## 6. Prohibited Actions

| Agent    | 禁止            |
| -------- | ------------- |
| Planner  | 编写业务代码        |
| Backend  | 修改任务规划、编写前端代码 |
| Frontend | 修改任务规划、编写后端代码 |
| Reviewer | 修改业务代码        |
| Tester   | 修改业务代码、直接修复问题 |

---

## 7. Handoff Principle

Agent 仅负责当前阶段。

典型流程：

```text
Planner
  ↓
Backend / Frontend
  ↓
Reviewer
  ↓
Tester
  ↓
Planner
```

任何 Agent 不应跳过必要环节直接进入后续阶段。

---

Status: Approved

Version: Agent OS V2
