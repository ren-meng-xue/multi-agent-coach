# Agent Skill

## 结构约定

- `.ai/skills/*.md` 是项目自定义 skill / protocol 的规则正文唯一来源。
- `.claude/skills/<name>/SKILL.md` 只作为 Claude Code 的 skill 注册入口，不重复维护规则正文。
- 可执行逻辑放在 `.ai/bin/<tool>`，skill 文件只描述触发条件、行为边界和调用入口。
- 如果 `.ai/skills` 与 `.claude/skills` 同名内容出现冲突，以 `.ai/skills/*.md` 为准，并将 `.claude/skills/<name>/SKILL.md` 收敛成薄入口。

## sync-protocol

- 规则正文：`.ai/skills/sync-protocol.md`
- Claude Code 注册入口：`.claude/skills/sync-protocol/SKILL.md`
- 执行工具：`.ai/bin/sync-protocol`
- 记忆写入辅助工具：`.ai/bin/sync-memory`
- `propose` 只生成同步提案，不写文件。
- `apply --confirmed` 只应用可机械验证的自动项，例如补 memory 索引、创建或收敛 Claude Code skill 薄注册入口。
- 删除、`CLAUDE.md`、workflow 拓扑、agent 职责、prompt 模板和 `.ai/skills/*.md` 行为边界必须人工确认后处理。

## 加载时机

仅在涉及以下主题时加载本记忆：

- 自定义 skill / protocol
- `.ai/skills`
- `.claude/skills`
- Claude Code skill 注册入口
- `.ai/bin/*` 协议工具
- sync-protocol / sync-memory
