# Workflow Specification

本目录定义 Agent OS 的工作流规范。

---

## 1. Schema

| 字段 | 必填 | 说明 |
|---|---:|---|
| `id` | ✓ | Workflow 唯一标识 |
| `version` | ✓ | 版本号（变更协议时 +1） |
| `name` | ✓ | Workflow 名称 |
| `description` | ✓ | 简短描述 |
| `entry` | ✓ | 入口 step |
| `terminal` | ✓ | 结束 step |
| `steps` | ✓ | 状态与流转定义 |
| `extends` |  | 继承的 base workflow id（深合并；子 workflow 字段覆盖 base） |

### Extends 机制

允许子 workflow 继承 base，避免重复声明几乎相同的 step。例如 `refactor` 与 `feature`
仅 `implementation.mode` 不同，可写为：

```yaml
id: refactor
version: 1
name: Refactor Flow
description: 重构流程
extends: feature
steps:
  implementation:
    mode: single  # 覆盖 feature 的 parallel
```

解析后通过 `python3 .ai/lib/python/workflow_loader.py show refactor` 可以查看展开结果。
extends 链不可循环；解析在 `workflow_loader.py` 内完成，所有消费者
（lint / cockpit / hooks）必须通过该 loader 读取，不允许重复硬编码 step/state/owner 列表。

---

## 2. Common States

优先复用通用状态，但允许 Workflow 定义领域专属状态。

| State | 说明 |
|---|---|
| `planning` | 分析任务、制定计划 |
| `implementation` | 执行开发、修复、重构、迁移 |
| `blocked` | 等待依赖或外部输入 |
| `review` | Review 与质量检查 |
| `testing` | 测试与验证 |
| `done` | 完成并归档 |

### Domain States

允许在必要时增加领域状态。

| State | 场景 |
|---|---|
| `rollback` | 回滚执行 |
| `verification` | 回滚、发布后的恢复验证 |
| `restored` | Hotfix 后服务已恢复 |
| `migration` | 数据迁移执行 |
| `release` | 发布执行 |

---

## 3. Step Fields

| 字段 | 类型 | 说明 |
|---|---|---|
| `owner` | string | 单个负责 Agent |
| `owners` | array | 多个可执行 Agent |
| `mode` | string | `single` 或 `parallel` |
| `dynamic_owners` | boolean | 是否由 planner 决定实际参与 Agent |
| `outputs` | array | 当前 step 产出文件（包含 `done` 的归档凭证 `handoff.md`） |
| `next` | string | 默认下一步 |
| `transitions` | object | 条件流转 |
| `on_blocked` | string | 阻塞时进入的 step |
| `resume_to` | string | 阻塞解除后返回的 step |
| `min_depth` | string | **v2 新增**。该 step 的最低激活深度：`quick` / `standard` / `thorough` / `full`。缺省为 `quick` |
| `checkpoint` | boolean | **v2 新增**。该 step 是否需要人工确认。缺省为 `false` |

### 深度系统 (Depth)

4 档复杂度，由低到高：

| 深度 | 典型步骤链 | 适用场景 |
|---|---|---|
| `quick` | plan → impl → review → done | ≤3 文件，低风险，小修小改 |
| `standard` | plan → impl → review → qa → done | ≤10 文件，常规功能/bugfix（默认） |
| `thorough` | office-hours → spec → plan → eng-review → impl → review → qa → done | 复杂功能，API 变更 |
| `full` | office-hours → spec → plan → ceo+eng+design review → 冲突裁决 → impl → review → qa → ship | 重大变更，架构调整 |

3 个人工卡点（仅 full 深度全部激活）：plan / conflict-resolution / ship

---

## 4. Agents

| Agent | 职责 |
|---|---|
| `planner` | 分析、拆解、分配、归档 |
| `backend` | Backend 实现 |
| `frontend` | Frontend 实现 |
| `reviewer` | Review 与质量检查 |
| `tester` | 测试与验证 |

---

## 5. Recommended Flows

| Workflow | 完整流程（full 深度） | quick 深度 |
|---|---|---|
| `feature` | office-hours → spec → plan → eng-review → ceo-review → design-review → conflict-resolution → implementation → review → qa → ship → done | plan → implementation → review → done |
| `bugfix` | office-hours → plan → eng-review → investigation → implementation → review → qa → ship → done | plan → investigation → implementation → review → done |
| `refactor` | 同 feature（implementation mode = single） | 同 feature quick |
| `migration` | office-hours → plan → review → migration → verification → ship → done | plan → review → migration → verification → done |
| `release` | office-hours → plan → review → release → verification → ship → done | plan → review → release → verification → done |
| `rollback` | plan → rollback → verification → done（无额外步骤） | plan → rollback → verification → done |
| `hotfix` | plan → implementation → testing → restored → review → done（无 quick 以上） | plan → implementation → testing → done |

---

## 6. Responsibility Boundary

| 模块 | 负责 |
|---|---|
| `workflows/` | 流程、状态、流转、并行关系 |
| `agents/` | Agent 面具行为与职责 |
| `memory/` | 项目知识与长期规则 |
| `prompts/` | 输出模板 |
| `tasks/` | 任务实例与运行状态 |
| `bin/` | CLI 工具（new-task / lint-protocol） |
| `lib/` | 共享逻辑（workflow_loader / protocol_linter） |

---

## 7. Rules

| 规则 | 说明 |
|---|---|
| 优先复用通用状态 | 不为小差异创造新状态 |
| 允许领域状态 | 回滚、发布、迁移、恢复等可以有专属状态 |
| 流程轻量 | Workflow 只定义流程，不写执行细节 |
| 行为下沉 | 复现、根因分析、Review checklist 写入 `agents/` 或 `prompts/` |
| 知识下沉 | 架构、API、数据库规则写入 `memory/` |
| 状态下沉 | 任务当前状态写入 `tasks/YYYYMMDD-semantic-name/status.json` |
| 单一真值 | step / state / owner 列表只在 yaml 中声明，所有消费者通过 `workflow_loader.py` 读取 |
| `done` 是终态 | 进入 `done` 表示任务结束；step 仍保留 `owner: planner` 用于归档动作，并要求 `handoff.md` 作为归档凭证 |

---

## 8. Status Schema

任务状态文件 `status.json` 的字段定义以 `.ai/prompts/status-template.md` 为唯一来源。
**不要使用 `type` 字段**——已弃用，与 `workflow` 字段冗余。lint 会就此告警。