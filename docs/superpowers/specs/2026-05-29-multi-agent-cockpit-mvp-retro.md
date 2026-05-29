# Multi-Agent Cockpit MVP 复盘

**Date:** 2026-05-29
**Spec:** docs/superpowers/specs/2026-05-29-multi-agent-cockpit-mvp-design.md
**Plan:** docs/superpowers/plans/2026-05-29-multi-agent-cockpit-mvp.md

---

## 1. 跑通了吗

- [ ] 是 / 否
- 终态 status.json：
- 总耗时（启 session → DONE）：

## 2. 4 次"手动切窗口 + 粘 bootstrap" 哪几次值得 hook 化

按"切换次数 / 等待时长 / 信息冗余"打分（1-5），分高的是优先 hook 候选：

| 切换点 | 切换次数 | 等待时长 | 信息冗余 | hook 候选优先级 |
|---|---|---|---|---|
| planner → backend | | | | |
| backend → reviewer | | | | |
| reviewer → tester | | | | |
| reviewer → backend（如发生 changes_requested） | | | | |

## 3. cockpit 哪几列信息不够 + 性能与可移植性观察

- [ ] 需要看 git diff 行数
- [ ] 需要看最近修改文件
- [ ] 需要看每段子任务进度
- [ ] 需要看耗时（X 分钟前，而非 HH:MM）
- [ ] 其他：

### 3a. 性能 (D8 决定入复盘观察)

- cockpit.sh 单次 refresh 起的 jq 子进程数（N task × 8 调用）：
- cockpit.sh 单次 refresh 平均耗时（time bash .ai/dashboard/cockpit.sh）：
- watch -n 2 持续运行 5 分钟后，cockpit.sh 累计 CPU：
- 是否需要把 jq 7 次调用合并为 1 次 `jq @tsv`（O(N)→O(1) per task）：

### 3b. 可移植性 (D14 决定入复盘观察)

- `.tmuxinator/multi-agent.yml` 当前 `root: ~/learn/AI项目/multi-agent-coach` 写死本机路径。是否需要社区化 / 多机启动 / CI 运行？
  - [ ] 是 → 改为 ENV 变量 / 动态生成 yaml
  - [ ] 否 → 维持现状

## 4. status.json schema 哪些字段不够 / 哪些没用上

| 字段 | 实际被读次数 | 实际被写次数 | 评价 |
|---|---|---|---|
| task_id | | | |
| state | | | |
| current_owner | | | |
| next_owner | | | |
| updated_at | | | |
| blockers | | | |
| notes | | | |

需要新增字段：
-

## 5. `.ai/workflows/feature.yaml` 在实际跑里被遵守了几条 / 被违反了几条

- 实际状态流转：
- 是否出现 dynamic_owners 场景：
- 是否触发 changes_requested 回退：
- 与 yaml 定义的差异：

## 6. 剩下没补的下一批先补哪些

下批候选（spec §1.2 列）：

- [ ] `.ai/prompts/task-template.md`
- [ ] `.ai/prompts/plan-template.md`
- [ ] `.ai/prompts/review-template.md`
- [ ] `.ai/memory/project.md`
- [ ] `.ai/memory/architecture.md`
- [ ] `.ai/memory/conventions.md`
- [ ] `.ai/memory/{backend,frontend,api,database,testing,deployment}.md`

按本次经验优先排序：
1.
2.
3.

## 7. Phase 4 hook 建议清单

基于第 2 节排序，下一阶段挂哪几个 hook：

1.
2.
3.

## 8. 其他观察
