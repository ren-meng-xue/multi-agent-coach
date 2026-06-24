# Every Claude Code Memory System Compared（六层记忆系统全比较）

来源：https://www.youtube.com/watch?v=UHVFcUzAGlM&t=305s
作者：Simon Scrapes
日期：2026-06-10

---

## 一句话总结

Claude Code 的记忆系统分六个层级，每层回答同一个问题：如何在正确时间把正确上下文注入 Claude——从免费的内置文件到跨工具的云端 Postgres 数据库，按需选择、可叠加使用。

---

## 核心观点

**1. 所有记忆系统解决同一个问题**
每个记忆系统都在回答：给 Claude 一个任务时，如何拉取正确上下文？差异只有两点——存储在哪里（文件结构）+ 如何检索（注入方式）。

**2. 上下文腐化（Context Rot）是核心病因**
随着加载的上下文越来越多，LLM 无法 100% 召回其中所有信息。解法不是塞更多内容，而是"按需加载"——claude.md 控制在 200 行以内，其余文件按需引用。

**3. 六层系统各有定位，可叠加**

- 层级 1-3 可以同时运行，文件夹结构兼容
- 层级 4 是逐字召回的本地 RAG 系统
- 层级 5 是知识库（非运营记忆）
- 层级 6 是跨工具共享记忆的基础设施层

**4. Anthropic 内部正在开发 Kairos**
Claude Code 源码泄露中发现了 Kairos——一个未发布的始终运行守护进程，持续监视项目、决定什么值得记住、在后台整合旧笔记。原生记忆只会越来越强。

**5. 钩子（Hooks）是自动注入的关键机制**
从层级 2 开始，通过 session start 钩子、user-prompt-submit 钩子实现"无需手动询问"的上下文注入。这是所有层级实现自动化的核心技术。

**6. Markdown 优先 vs. 黑盒存储**
MemSearch（层级 3）和 LLM Wiki（层级 5）坚持纯 Markdown，所有内容可读可迁移；Mem Palace（层级 4）和 Claude Mem 的底层存储不可直接阅读；Mem0 和 Recall 数据在第三方服务器。数据主权是选择标准之一。

---

## 六层系统时间线

| 时间点 | 层级        | 工具/方案                               | 核心能力                               |
| ------ | ----------- | --------------------------------------- | -------------------------------------- |
| 00:01  | **Layer 1** | claude.md + memory.md                   | 内置免费，按项目继承，200 行限制       |
| 00:06  | **Layer 2** | John Connolly 结构化记忆 + session hook | 目录化记忆 + 会话自动注入              |
| 00:17  | **Layer 3** | MemSearch（Zilliz，基于 OpenClaude）    | 语义向量搜索 + user-prompt-submit 钩子 |
| 00:23  | **Layer 4** | Mem Palace                              | 逐字 RAG，SQL + ChromaDB，本地存储     |
| 00:29  | **Layer 5** | LLM Wiki（Karpathy）/ Recall            | 互联知识库，非运营记忆                 |
| 00:34  | **Layer 6** | OpenBrain / Mem0                        | 跨工具共享，Postgres 数据库，MCP 接入  |

---

## 各层级详细对比

| 维度     | Layer 1       | Layer 2       | Layer 3           | Layer 4        | Layer 5   | Layer 6         |
| -------- | ------------- | ------------- | ----------------- | -------------- | --------- | --------------- |
| 存储     | Markdown 文件 | Markdown 文件 | Markdown + 向量   | SQL + ChromaDB | Markdown  | Postgres        |
| 检索方式 | 全量加载      | 钩子自动注入  | 语义搜索+钩子注入 | 符号索引+向量  | 知识图谱  | MCP 查询        |
| 数据位置 | 本地          | 本地          | 本地              | 本地           | 本地/云   | 自托管云        |
| 安装成本 | 零            | 低（<30 min） | 低（2 行命令）    | 中（1 命令）   | 中        | 高（30-45 min） |
| 月费用   | 免费          | 免费          | 免费              | 免费           | 免费/付费 | ~¥1/月          |
| 可读性   | 完全可读      | 完全可读      | 完全可读          | 不可直接读     | 可读      | 不可直接读      |
| 跨工具   | 否            | 否            | 否                | 否             | 否        | 是              |

---

## 可执行建议

1. **刚开始用 Claude Code** → 花 10 分钟把 claude.md 控制在 200 行内，引用外部文件；用 `/memory` 命令查看自动记忆状态。
2. **用了 1 个月以上** → 安装 Layer 2（John Connolly 方案），添加 session start 钩子自动注入 memory.md 索引，大多数人到这里就够了。
3. **文件越来越多、Claude 找不到历史决策** → 安装 Layer 3 MemSearch（`/plugin marketplace add zilliztech memsearch`）获得语义搜索；或 Layer 4 Mem Palace 实现逐字检索。
4. **需要整理大量文章/视频/播客** → 考虑 LLM Wiki（Karpathy 方案）或 Recall。
5. **在多个 AI 工具间切换（手机 ChatGPT + 桌面 Claude）** → OpenBrain 或 Mem0。
6. **运行 "reorganize memory" 定期维护** → Layer 2 设置完成后定期执行，删除空文件、整合过时内容、更新交叉引用。

---

## 关键术语

| 术语                      | 解释                                                             |
| ------------------------- | ---------------------------------------------------------------- |
| Context Rot（上下文腐化） | 上下文加载越多，LLM 的有效召回率越低                             |
| Session Start Hook        | 会话启动时自动执行的脚本，可注入记忆索引                         |
| User Prompt Submit Hook   | 每次提交提示前触发的钩子，MemSearch 用此注入语义匹配             |
| Dreaming                  | OpenClaude 的后台进程，将频繁出现的日常笔记提升为长期记忆        |
| AAAK                      | Mem Palace 使用的密集符号语言，让 LLM 快速扫描索引               |
| Memory Palace             | 古代记忆术，Mem Palace 用翼/房/抽屉结构模拟                      |
| Kairos                    | Anthropic 内部未发布的记忆守护进程（Claude Code 源码泄露中发现） |
| OpenBrain                 | 基于 Supabase Postgres 的跨 AI 工具共享记忆方案                  |

---

## 适合谁看

- **Claude Code 日常用户**：想提升记忆可靠性、减少重复输入上下文的开发者和创作者
- **Agentic 系统构建者**：需要跨会话、跨 agent、跨工具共享上下文的人
- **AI 工作流重度用户**：同时使用 ChatGPT、Claude、Cursor 等多个 AI 工具的人

---

## 来源与限制

- 视频发布时间约为 2026 年初，MemSearch、Mem Palace 等工具的 API 和安装方式可能已有变化，使用前建议查看各工具最新文档。
- Kairos 在视频录制时尚未公开发布，当前状态需自行确认。
- 字幕轨道为英文自动字幕，翻译为简体中文；个别术语（如 AAAK、Zilliz）保留原文。
- 视频作者的使用场景为"Agentic 业务操作系统"，部分建议（如跳过 Level 5 知识库）基于该场景，不同场景下结论可能不同。
