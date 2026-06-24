# AI Agent 完整架构面试题全解析

## 一句话总结

Agent 架构面试的核心不是背七大组件名词，而是能说清"生产中一切 agent 都是同一个 while loop"，再深入三个工程战场：工具设计、上下文压缩、编排配置旋钮——说到第三层及格，第五层优秀。

## 核心观点

1. **教科书七大组件是及格线，不是终点** — 感知层、推理引擎、短期/长期/情景三层记忆、工具使用、编排、多 Agent 协作、安全治理，背出来能及格但面试官一追问"你会用 ReAct 还是 Plan-and-Execute"就会露馅，因为这两个在生产里根本不是独立架构。

2. **生产中所有现代 Agent 架构都是同一个 while loop 的变体** — 2026 年 3 月 Claude Code 源码泄露（51.2 万行），验证了 Claude Code / Cursor / Manus / Devin 四款产品核心架构完全一致：模型调用 → 有 tool call 就执行 → 没有就结束循环。ReAct 是给这个循环加了显式思考步骤，Plan-and-Execute 是用 TODO 文件做软规划让规划和执行交错，都不是新架构。Anthropic 原话："agent 实现很简单，就是 LLM 在循环中基于环境反馈调用工具。"

3. **工具设计是性能天花板，比换模型更有效** — Anthropic 在 SWE-bench 上仅用 2 个工具（bash + edit）加精心的工具描述，就达到 49%。数据警示：工具数量存在悬崖效应——SpeakEasy 团队测试显示 10 个工具时表现完美，107 个时大小模型同时出现频繁幻觉和错误（非线性退化，是崩塌）。GitHub Copilot 将工具从 40 个精简到 13 个，配合智能路由，基准提升 2~5 个百分点。

4. **ACI 是工具设计的理论框架，有五条原则** — ACI（Agent Computer Interface）类比 HCI，来自 SWE-agent 论文，Anthropic 借用并总结五条工具设计原则：选对工具（为 agent 重新设计，而非包装现有 API）、命名空间化、返回语义化信息（非技术标识符）、优化 token 效率、精心编写工具描述（Anthropic 称其为"最有效的方法之一"）。工具过多时的优雅解法：不删除工具定义（会导致 KV cache 失效），而是用 logit masking 遮蔽不可用工具 token，配合一致前缀命名实现动态工具组切换。

5. **上下文管理（context engineering）是隐藏战场，也是面试加分项** — Context rot 是结构性问题：ICML 2025 NOLA 测试发现 13 个 LLM 中 11 个在仅 32K token 时性能降至短上下文基线的一半以下。JetBrains NeurIPS 2025 实验发现 Observation Masking（占位符替换旧工具输出，保留推理历史）比不管理上下文便宜 52%，解决率还高 2.6%。反直觉：LLM 摘要反而让 agent 多跑 13%~15% 步骤（平滑了停止信号），最佳方案是 Masking 一线防御 + 偶发 LLM 摘要兜底。

6. **Agent 类型分类要先说清维度，否则无限膨胀** — 分类混乱的根源是维度被混用（决策行为/系统架构/应用角色）。最实用的是 Anthropic 三层编排架构：增强型 LLM（LLM + 检索 + 工具 + 记忆）→ Workflow（预定义代码编排多 LLM 调用，5 种模式）→ 真正的 Agent（LLM 自主决定流程，即 while loop）。Russell & Norvig 经典五类可开场提一句表示知道理论，现代 LLM agent 天然是 goal-based + learning 的混合体，经典分类区分度低。

7. **不同 Agent 类型骨架相同，差异在三个配置旋钮** — 工具集（最大差异源：coding agent 用文件读写和终端，客服 agent 用数据库查询和退款接口，research agent 用搜索和爬虫）；System prompt（不只是指令，还是权限系统，同一骨架可以 plan 模式只读、implementation 模式完整编辑权限）；编排模式（单 agent 在大多数场景比多 agent 更可靠，先穷尽单 agent 再考虑多 agent）。

## 时间线笔记

| 时间点 | 内容                                                                 |
| ------ | -------------------------------------------------------------------- |
| 00:00  | 引入：这题坑多，背名词没用                                           |
| 00:28  | 教科书七大组件：感知/推理/记忆/工具/编排/多 Agent/治理               |
| 00:48  | 及格但不出彩，面试官会追问推理模式                                   |
| 01:09  | 生产真相：所有现代 agent 都是同一个 while loop                       |
| 01:14  | 一手证据：Claude Code 51.2 万行源码验证四大产品架构一致              |
| 01:44  | 99% 代码是围绕循环的工程系统，不是循环本身                           |
| 01:53  | ReAct = while loop + 显式思考步骤；Plan-and-Execute = 软规划交错执行 |
| 02:21  | Anthropic 原话引用 + "复杂度杀死迭代速度"                            |
| 02:39  | 答题策略：先说"while loop"，再展开三大工程战场                       |
| 02:59  | 战场一：工具设计（性能天花板）                                       |
| 03:04  | SWE-bench 数据：2 个工具 + 好描述 = 49%                              |
| 03:30  | 工具悬崖效应：107 个工具时大小模型均崩塌                             |
| 03:47  | GitHub Copilot 精简工具案例                                          |
| 04:02  | ACI 框架 + 五条工具设计原则                                          |
| 04:37  | 工具过多的优雅解法：logit masking + 前缀命名                         |
| 05:06  | 战场二：上下文管理（隐藏战场）                                       |
| 05:15  | Context engineering 概念 + NOLA 测试数据                             |
| 05:42  | JetBrains NeurIPS 2025：Observation Masking 省 52% 成本              |
| 06:04  | 反直觉：LLM 摘要让 agent 多跑 13~15% 步骤                            |
| 06:17  | 最佳方案：Masking 一线 + LLM 摘要兜底                                |
| 06:23  | Claude Code 分层压缩策略 + 子 agent 隔离                             |
| 06:50  | Agent 类型分类：如何答不踩坑                                         |
| 07:00  | 分类混乱根源：维度被混用                                             |
| 07:15  | Anthropic 三层编排架构（最实用维度）                                 |
| 07:37  | Russell & Norvig 经典五类的使用方式                                  |
| 07:54  | 三个配置旋钮：工具集/system prompt/编排模式                          |
| 08:33  | 五层面试回答框架 + 及格/优秀分界线                                   |
| 09:26  | 三大避坑：不列名词/不混淆 chatbot/不过度吹嘘多 agent                 |

## 五层面试回答框架

| 层次   | 内容                                                               | 水准       |
| ------ | ------------------------------------------------------------------ | ---------- |
| 第一层 | 七大组件：感知/推理/记忆/工具/编排/多 Agent/治理                   | 背了书     |
| 第二层 | while loop 本质 + ReAct/Plan-and-Execute 是学术命名非独立架构      | 理解了原理 |
| 第三层 | 工具设计：ACI 五原则 + SWE-bench 数据 + 悬崖效应                   | 及格 ✅    |
| 第四层 | 上下文管理：context rot + Observation Masking 数据 + 子 agent 隔离 | 良好       |
| 第五层 | Agent 类型：三层编排架构维度 + 三个配置旋钮本质差异                | 优秀 ⭐    |

## 三大避坑

| 坑                           | 表现                                   | 正确做法                                                   |
| ---------------------------- | -------------------------------------- | ---------------------------------------------------------- |
| 只列名词不解释机制           | "Agent 有感知层、推理引擎、记忆系统……" | 每个组件说清楚为什么存在、解决什么问题                     |
| 把 agent 和 chatbot 混为一谈 | 把对话系统当 agent 举例                | 强调 agent 的核心区别：自主循环 + 工具使用                 |
| 过度吹嘘多 agent             | 设计上来就上多 agent 架构              | Anthropic 和 OpenAI 均明确：先穷尽单 agent，再考虑多 agent |

## 可执行建议

- **面试开场**：先说"所有现代 agent 本质是 while loop"，立刻区别于只背名词的候选人，再展开三个工程战场。
- **提 SWE-bench 数据**：2 个工具 + 好描述 = 49%，是说明"工具描述投入应等同于 UI 设计"最有力的支撑。
- **提悬崖效应数据**：107 个工具时崩塌（非线性退化），面试官常见的错误认知是"工具多一点没关系"，这个数据直接纠偏。
- **提 Observation Masking**：NeurIPS 2025 + JetBrains 组合，省 52% 成本还提高 2.6% 解决率，而且反直觉（LLM 摘要反而更差），是上下文管理的最佳加分点。
- **分类题的答法**：先说"分类维度很多，我用 Anthropic 的编排架构维度来答"，然后展开三层，开头承认 Russell & Norvig 经典理论，避免显得不知道学术背景。
- **工程实践中**：工具设计参照 ACI 五原则，工具过多时用 logit masking 而非删除定义（否则 KV cache 失效），子 agent 输出限制在 1000~2000 token 防止主上下文膨胀。

## 关键术语

| 术语                            | 说明                                                              |
| ------------------------------- | ----------------------------------------------------------------- |
| while loop                      | 现代 agent 的核心实现：模型调用 → 有 tool call 则执行 → 无则退出  |
| ReAct                           | while loop 的一种变体，在推理步骤和行动步骤之间显式交替           |
| Plan-and-Execute                | 用 TODO 文件做软规划，规划与执行交错进行（非严格先后）            |
| ACI（Agent Computer Interface） | 类比 HCI 的工具设计框架，来自 SWE-agent 论文，Anthropic 借用      |
| Context Rot                     | 随上下文 token 增加，模型回忆能力下降的结构性问题                 |
| Context Engineering             | Anthropic 提出的概念：找到最小高信号 token 集合最大化任务成功率   |
| Observation Masking             | 用占位符替换旧工具输出但保留推理历史，JetBrains 验证可省 52% 成本 |
| Logit Masking                   | 在解码时屏蔽特定工具 token 的概率，实现动态工具组控制             |
| KV Cache                        | 模型键值缓存，工具定义删除会导致 cache 失效，增加推理成本         |
| 三层编排架构                    | Anthropic 提出：增强型 LLM → Workflow → 真正的 Agent              |
| 三个配置旋钮                    | 工具集 / System Prompt / 编排模式，决定不同 agent 类型的实际差异  |
| SWE-bench                       | 评估 AI agent 软件工程能力的标准基准测试                          |

## 适合谁看

- 正在准备 AI 工程师/LLM 应用工程师面试，预期被问 agent 架构的候选人
- 想区分"背了文档"和"真正理解 agent"的技术面试官
- 正在构建 agent 系统、想了解工具设计和上下文管理最新工程实践的开发者
- 想了解 Claude Code 等产品架构真相的技术研究者

## 来源与限制

- 字幕轨道为 B 站 AI 自动生成中文字幕（`ai-zh`），视频原声为中文，整体质量良好，部分技术词汇存在 AI 转写偏差：
  - "Crowd code" → Claude Code
  - "mace" → Manus（AI agent 产品）
  - "NOLIA 测试" → NOLA 测试（ICML 2025 论文中的长上下文测试）
  - "new ips" → NeurIPS 2025
  - "russell and novc" → Russell & Norvig（经典 AI 教材作者）
  - "reflect model based go base" → reflexive / model-based / goal-based（R&N 五类 agent）
  - "s w e bench" → SWE-bench
  - "字节dear flow2.0" → 字节跳动 DeerFlow 2.0
  - "bite bite go" → 某博主的网名（具体人物不确定）
  - "VENUS" → 某 agent 产品（具体名称不确定）
- JetBrains NeurIPS 2025 数据（Observation Masking 省 52%）为视频发布时最新研究，验证链接未提供
- SWE-bench 数据随模型迭代快速变化，49% 为当时（Claude 3.5 Sonnet 时代）数据，现已大幅超越
- 视频未包含代码演示，专注于面试场景的概念和数据引用
