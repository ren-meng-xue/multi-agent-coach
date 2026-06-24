# 14 个让 Claude Code 变超级工具的设置决策

## 一句话总结

不要把 Claude Code 当聊天机器人用——这 14 个设置决策能把它变成一个自主运行业务的 agentic 系统。

---

## 核心观点

1. **Ultra Code / 动态工作流** — 输入关键词 `ultra code` 后，Claude 会为该任务自主设计工作流，拆分为多个 sub-agent 并行执行，支持 6 种模式：分类路由、扇出合成、对抗验证、生成过滤、淘汰赛、循环直到完成。适合长复杂任务，但 token 消耗极大（演示中 26 个 agent、13 分钟、数十万 token）。

2. **Auto Mode（自动权限模式）** — `Shift+Tab` 两次切换。不同于"审批一切"的默认模式，也不是危险的 `--dangerously-skip-permissions`，而是用分类器自动判断每个操作的风险，只在真正危险时打断用户。可以安心离开桌子让 Claude 干活。

3. **自主长任务：`/loop` + `/goal`** — `/loop` 设置重复间隔（最长 3 天），`/goal` 设置停止条件，两者组合后 Claude 会不断自我检查是否达成目标，直到条件满足才停止。演示：每天自动整理 Gmail 收件箱。

4. **正确构建 Skills** — 好的 skill.md 应具备：① 不超过 200 行的分步指南；② 渐进式披露（详细参考上下文按需加载，存于独立文件夹）；③ 自学习机制（每次运行后把反馈存入 skill 的 rules 区，下次读取）。Anthropic 官方有 skill creator skill 可辅助构建。

5. **Skill Systems（技能系统）** — 多个 skill 串联成流水线，前一个输出成为下一个输入。以社交内容创作系统为例，18 个 skill 如乐高积木组合，其中品牌语气、视觉风格等 skill 可被多个系统共用，改一处更新所有系统。

6. **MCP vs CLI 工具连接** — MCP 是持久连接，每次会话都把工具定义加载到上下文（即使未使用也消耗 token）。CLI 是按需调用，用完即忘。规则：高频、复杂交互（CRM、数据库）→ MCP；低频、简单操作（发消息、触发脚本）→ CLI。

7. **语义记忆层** — Claude Code 原生记忆靠关键词搜索历史会话，容易失真。推荐用开源语义搜索框架（memsearch、Hermes、openclaw）构建向量数据库记忆层，按语义（而非关键词）检索历史上下文，解决跨会话记忆衰退问题。

8. **文件夹结构即 Agentic OS** — 在 claude.md 中定义不同任务应加载哪些文件夹的上下文（品牌声音、客户信息、视觉规范等），Claude 会在执行对应任务时自动注入正确上下文。这是提升输出质量最立竿见影的单一操作。

9. **正确规划：Plan 要存入项目文件夹** — Plan mode 默认把计划存到项目外的临时目录，上下文压缩后 Claude 会丢失原始计划。解决方案：把计划写成项目内的文件（PRD/plan.md），Claude 可随时重读，不会因 context compaction 而迷失。

10. **老虎机理论：`/rewind` 而非争论** — Claude 输出错误时，不要继续"不对，修一下"，因为每次纠错都把损坏代码叠加进上下文，越改越差。正确做法：用 `/rewind` 回退到出错前的检查点，加上额外上下文，重新执行。

11. **Agent View（多 Agent 并行视图）** — `claude agents` 命令打开多 agent 管理界面，按仓库和状态分组显示所有进行中的 agent，可快速查看/回复。相比过去切换多个终端窗口，效率大幅提升。

12. **可移植性：逃生路线** — 用开放标准构建，避免锁定 Claude Code：`agents.md`（等同于 claude.md，Codex/Cursor/Copilot 均原生支持）、`skills.md`（开放标准）、MCP/CLI 工具连接（各主流工具均支持）。

13. **手机远程控制：VPS + Tmux + Telegram** — 原生 channel（Telegram/Discord）本身支持手机遥控，但会话断开后任务停止。解决方案：在 VPS 上运行 Claude Code，用 Tmux 保持持久会话，通过 Telegram 派发任务和审批操作，实现真正的"派出去就走"。

14. **Skills vs Sub-agents 的区别** — Skills = Claude 知道怎么做（方法论）；Sub-agents = 谁去做（执行者，有独立上下文）。使用 sub-agent 的三个场景：① 任务会产生大量不需要回流主会话的上下文；② 需要不同工具/权限/模型；③ 需要并行执行多个相同任务。使用 skill 的场景：需要中间上下文留在主会话中。

---

## 时间线笔记

| 时间点 | 内容                                                                |
| ------ | ------------------------------------------------------------------- |
| 00:00  | 开场：大多数人把 Claude Code 当聊天机器人，少数人在用它运营整个业务 |
| 00:43  | #1 Ultra Code / 动态工作流：6 种 agent 编排模式                     |
| 05:40  | #2 Auto Mode：Shift+Tab×2，智能权限分类器                           |
| 06:27  | #3 自主长任务：/loop + /goal 组合，Gmail 整理演示                   |
| 09:14  | #4 正确构建 Skills：200 行限制、渐进披露、自学习                    |
| 10:53  | #5 Skill Systems：18 个 skill 组成的社交内容流水线                  |
| 13:20  | #6 MCP vs CLI：持久连接 vs 按需调用，token 成本权衡                 |
| 15:09  | #7 语义记忆层：memsearch/Hermes/openclaw 解决跨会话记忆             |
| 17:25  | #8 文件夹结构即 Agentic OS：claude.md 定义上下文路由                |
| 18:52  | #9 规划的正确姿势：Plan 存入项目文件夹以抗 compaction               |
| 20:34  | #10 老虎机理论：/rewind 而非反复纠错                                |
| 21:50  | #11 Agent View：claude agents 命令管理并行任务                      |
| 22:46  | #12 可移植性：agents.md / skills.md 开放标准                        |
| 24:01  | #13 手机远程：VPS + Tmux + Telegram 派发并离开                      |
| 25:50  | #14 Skills vs Sub-agents：上下文隔离决定使用哪个                    |

---

## 可执行建议

- **立即可做**：在 claude.md 中加入文件夹路由规则，定义不同任务加载哪些上下文目录（#8，最高杠杆单一操作）
- **今天可做**：把 Plan mode 的输出改为写入项目内文件，而非依赖临时目录（#9）
- **本周可做**：为现有 skill 补充 progressive disclosure 结构和自学习 rules 区（#4）
- **习惯养成**：输出出错时强制用 /rewind 而非追加纠错（#10，违反人类直觉但效果显著）
- **架构升级**：把大 skill 拆解为可复用的 Lego block，支持跨 skill system 共用（#5）
- **工具连接**：审查当前 MCP 配置，把低频操作改为 CLI 调用以节省 token（#6）

---

## 关键术语

| 术语                   | 含义                                                                |
| ---------------------- | ------------------------------------------------------------------- |
| Ultra Code             | 触发动态工作流的关键词，让 Claude 自主设计 multi-agent 执行计划     |
| Dynamic Workflow       | Claude 为特定任务自动编排的 sub-agent 协作流程                      |
| Auto Mode              | 基于分类器的智能权限模式，Shift+Tab×2 切换                          |
| /loop                  | 设置任务重复执行间隔（最长 3 天）的命令                             |
| /goal                  | 设置任务停止条件，未达成则持续派发 agent 的命令                     |
| /rewind                | 回退到会话中某个历史检查点的命令                                    |
| Skill System           | 多个 skill 串联成端到端工作流的架构模式                             |
| Progressive Disclosure | skill 中详细参考上下文按需加载的设计原则                            |
| Agentic OS             | 以文件夹结构+claude.md路由实现上下文按需注入的系统架构              |
| memsearch              | 开源语义记忆框架，用向量数据库实现跨会话语义检索                    |
| agents.md              | 跨工具通用指令文件（等同于 claude.md），Codex/Cursor/Copilot 均支持 |
| Context Compaction     | Claude Code 在上下文增长时自动压缩历史的机制，会导致计划丢失        |

---

## 适合谁看

- 已入门 Claude Code 但仍主要用于单次对话的用户
- 想将 Claude Code 接入日常业务流程（邮件、CRM、内容生产）的创业者/独立开发者
- 正在构建 multi-agent 系统或 skill 库的技术团队

---

## 来源与限制

- **视频来源**：[14 GENIUS Ways to Give Claude Code SUPERPOWERS](https://www.youtube.com/watch?v=mNawxNjrR_E)，Simon Scrapes 频道
- **字幕轨道**：英文原声（en），非自动翻译轨道
- **内容时效**：截至 2026-06-13，视频发布时间约为 2025 年底至 2026 年初
- **局限性**：部分功能（如 `/goal`、`claude agents`）为较新特性，版本可能有更新；Ultra Code 的 token 消耗较高，适用场景有限；VPS + Tmux 方案需要一定运维基础
