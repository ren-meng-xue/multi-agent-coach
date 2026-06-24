# AI Agent 记忆 · 面试答题框架

> 面向 multi-agent-coach 项目求职者的面试备战材料。
> 核心思路:先用通用知识体系撑起系统性认知,再把本项目里真做过的记忆系统讲成"我亲手实现过"的 STAR 故事。
> 生成日期:2026-06-16

---

## 一、通用知识骨架(展示系统性认知)

### 1. 短期记忆 vs 长期记忆

| 维度     | 短期(Working / Context)                   | 长期(Long-term)                  |
| -------- | ----------------------------------------- | -------------------------------- |
| 载体     | LLM 上下文窗口、单次会话历史              | 外部存储(DB / 向量库 / 知识图谱) |
| 生命周期 | 会话结束即失效                            | 跨会话持久化                     |
| 容量     | 受 token window 限制                      | 理论无上限,受检索成本约束        |
| 用途     | 当前任务状态、ReAct scratchpad、最近 N 轮 | 用户画像、历史经验、技能         |

一句话:**短期是"这次对话里我知道什么",长期是"我跨越所有对话累积了什么"。** 工程难点在于"如何在海量历史里只把相关那部分捞回 context"。

### 2. 长期记忆三类细分(认知心理学映射,这是加分点)

- **情景记忆(Episodic)**:具体事件,带时间戳。"用户上周那场面试分布式题答得好。"
- **语义记忆(Semantic)**:抽象事实,脱离场景。"这个用户技能栈是 Python + 微服务。"
- **程序性记忆(Procedural)**:怎么做的技能/规则,固化在 prompt/工具/工作流。"遇到 junior 别一上来问 benchmark。"

很多人只会说"短期 vs 长期",你能把长期拆成 episodic/semantic/procedural 并举例,立刻显出系统性。

### 3. 记忆五阶段生命周期

```
写入/抽取 → 存储 → 检索 → 更新/反思 → 遗忘
Encoding   Storage  Retrieval  Reflection  Forgetting
```

- **写入/抽取**:不是存原文,而是 LLM 结构化提取"值得记住的东西"。
- **存储**:选型决定能力——关系表/JSONB、向量库、知识图谱、文档。
- **检索**:核心矛盾是"召回率 vs context 预算"。手段:精确查询、向量相似度、关键词、时间窗、重要性排序。
- **更新/反思**:记忆不是 append-only,要去重、合并、计数、LLM 二次总结出高阶洞察。
- **遗忘**:主动淘汰(FIFO / 时效衰减 / 重要性加权)。遗忘不是 bug,是控制膨胀和保鲜的必需机制。

### 4. 常见技术实现与代价

| 技术            | 解决什么               | 代价/风险                          |
| --------------- | ---------------------- | ---------------------------------- |
| Context 全塞    | 简单无检索成本         | token 爆炸、lost-in-the-middle     |
| 向量库 + RAG    | 海量记忆语义检索 Top-K | embedding 成本、阈值难调、召回噪声 |
| 知识图谱        | 实体关系、多跳推理     | 构建维护成本高                     |
| 摘要压缩        | 长历史压成短摘要       | 信息有损                           |
| LLM 反思总结    | 提炼高阶洞察           | 额外调用、幻觉                     |
| 重要性/时效衰减 | 控膨胀、保鲜           | 权重设计复杂                       |

### 5. 业界参考(展示视野)

- **MemGPT**:LLM 类比操作系统,主存(context)+ 外存(归档记忆),函数调用做自主分页——**有限 context 之上做无限记忆的虚拟内存管理**。
- **Generative Agents(斯坦福小镇)**:**memory stream** + 检索三因子打分(**recency × importance × relevance**)+ **reflection**(周期聚合观察成高层洞察)。
- **LangGraph / LangMem**:LangGraph 用 **State(TypedDict)** 传短期状态 + **checkpointer** 持久化;LangMem 封装长期记忆的读写。

---

## 二、结合本项目的 STAR 叙述("我亲手实现过")

> **项目一句话**:multi-agent-coach 是 AI 面试教练,五阶段 Prepare → Interview → Evaluate → Coach → 画像积累,多 Agent 协作。我设计实现了它的**分层跨会话记忆系统**。

### STAR 故事 1:从零搭建跨 session 候选人长期记忆(主线)

- **S 场景**:核心价值是"长期教练关系"——要像真人记住你前几场表现。难点:单场 working memory 随 session 结束消失,撑不起"你三场都缺量化"这种跨会话洞察。
- **T 任务**:设计跨 session 持久化记忆层,既累积画像,又能低成本注入 Coach 的 prompt。
- **A 做法**(对齐知识骨架):
  - **抽取**:每轮面试后 `evaluator_node` 调 LLM 结构化输出 `TurnEvaluation`,提取 `candidate_level`(语义)、`latent_signals`(隐含能力,如 `workflow_orchestration`)、`missing_dimensions`(如 `quantification`)。关键:抽**高级概念信号而非实现细节**,稳定分类才能做趋势追踪。
  - **存储**:落 PostgreSQL `candidate_memory` 表,PK 是 Clerk `user_id`。三核心字段:`latest_level`(覆盖)、`cumulative_signals`(JSONB,去重保序)、`weakness_tags`(JSONB,每条 `{tag, count, last_seen_at}`)。**有意用 JSONB 而非子表**:放弃 SQL 聚合灵活性,换 prompt 直接序列化注入 + 少 JOIN。**这期不上向量库**,因为画像是结构化数据,v0 不需要语义检索。
  - **反思**:`upsert_candidate_memory()` 原子合并——信号去重追加;弱点标签已存在则 `count++` 刷新 `last_seen_at`。**计数本身就是轻量反思**:跨轮重复弱点被自动加权,无需每次重跑全量 LLM 提取。
  - **遗忘**:`cumulative_signals` FIFO 上限 **50 条**,控制 prompt token 预算恒定。
  - **检索/注入**:Coach 是 LangGraph 线性子图 `load_memory → review → plan → persist`。`load_memory_node` 把记忆拉进 `CoachState`,`review/plan` 节点 `json.dumps` 后以 `【候选人长期记忆】` 嵌进 prompt,LLM 基于【长期记忆 + 最近报告 + 简历摘要 + 岗位情报】四层生成复盘。
- **R 结果**:真正跨会话教练——能说"你三场都缺量化"而非泛泛建议;Dashboard 直接消费 `weakness_tags` 的 count(`≥3` severe、`≥2` warn)自动可视化。整层走**单向数据流**(interview 写 → coach 只读 + 写 `coach_plans`,不回写),架构上避免多 Agent 循环依赖。

### STAR 故事 2:分层记忆 + 上下文预算控制("不是全塞进 context")

- **S**:全量历史喂 evaluator,token 指数涨;简历原文几千字撑爆 context。
- **T**:保证 agent 感知足够上下文,把 token 成本压到线性。
- **A**(短期/长期分层 + 摘要压缩):
  - **两层分离**:`InterviewState.candidate_profile` 是 session 内 working memory;`CandidateMemory` 是跨 session 长期记忆。Coach 看长期记忆,**有意降低单次异常的权重,避免过拟合**。
  - **摘要压缩**:简历上传时**一次性** LLM 生成 200 字摘要存 `User.resume_summary`,后续复用;注入用摘要非原文。生成失败不阻塞(fail-soft,退化到 `None`)。
  - **窗口裁剪**:evaluator 跨轮只读**最近 8 条消息**;`latent_signals` 设上限。
  - **缓存**:Coach 开场词 Redis 缓存 24h TTL,LLM 失败有兜底文案。
- **R**:规模化时成本**线性而非指数**;SSE 把 level/signals/missing 透传前端渲染 chip,**用可解释性换信任**。

---

## 三、面试官可能的追问 + 应答要点

**Q1 记忆无限膨胀怎么控制?**

> 三层:① `cumulative_signals` FIFO 硬上限 50;② `weakness_tags` 用聚合计数非逐条存储;③ 简历 200 字摘要 + evaluator 只读最近 8 条。**坦诚短板**:目前 FIFO 而非重要性加权,长期用户早期重要信号会被挤掉;改进方向是按 `count`/`last_seen_at` 加权淘汰,或上 recency×importance 打分。

**Q2 怎么避免错误/过期记忆污染?**

> ① 抽取层 LLM 输出**结构化字段而非自由文本**,Pydantic 默认值兜底,失败不写脏数据;② 分层让 Coach 看聚合画像,单场异常被平滑;③ `latest_level` 覆盖更新。**已知缺口**:无"弱点已改善"自动失效——改掉的弱点仍按历史 count 靠前;需引入近窗口衰减或 evaluator 显式标 resolved。

**Q3 没上向量库,检索准确率/语义重复怎么办?**

> 诚实说**会**——`QPS 量化` 和 `性能量化` 不会自动合并。缓解:① 抽取约束 LLM 输出**受控词表式高级标签**;② 注入是 LLM 读 JSON,模型能理解近义。**为什么合理**:我的记忆是结构化画像,按 user_id 精确查询 O(1),没有"百万条里找 Top-K"场景,向量检索边际收益低。**何时该上**:做跨用户相似候选人推荐、或信号量级需要语义聚类时(Phase 6+)。

**Q4 为什么不直接全塞 context?**

> 三个硬约束:**成本**(token 随历史线性涨)、**延迟**、**lost-in-the-middle**(context 越长中间信息越稀释)。而且原文大量是噪声——我要的是"三场都缺量化"这个**提炼结论**而非逐字记录。所以做"抽取→聚合→按需注入",本质是**用写入时计算换检索时精准和省钱**。

**Q5 多用户隔离和隐私?**

> `candidate_memory` 以 `user_id` 为主键,**所有读写带 user_id 维度**,天然隔离。Coach API 校验 `session_id` 属当前用户且 completed 才放行。`last_session_id` 用 `ON DELETE SET NULL`。存的是提炼后画像而非简历敏感原文。**可补强**:无主动清空/过期删除入口,做 GDPR 合规需补级联清理。

**Q6 两层记忆会不会不同步?**

> 会,有意取舍。session 存实时细节、`CandidateMemory` 是周期聚合版,Coach 看聚合版——不被单场带偏,代价是最新反馈权重低。用**单向数据流 + persist 节点幂等**(按 session_id 查重)保证不重复写脏。

---

## 四、电梯版口头回答(30-60 秒)

> "AI agent 记忆我一般分两层讲:短期是 context 里的 working memory,跟着会话走;长期是跨会话持久化的画像,落外部存储。长期又能拆成情景、语义、程序三类。一套完整记忆系统要走五步——抽取、存储、检索、反思、遗忘。
>
> 这套我在自己的 AI 面试教练项目里完整实现过。每轮面试后 evaluator 用 LLM 结构化抽取候选人的能力信号和缺失维度,upsert 到 PostgreSQL 的 `candidate_memory` 表——信号去重保序、FIFO 控制在 50 条防膨胀、弱点标签按次数计数累积,这样'三场都缺量化'这种跨会话模式就能被自动捕捉。Coach Agent 是个 LangGraph 子图,加载长期记忆加最近报告加简历摘要,注入 prompt 生成个性化复盘。
>
> 关键取舍是这期我用 JSONB 而非向量库,因为画像是结构化数据、按 user_id 精确查询就够,向量检索留给后面做跨用户推荐。整套记忆走单向数据流,架构上避免了多 Agent 循环依赖。"

---

## 五、为什么这样答能赢

讲的全是项目里真做了的(`candidate_memory` 表、`upsert_candidate_memory`、evaluator 抽取、Coach LangGraph 子图、JSONB/FIFO 50/计数累积、单向数据流、Redis 缓存、简历摘要),没把没做的吹成做了——向量库、重要性加权淘汰、弱点自动失效、跨用户推荐都明确标成"改进方向/Phase 6+"。

**主动暴露边界 + 给演进规划,恰恰是面试里最稀缺的加分项**:它证明你不是堆功能,而是懂取舍、知道下一步往哪走。
