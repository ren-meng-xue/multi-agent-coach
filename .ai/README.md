# AI Agent 系统

本目录为 Agent OS 的运行规范目录。项目运行在**单 Coach（Supervisor）模式**下，详见 `CLAUDE.md` §0。

---

## 系统结构

```text
.ai/
├── README.md                    # 本文件
│
├── agents/                      # Agent 角色定义（Supervisor 的面具）
│   ├── README.md
│   ├── supervisor.md            # 元角色：接收消息、判定深度、自动接力
│   ├── planner.md               # plan/done step 面具
│   ├── backend.md               # implementation step 面具
│   ├── frontend.md              # implementation step 面具
│   ├── reviewer.md              # review step 面具
│   └── tester.md                # qa/testing step 面具
│
├── workflows/                   # Workflow 定义（v2，含深度系统）
│   ├── README.md
│   ├── feature.yaml
│   ├── bugfix.yaml
│   ├── hotfix.yaml
│   ├── migration.yaml
│   ├── release.yaml
│   ├── rollback.yaml
│   └── refactor.yaml            # extends feature
│
├── prompts/                     # 输出模板
│   ├── task-template.md
│   ├── plan-template.md
│   ├── review-template.md
│   ├── handoff-template.md
│   └── status-template.md
│
├── memory/                      # 项目长期知识
│   ├── project.md
│   ├── architecture.md
│   ├── conventions.md
│   ├── decisions.md
│   ├── backend.md / frontend.md / api.md / database.md
│   ├── testing.md
│   └── deployment.md
│
├── tasks/                       # 任务实例
│   ├── YYYYMMDD-semantic-name/  # 活跃任务
│   └── archive/                 # 已归档任务
│
├── bin/                         # CLI 工具
│   ├── new-task                 # 创建任务脚手架
│   └── lint-protocol            # 协议校验
│
└── lib/python/                  # 共享逻辑
    ├── workflow_loader.py       # Workflow 解析 + 深度过滤
    └── protocol_linter.py       # 协议校验规则
```

---

## 运行模式：单 Coach（Supervisor）

- 用户只与一个 Claude 实例对话，其默认身份为 **supervisor**
- Supervisor 是元角色：接收消息、判定意图、判定 workflow 类型与深度档位、按 workflow yaml 自动推进 step
- `agents/{backend,frontend,planner,reviewer,tester}.md` 是 supervisor 在不同 step **戴的面具**，而非独立进程
- 面具之间不直接对话，交接信息走 `handoff.md`

## 深度系统

4 档复杂度，supervisor 自动判定：

| 深度 | 适用场景 | 步骤链 |
|---|---|---|
| `quick` | ≤3 文件，低风险 | plan → impl → review → done |
| `standard` | ≤10 文件，常规功能/bugfix（默认） | plan → impl → review → qa → done |
| `thorough` | 复杂功能，API 变更 | office-hours → spec → plan → eng-review → impl → review → qa → done |
| `full` | 重大变更，架构调整 | 全 13 步 + 3 卡点 |

## 3 个人工卡点

1. **Plan 卡点**（所有深度）：plan.md 写完后等用户拍板
2. **冲突裁决卡点**（仅 full）：多角色 review 有分歧时等用户裁决
3. **Ship 卡点**（仅 full）：发布前等用户确认

---

## 模块职责

| 模块 | 职责 |
|---|---|
| `agents/` | 定义 Supervisor 及各面具的角色、职责与边界 |
| `workflows/` | 定义状态机、流程、深度过滤、流转规则 |
| `prompts/` | 输出模板（task/plan/review/handoff/status） |
| `memory/` | 项目长期知识与规则 |
| `tasks/` | 任务实例与运行状态 |
| `bin/` | 面向开发者/CI 的全局工具 |
| `lib/` | 跨模块复用的核心逻辑（workflow_loader / protocol_linter） |

---

## Workflow 类型

| Workflow | 说明 |
|---|---|
| feature | 新功能开发 |
| bugfix | 缺陷修复 |
| hotfix | 紧急修复 |
| refactor | 代码重构（extends feature） |
| migration | 数据迁移 |
| release | 发布流程 |
| rollback | 回滚流程 |

详细规范见 `workflows/README.md`。

---

## Agent 面具

| 面具 | 职责 |
|---|---|
| supervisor | 元角色：接收消息、判定意图、切面具、自动接力 |
| planner | plan step：写 task.md/plan.md；done step：归档 |
| backend | 后端开发、数据库变更、接口实现 |
| frontend | 页面开发、组件实现、状态管理 |
| reviewer | Review、风险检查、质量评估 |
| tester | 测试、验证、回归检查 |

详见 `agents/README.md`。

---

## Memory 系统

Memory 用于存放项目长期知识。按需加载（On-Demand Loading），默认不全部读入。

| 文件 | 说明 |
|---|---|
| project.md | 项目目标与业务背景 |
| architecture.md | 系统架构设计 |
| conventions.md | 开发规范与编码约定 |
| decisions.md | 技术决策记录 |
| backend.md / frontend.md / api.md / database.md | 领域规范 |
| testing.md / deployment.md | 测试与部署规范 |

---

## Task 系统

Task 是 Workflow 的运行实例。

### 目录结构

```text
tasks/YYYYMMDD-semantic-name/
├── task.md
├── plan.md
├── status.json
├── review.md
└── handoff.md
```

### 创建任务

必须使用脚本：`bash .ai/bin/new-task <name> <workflow> <priority> [depth]`

---

## 规范优先级

与 `CLAUDE.md` §5 保持一致：

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
Memory（memory/* 其余知识）
  ↓
Agent（agents/*.md 角色定义）
```

---

Status: Approved
Version: Agent OS V2（单 Coach 模式）
