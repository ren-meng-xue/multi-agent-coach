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
