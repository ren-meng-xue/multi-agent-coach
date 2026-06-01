# 决议记录

> Agent OS V1 已批准决议

---

## 工作流系统

| 项目    | 决议                                                            |
| ----- | ------------------------------------------------------------- |
| 工作流职责 | 仅负责流程、状态、状态流转                                                 |
| 工作流结构 | id / name / description / entry / terminal / steps            |
| 通用状态  | planning / implementation / blocked / review / testing / done |
| 允许扩展  | 允许定义领域专属状态                                                    |

### 已批准工作流

| 工作流       | 流程                                                                  |
| --------- | ------------------------------------------------------------------- |
| Feature   | planning → implementation → review → testing → done                 |
| BugFix    | planning → investigation → implementation → review → testing → done |
| Refactor  | planning → implementation → review → testing → done                 |
| Migration | planning → review → migration → verification → done                 |
| Release   | planning → review → release → verification → done                   |
| Rollback  | planning → rollback → verification → done                           |
| Hotfix    | planning → implementation → testing → restored → review → done      |

---

## Agent 系统

| Agent    | 职责           |
| -------- | ------------ |
| Planner  | 规划、拆解、归档     |
| Backend  | 后端实现         |
| Frontend | 前端实现         |
| Reviewer | Review 与质量检查 |
| Tester   | 测试与验证        |

---

## Memory 系统

| 项目   | 决议          |
| ---- | ----------- |
| 组织方式 | 按主题拆分       |
| 加载方式 | 按需读取        |
| 职责   | 存储长期知识与项目规则 |

---

## Task 系统

| 项目        | 决议          |
| --------- | ----------- |
| 存储位置      | .ai/tasks/  |
| 状态文件      | status.json |
| 计划文件      | plan.md     |
| Review 文件 | review.md   |
| 交接文件      | handoff.md  |

---

## 2026-05-31 — Agent Skill 规则单一来源

决议：项目自定义 skill / protocol 的规则正文统一维护在 `.ai/skills/*.md`；`.claude/skills/<name>/SKILL.md` 仅作为 Claude Code 的 skill 注册入口；可执行逻辑放在 `.ai/bin/<tool>`。

原因：

- Claude Code 需要 `.claude/skills/<name>/SKILL.md` 才能识别 `/skill` 入口。
- 项目协议需要在 `.ai/` 下统一维护，避免规则散落到工具私有目录。
- 双份规则正文容易漂移，因此 `.claude/skills` 只能保留薄入口，具体边界以 `.ai/skills` 为准。

状态：已批准
