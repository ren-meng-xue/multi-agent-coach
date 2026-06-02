# Implementation Plan: Video to Chinese Skill

## Goal

新增项目级 `video-to-chinese` skill，让 Agent 在用户提供 Bilibili / YouTube 视频链接、字幕文件或转写文本时，可以提取视频内容并转换为用户指定的中文格式。

---

## Scope

### In Scope

- 创建 `.ai/skills/video-to-chinese.md` 作为唯一规则正文。
- 创建 `.claude/skills/video-to-chinese/SKILL.md` 作为 Claude Code 薄注册入口。
- 设计默认中文输出模板，覆盖：
  - 标题
  - 一句话总结
  - 核心观点
  - 时间线笔记
  - 可执行建议
  - 术语表
  - 原始链接与来源说明
- 支持用户传入自定义格式；如果用户给了格式样例，则严格按样例产出。
- 明确处理顺序：
  - 优先使用用户提供的字幕/转写
  - 其次尝试平台公开字幕
  - 无字幕时提示需要用户提供转写或授权可用的转写工具
- 明确合规边界：不绕过权限、不抓取付费/私密内容、不输出超长逐字稿。

### Out of Scope

- 不接入真实 YouTube/Bilibili 下载器。
- 不加入 Whisper、yt-dlp、browser cookie 等运行时依赖。
- 不新增业务后端 API 或数据库表。
- 不改动现有 workflow/agent 协议。

---

## Execution Steps

1. 新增 `.ai/skills/video-to-chinese.md`
   - 写明触发方式：用户要求读取 B 站 / YouTube 视频并转成中文笔记、中文摘要、中文稿件、中文学习卡片等。
   - 写明输入类型：URL、字幕文件路径、文本转写、目标格式样例。
   - 写明工作流：识别来源 → 获取字幕/转写 → 清洗 → 翻译/润色 → 按格式输出 → 标注限制。
   - 写明默认输出格式和用户自定义格式优先级。

2. 新增 `.claude/skills/video-to-chinese/SKILL.md`
   - 保持项目约定的薄入口。
   - `description` 指向该 skill 的能力。
   - 正文只要求读取 `.ai/skills/video-to-chinese.md`。

3. 可选检查 `.ai/bin/sync-protocol propose`
   - 确认薄入口策略与项目同步工具一致。
   - 不执行自动 apply，避免触碰需要用户确认的行为边界。

4. 运行验证
   - `bash .ai/bin/lint-protocol`
   - 如 sync-protocol 支持 audit，则运行 `.ai/bin/sync-protocol audit`
   - 若命令失败，记录失败原因。

5. Review
   - 检查新增 skill 是否没有承诺绕过平台限制。
   - 检查输出格式是否能覆盖“特定格式的中文”的需求。
   - 检查 `.claude/skills` 是否保持薄入口。

---

## Deliverables

- `.ai/skills/video-to-chinese.md`
- `.claude/skills/video-to-chinese/SKILL.md`
- `.ai/tasks/20260601-video-to-chinese-skill/review.md`
- 最终 `handoff.md`

---

## Testing Strategy

- 协议验证：运行 `.ai/bin/lint-protocol`。
- 同步验证：运行 `.ai/bin/sync-protocol audit` 或 `propose`，确认新 skill 注册入口无漂移。
- 人工验收：用一个 YouTube/Bilibili URL + 一段示例字幕，检查 skill 说明能指导 Agent 输出中文结构化内容。
