# Claude Code 概念全解：普通人也能看懂的完整指南

> **来源视频**：[Every Claude Code Concept Explained for Normal People — Simon Scrapes](https://www.youtube.com/watch?v=ZlDnsf_DOzg)（2026 年 2 月）
> **正文来源**：[sabrina.dev 书面整理版](https://www.sabrina.dev/p/every-claude-code-concept-explained-beginners)（2026 年 3 月 16 日更新）
> **整理日期**：2026-06-01

---

## 一句话总结

这是一期从零开始、按难度分 9 个阶段的 Claude Code 概念扫盲视频，覆盖终端入门、对话管理、记忆与技能、MCP 连接外部工具、到多 Agent 并行——帮助没有技术背景的人真正用起来 Claude Code。

---

## 核心观点

1. **Claude Code 不是聊天框，是能直接改你电脑文件的执行层**——和你描述问题不同，它会真正打开文件、运行命令、做事。
2. **CLAUDE.md 是你的"永久说明书"**——把业务规则、写作风格、工具偏好一次写进去，每次对话自动加载，彻底摆脱重复解释。
3. **MCP（模型上下文协议）是打通外部世界的桥梁**——连上 Notion、Google Drive、Slack、Airtable 等工具，Claude 就能直接操作，不再只是"给建议"。
4. **Skills（技能文件）让重复流程一键触发**——用一个 Markdown 文件封装完整工作流，一条斜杠命令搞定转录→总结→发布→入库的全套操作。
5. **Hooks（钩子）是无人值守的质量防线**——在 Claude 执行前/后自动跑脚本，拦截违禁词、校验字数、检查品牌规范，不用手动审核。

---

## 时间线笔记（按 9 大阶段）

| 阶段 | 概念 | 核心内容 |
|---|---|---|
| 第 1 阶段：入门 | 终端 / 安装 / 文件访问 / 读图 | Claude Code 在终端运行，可直接读写本机文件和图片 PDF；Max 套餐 $100–200/月，Pro $20/月 |
| 第 2 阶段：第一批真实任务 | 工具调用 / 如何提问 / CLAUDE.md / Plan 模式 | 越具体越好；CLAUDE.md 一次配置永久生效；Plan 模式先出方案再执行，你来审批 |
| 第 3 阶段：大脑运作原理 | 上下文窗口 / Token 成本 / 模型选择 | 上下文像白板会写满；Opus 最强最贵、Sonnet 日常主力、Haiku 轻量最快；简单任务用便宜模型 |
| 第 4 阶段：管理对话 | /compact / /clear / 会话恢复 | `/compact` 压缩对话释放空间；`/clear` 彻底重开；`claude --resume` 跨天接续上次进度 |
| 第 5 阶段：控制 Claude | 权限模式 / 努力级别 / 中断 | 可设置每步需确认或全自动；`ultrathink` 触发最深度推理；Escape 键随时中断不丢进度 |
| 第 6 阶段：审查与教 Claude | VS Code / 记忆 / 项目 vs 全局作用域 | VS Code 高亮显示改动便于 review；Memory 是 Claude 跨对话积累的个人笔记；项目规则 vs 全局规则分开管理 |
| 第 7 阶段：技能与自动化 | 斜杠命令 / Skills / Hooks | Skills 是封装工作流的 MD 文件；Hooks 是执行前后自动触发的守卫脚本 |
| 第 8 阶段：连接真实世界 | 网页浏览 / MCP / Perplexity MCP | MCP 连接 Google Drive、Slack、Notion 等；Perplexity MCP 让 Claude 能多源引用搜索 |
| 第 9 阶段：Agent 与调度 | Subagents / 远程控制 / /loop / Git | 多个子 Agent 并行跑；手机远程继续 PC 上的会话；`/loop` 定时任务（有效期 3 天）；Git 做版本回滚 |

---

## 可执行建议

- **第一周**：安装 Claude Code，完成文件读写，建好你的 CLAUDE.md，打开 Plan 模式养成"先审批再执行"的习惯
- **第二到四周**：学会用 `/compact` 管理上下文，配置 Memory 让 Claude 记住你的偏好，动手写第一个 Skill 文件自动化最高频任务
- **第二个月起**：接入最常用的 MCP（建议从 Notion 或 Google Drive 开始），配置 Hooks 做自动质检，试用 Subagents 并行跑多任务

---

## 关键术语

| 术语 | 中文解释 |
|---|---|
| Claude Code | Anthropic 出品的 AI 命令行工具，直接在终端操作本机文件和执行命令 |
| CLAUDE.md | 项目指令文件，每次对话自动加载，相当于给 Claude 的"永久说明书" |
| Context Window（上下文窗口） | Claude 单次对话能"记住"的内容上限，满了会自动压缩旧内容 |
| Token | 文本计量单位，输入和输出都消耗 Token，直接影响费用 |
| Plan Mode（计划模式） | Claude 先输出完整执行方案，等你确认后再动手 |
| Slash Commands（斜杠命令） | 内置快捷操作，如 `/clear`、`/compact`、`/model` 等 |
| Skills（技能文件） | 用 Markdown 写的自定义工作流，一条命令触发整套自动化 |
| Hooks（钩子） | 执行前/后自动运行的脚本，用于质量守卫和规则强制 |
| MCP（模型上下文协议） | 连接外部应用（Notion、Slack、Airtable 等）的标准协议 |
| Subagents（子 Agent） | Claude 自动拆分任务、并行处理的多线程工作单元 |
| /loop | 定时重复任务指令，默认有效期 3 天 |
| Ultrathink | 触发最深度推理模式的关键词 |

---

## 适合谁看

- **想用 AI 提效但不会写代码的业务人员、创业者、产品经理**：视频用"普通人语言"解释每个概念，不需要技术背景
- **已经在用 Claude.ai 但想进阶到 Claude Code 的用户**：了解两者差异，以及 Claude Code 能做到哪些 Claude.ai 做不到的事
- **希望把 AI 真正嵌入工作流而不是"偶尔问一问"的人**：MCP + Hooks + Skills 的组合是核心收益

---

## 来源与限制

- **来源**：sabrina.dev 书面整理版（对应视频由 Simon Scrapes 发布，2026 年 2 月）
- **限制**：视频字幕无法直接抓取，内容基于与视频对应的公开书面整理版；时间线时间点为阶段性估算，非精确字幕时间戳；视频中具体演示画面细节未覆盖
