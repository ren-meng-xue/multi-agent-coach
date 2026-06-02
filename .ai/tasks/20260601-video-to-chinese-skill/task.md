# Task: Video to Chinese Skill

## Background

用户希望新增一个项目自定义 skill，用于读取 B 站和 YouTube 视频内容，并转换成指定格式的中文产物。当前仓库已有自定义 skill 约定：

- 规则正文放在 `.ai/skills/*.md`
- `.claude/skills/<name>/SKILL.md` 只作为 Claude Code 的薄注册入口
- 可执行逻辑如需要，应放在 `.ai/bin/<tool>`

本任务先按项目协议完成 plan 卡点，确认后再进入 implementation。

---

## Goal

新增一个可被 Agent 调用的 `video-to-chinese` skill，支持输入 Bilibili / YouTube 视频链接或已有字幕/转写文本，并按用户指定的中文格式输出。

---

## Scope

### In Scope

- 新增 `.ai/skills/video-to-chinese.md`，定义触发条件、输入要求、处理流程、输出格式和限制。
- 新增 `.claude/skills/video-to-chinese/SKILL.md` 薄入口，遵循项目现有 skill 注册规则。
- 如需要，新增轻量 `.ai/bin/video-to-chinese` 辅助脚本，用于从本地文件标准化读取/输出；网络下载能力只做可选边界说明，避免默认依赖不稳定平台抓取。
- 增加最小验证，确保 skill 文件存在、薄入口指向正确、协议 lint 不回归。

### Out of Scope

- 不绕过 Bilibili / YouTube 的访问控制、登录、付费、地区限制或反爬限制。
- 不承诺直接下载无字幕视频的音频并做 ASR，除非后续用户明确要求接入具体转写工具。
- 不删除或重写现有 skill / 协议文件。
- 不实现前端页面。

## Acceptance Criteria
- [ ] `.ai/skills/video-to-chinese.md` 描述清晰，能指导 Agent 对 Bilibili / YouTube 视频进行字幕获取、中文转写、结构化整理。
- [ ] `.claude/skills/video-to-chinese/SKILL.md` 是薄入口，规则正文指向 `.ai/skills/video-to-chinese.md`。
- [ ] skill 支持“用户指定格式”；未提供格式时使用默认中文笔记格式。
- [ ] 明确版权、平台限制和无法读取视频时的降级路径。
- [ ] 通过项目相关协议检查或说明无法运行的原因。
