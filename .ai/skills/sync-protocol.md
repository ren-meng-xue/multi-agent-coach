# Sync-Protocol

保持 CLAUDE.md ↔ `.ai/` ↔ `MEMORY.md` 三者的引用一致性。

核心原则：**自动触发只审计，手动触发可同步匹配**。

- 自动触发时只能执行 `audit`，输出报告，不写文件
- 禁止因为一次任务完成而批量更新 `CLAUDE.md` 或 `.ai/` 下所有内容
- 当项目、文档或 `.ai/` 结构变化后，用户可以手动执行 `propose` 生成同步提案，再执行 `apply --confirmed` 应用可机械验证的同步项
- 写操作必须由用户明确触发；执行时只更新可从当前文件树确定的匹配关系，不做全量重写
- `CLAUDE.md`、workflow YAML、agent 角色文件属于协议核心，自动触发时只报告问题；手动触发时按下方写入边界处理

## 触发方式

- 用户手动：`/sync-protocol <操作>`
- supervisor 自动：每次 `done` step 归档后只允许跑 `audit`

自动触发的 `audit` 不得修改任何文件。

## 操作

执行入口：

```bash
.ai/bin/sync-protocol <audit|sync|propose|apply --confirmed|orphans|stale|update-index>
```

### audit — 全量一致性检查

扫描并报告：

1. **CLAUDE.md 引用检查**：CLAUDE.md 中所有路径引用是否指向实际存在的文件
2. **Agent Context 引用检查**：每个 `agents/*.md` 的 Context 段引用的 memory 文件是否存在
3. **MEMORY.md 条目检查**：每条索引是否对应实际存在的 memory 文件；是否有 memory 文件未被索引
4. **Workflow owner 检查**：workflow YAML 中声明的 owner 是否都有对应的 agent 文件
5. **prompts 引用检查**：CLAUDE.md 和 agent 文件中引用的模板路径是否存在

输出报告格式：

```
=== Sync-Protocol Audit ===
✓ CLAUDE.md 引用: N/N 通过
✓ Agent Context: N/N 通过
✓ MEMORY.md: N/N 通过
✓ Workflow owners: N/N 通过
✓ Prompts: N/N 通过

[如有问题则列出具体文件和行号]
```

### sync — 手动同步匹配

用于项目、文档或 `.ai/` 文件变化后，让协议索引重新匹配当前文件树。

执行条件：

- 用户明确要求执行 `sync`
- 先执行 audit，列出将同步的具体目标
- 每次只修复报告中列出的具体问题，不做全量重写

手动 `sync` 允许处理：

- 补全 `MEMORY.md` 中缺失的 memory 文件条目
- 更新 `MEMORY.md` 中与实际 memory 文件不匹配的单条描述
- 更新 README / 索引类文档中可机械推导的文件清单
- 修正 markdown 中明显失效、且可唯一映射到新位置的相对路径

需要二次确认的内容：

- 删除 `MEMORY.md` 中指向不存在文件的条目
- 修改 `CLAUDE.md`
- 修改 `.ai/workflows/*.yaml` 的拓扑、owner、depth、checkpoint
- 修改 `.ai/agents/*.md` 的 Role / Responsibilities / Rules
- 修改 `.ai/prompts/*.md` 模板结构
- 修改 `.ai/skills/*.md` 行为边界

执行前必须说明：

1. 将写入的目标文件
2. 将更新的匹配关系
3. 是否涉及删除、协议核心或行为边界
4. 涉及二次确认项时等待用户明确允许

### propose — 生成同步提案

只读操作。扫描当前文件树，输出：

- 可在确认后自动应用的机械同步项
- 涉及删除、协议核心、行为边界或语义判断的人工处理项
- 应用命令：`.ai/bin/sync-protocol apply --confirmed`

当前可自动应用的同步项：

- 补全 `.ai/memory/MEMORY.md` 缺失索引
- 为 `.ai/skills/*.md` 创建或收敛 `.claude/skills/<name>/SKILL.md` 薄注册入口

### apply --confirmed — 应用同步提案中的自动项

执行条件：

- 必须显式传入 `--confirmed`
- 只应用 `propose` 标记为 `AUTO` 的机械同步项
- 不自动删除任何文件、目录、索引、分支或远程资源
- 不自动修改 `CLAUDE.md`、workflow YAML 拓扑、agent 职责、prompt 模板结构或 `.ai/skills/*.md` 行为边界

### orphans — 孤立文件检测

列出 `.ai/` 下没有被任何文件引用的孤立文件（不在 MEMORY.md、CLAUDE.md、workflow YAML 或 agent Context 中）。

### stale — 过期引用检测

列出引用了不存在路径的文件和行号。

### update-index — 更新 MEMORY.md

重新扫描 `.ai/memory/*.md`（不含 MEMORY.md 自身），只补全缺失索引并报告孤立索引。

限制：

- 不覆盖重写整个 `MEMORY.md`
- 不修改已有条目的人工描述，除非用户执行 `sync` 并确认该条需要跟随实际文件更新
- 不删除孤立索引，除非用户明确确认删除目标

## 执行流程

1. 先读 CLAUDE.md、MEMORY.md、所有 agent 文件、所有 workflow YAML
2. 扫描 `.ai/` 实际文件树
3. 交叉比对，按所选操作输出结果
4. 如果是 `audit` / `orphans` / `stale`，只输出报告
5. 如果是 `propose`，只输出提案，不写文件
6. 如果是 `apply --confirmed` / `sync` / `update-index`，先列出将写入的具体目标；涉及删除、协议核心或行为边界时等待用户确认

## 适用范围

- 仅扫描 `.ai/` 和 `CLAUDE.md`
- 不扫描 `tasks/`（任务文件随任务生命周期变化）
- 不扫描 `lib/python/__pycache__/`（自动生成）

## 写入边界

手动 `sync` 默认可写范围：

- `.ai/memory/MEMORY.md` 的缺失索引补全
- `.ai/memory/MEMORY.md` 中与实际 memory 文件匹配的单条描述更新
- README / 索引类文档中的文件清单同步
- 可唯一确定目标的新旧相对路径引用修正
- `.claude/skills/<name>/SKILL.md` 薄注册入口创建或收敛（规则正文仍以 `.ai/skills/*.md` 为准）

需要二次确认的写入范围：

- `CLAUDE.md`
- `.ai/agents/`
- `.ai/workflows/`
- `.ai/prompts/`
- `.ai/skills/`
- `.ai/tasks/`

任何涉及删除、协议核心或行为边界的修改，都必须先向用户说明目标与影响范围，并等待明确允许。
