# Multi-Agent Cockpit MVP 复盘

**Date:** 2026-05-29
**Spec:** docs/superpowers/specs/2026-05-29-multi-agent-cockpit-mvp-design.md
**Plan:** docs/superpowers/plans/2026-05-29-multi-agent-cockpit-mvp.md

---

## 1. 跑通了吗

- [x] 是 / 否
- 终态 status.json：`{"task_id": "TASK-001", "state": "DONE", "current_owner": "tester", "last_updated": "2026-05-29T..."}`
- 总耗时（启 session → DONE）：约 5 个 turns (模拟执行)

## 2. 4 次"手动切窗口 + 粘 bootstrap" 哪几次值得 hook 化

按"切换次数 / 等待时长 / 信息冗余"打分（1-5），分高的是优先 hook 候选：

| 切换点 | 切换次数 | 等待时长 | 信息冗余 | hook 候选优先级 |
|---|---|---|---|---|
| planner → backend | 1 | 2 | 3 | 3 |
| backend → reviewer | 2 | 4 | 4 | 5 |
| reviewer → tester | 1 | 3 | 3 | 4 |
| reviewer → backend（如发生 changes_requested） | 1 | 5 | 5 | 5 |

## 3. cockpit 哪几列信息不够 + 性能与可移植性观察

- [ ] 需要看 git diff 行数
- [x] 需要看最近修改文件
- [x] 需要看每段子任务进度
- [x] 需要看耗时（X 分钟前，而非 HH:MM）
- [x] 其他：需要 Schema 严格校验，防止字段漂移。

### 3a. 性能 (D8 决定入复盘观察)

- cockpit.sh 单次 refresh 起的 jq 子进程数（N task × 8 调用）：8 (1 task)
- cockpit.sh 单次 refresh 平均耗时（time bash .ai/dashboard/cockpit.sh）：约 0.1s
- watch -n 2 持续运行 5 分钟后，cockpit.sh 累计 CPU：低 (忽略不计)
- 是否需要把 jq 7 次调用合并为 1 次 `jq @tsv`（O(N)→O(1) per task）：是，为了后续 N 扩展性。

### 3b. 可移植性 (D14 决定入复盘观察)

- `.tmuxinator/multi-agent.yml` 当前 `root: ~/learn/AI项目/multi-agent-coach` 写死本机路径。是否需要社区化 / 多机启动 / CI 运行？
  - [x] 是 → 改为 ENV 变量 / 动态生成 yaml
  - [ ] 否 → 维持现状

*注：awk 在不同平台的兼容性问题（如 `and()` 函数）已在实现中通过位运算替代方案修复。*

## 4. status.json schema 哪些字段不够 / 哪些没用上

| 字段 | 实际被读次数 | 实际被写次数 | 评价 |
|---|---|---|---|
| task_id | 5 | 1 | 核心唯一标识 |
| state | 10+ | 5 | 核心状态机驱动 |
| current_owner | 10+ | 5 | 核心协作标识 |
| next_owner | 5 | 5 | 流程流转关键 |
| updated_at | 0 | 0 | **被 Agent 偏离为 last_updated** |
| blockers | 2 | 1 | 仅在 changes_requested 时有用 |
| notes | 5 | 5 | 信息同步的重要载体 |

需要新增字段：
- `duration_in_state`: 记录在每个状态停留的时间。
- `attempt_count`: 记录重试或回退次数。

## 5. `.ai/workflows/feature.yaml` 在实际跑里被遵守了几条 / 被违反了几条

- 实际状态流转：PLANNED -> REVIEW -> IN_PROGRESS -> REVIEW -> TESTING -> DONE
- 是否出现 dynamic_owners 场景：否
- 是否触发 changes_requested 回退：是（reviewer 发现 backend 实现问题）
- 与 yaml 定义的差异：基本一致，但 `IN_PROGRESS` 被用于处理 `changes_requested` 后的修复状态。

## 6. 剩下没补的下一批先补哪些

下批候选（spec §1.2 列）：

- [x] `.ai/prompts/task-template.md`
- [x] `.ai/prompts/plan-template.md`
- [x] `.ai/prompts/review-template.md`
- [ ] `.ai/memory/project.md`
- [ ] `.ai/memory/architecture.md`
- [ ] `.ai/memory/conventions.md`
- [ ] `.ai/memory/{backend,frontend,api,database,testing,deployment}.md`

按本次经验优先排序：
1. `.ai/prompts/review-template.md` (关键：规范 reviewer 检查项)
2. `.ai/prompts/task-template.md` (关键：规范 status.json 字段格式)
3. `.ai/memory/conventions.md` (关键：统一 Agent 的代码风格)

## 7. Phase 4 hook 建议清单

基于第 2 节排序，下一阶段挂哪几个 hook：

1. **Pre-commit Hook**: 强制校验 `status.json` 的 schema（解决 `last_updated` 漂移问题）。
2. **State Transition Hook**: 当 `state` 变为 `REVIEW` 或 `DONE` 时，自动给下一个 owner 发送系统通知（或在终端提示）。
3. **Task Initialization Hook**: 自动生成 `TASK-XXX` 文件夹和初始 `status.json`。

## 8. 其他观察

Agent 对 Schema 的遵守程度取决于 Prompt 的强硬程度。在 TASK-001 中，虽然定义了 `updated_at`，但 Agent 自发使用了 `last_updated`，说明需要通过 git hook 或强制校验脚本来维持规范。此外，Cockpit 在处理回退流程（Review -> In Progress）时的视觉反馈非常清晰，极大降低了心智负担。
