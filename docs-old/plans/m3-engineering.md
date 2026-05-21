# M3 里程碑计划：工程化 AI 产品

> 覆盖 Phase：**P5 + P6 + P7**
> 简历卖点：**"LLM-as-Judge Eval + 高级多 Agent 协作 + Meta-cognition 知识图谱"**
> 状态：v0.1（初版）
> 📍 全景位置：见 [`../product-vision.md` §6.5 M↔Phase↔功能模块总览图](../product-vision.md)

---

## 1. 里程碑目标

把 M2 的"能用的多 Agent 记忆系统"升级为「**工程化、可量化、有 Meta-cognition**」的成熟 AI 产品。完成后用户能看到自己**真实可量化的成长曲线**，Agent 团队**真协作**（不是流水线），系统具备**元认知能力**（看多场轨迹反思）。

## 2. 范围

| 包含 | 不包含（属于 M4） |
|---|---|
| ✅ LLM-as-Judge 多维度 Eval 体系 | ❌ MCP Server 化 |
| ✅ 量化进步曲线 + Benchmark | ❌ Voice 模式 |
| ✅ 共享 scratchpad + 动态路由 | ❌ 多用户系统 |
| ✅ BOSS 终面 / 记忆管家 / 出题升级 Agent | ❌ 商业化 |
| ✅ HITL 中途打断 | |
| ✅ A2A 通信协议 | |
| ✅ L5 反思日志 + Meta-reflection | |
| ✅ Neo4j 弱点知识图谱 + 可视化 | |
| ✅ 记忆衰减 / 冲突解决 / 压缩归档 | |
| ✅ LangSmith / Langfuse 追踪 | |

---

## 3. P5 — Eval 评测体系

### 3.1 LLM-as-Judge 多维度评分

参考 Anthropic Eval Cookbook，把 M2 的"单 LLM 给 4 维分"升级为「多 Judge + 共识 / 投票」：
- 3 个 Judge LLM（gpt-4o / claude-opus / claude-sonnet）独立打分
- 取中位数 + 离散度（离散度高的样本进 review 队列）
- Rubric 文档化（每维度详细标准 + 锚定例子）

### 3.2 Rubric 设计

每个维度的 1-10 分对应明确锚定（anchor examples）：
- `STAR_completeness` 1 分：「只提到任务结果，无情境/任务/行动」
- `STAR_completeness` 10 分：「四要素齐全 + 量化结果 + 反思」
- 锚定例子库需要 ~20 个标注样本

### 3.3 量化进步曲线

- 每周计算一次 user_profile 的能力均值，存 `user_metrics_weekly` 表
- 前端用 recharts 画雷达图 / 折线图
- 关键指标：
  - 各维度均分趋势
  - 弱点标签 `improved` 比例
  - 每周面试次数 / 完成率

### 3.4 Benchmark 测试集

- 构造 50 道"标准题 + 标准答案 + 标准评分"作为黄金集
- 每次 Judge 模型升级时跑一次，检查偏差
- 公开版本：去敏后放 GitHub（M4 实施）

### 3.5 个人成长仪表盘

```
┌─────────────────────────────────────────────────────┐
│  Multi Agent Coach · 我的成长                          │
├─────────────────────────────────────────────────────┤
│  [雷达图]              [折线图：4 周进步曲线]       │
│   ・clarity 7.8        ・clarity      ▁▃▅▆▇       │
│   ・depth 6.2          ・depth        ▁▂▃▄▅       │
│   ・specificity 5.5    ・specificity  ▁▁▂▃▄       │
│   ・STAR 6.0           ・STAR         ▁▂▃▄▅       │
├─────────────────────────────────────────────────────┤
│  弱点追踪（active / improved）                      │
│  ・star-缺量化   ████████░░ 出现 8 次（active）     │
│  ・系统设计-高并发 ██░░░░░░░░ 已改进（improved）    │
├─────────────────────────────────────────────────────┤
│  本周建议                                            │
│  • 多做 2 场技术面，目标提升 specificity 1 分        │
└─────────────────────────────────────────────────────┘
```

### 3.6 P5 验收标准

- [ ] 3 Judge 模型并行评分链路跑通
- [ ] Benchmark 测试集 50 题入库，跑一次给出基线
- [ ] 仪表盘前端展示雷达图 + 4 周进步曲线
- [ ] Rubric 锚定库 ≥ 20 例

---

## 4. P6 — 高级多 Agent 协作

### 4.1 共享 scratchpad

- 每场面试维护一个 `scratchpad` 字段（JSON），Agent 间可读写
- 例：HR Agent 写"用户提到了 LangGraph 项目"，技术 Agent 读到后主动深挖
- LangGraph 用 reducer 控制写入冲突

### 4.2 动态路由

- 在 HR → 技术 / 技术 → Coach 之间插入 router 节点
- 路由规则：
  - 用户在某维度连续 2 题低于 5 分 → 路由到"反向出题"分支
  - 用户主动说"换一道" → HITL 打断
  - 时间超过阈值 → 直接进 Coach

### 4.3 BOSS 终面 Agent

- 角色：高管面 / 反问环节 / 文化匹配
- 出题方向：「为什么离职」「未来 3 年规划」「反问环节」
- 注入：L2 画像 + L1 历史摘要

### 4.4 出题升级 Agent

- 在出题前介入：查 L4 弱点 → 加权出弱点题
- 加权策略：弱点 severity * occurrence_count → softmax → 抽样

### 4.5 记忆管家 Agent

- 后台周期性任务（Celery beat 每天/每周）
- 职责：
  - 清理过期 weakness_tags（连续 N 场未出现 → improved）
  - 合并 L3 同项目重复故事
  - 压缩 L1 老 session.summary
  - 检测 L2 画像异常漂移

### 4.6 Human-in-the-Loop（HITL）

- 用户在面试中可点"换一题" / "我想跳过这阶段" / "结束本场"
- LangGraph 的 `interrupt()` 机制
- 前端"暂停 / 继续 / 跳过"按钮

### 4.7 A2A 通信协议（Agent-to-Agent）

- 定义 Agent 间消息格式：`{from, to, intent, payload}`
- intent 类型：`hint` / `request_help` / `notify` / `escalate`
- 例：技术 Agent 发现用户答题异常 → 发 `escalate` 给 Coach Agent 让它温和介入

### 4.8 P6 验收标准

- [ ] 5 Agent 协作（HR / 技术 / BOSS / Coach / 出题）顺利运行
- [ ] 动态路由能根据用户表现切换分支
- [ ] HITL 用户能中途打断
- [ ] scratchpad 在 Agent 间可见
- [ ] A2A 消息日志能查询

---

## 5. P7 — Meta-cognition + 高级记忆

### 5.1 L5 反思日志

```sql
CREATE TABLE reflection_logs (
  id UUID PRIMARY KEY,
  user_id INT,
  session_id UUID,
  message_id UUID,
  reflexion_payload JSONB,         -- M2 的 Reflexion 结构化输出
  meta_reflection_id UUID,         -- 关联到 Meta-reflection
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE meta_reflections (
  id UUID PRIMARY KEY,
  user_id INT,
  window_start TIMESTAMP,          -- 反思的窗口
  window_end TIMESTAMP,
  source_log_ids JSONB,            -- 哪些 reflection_logs 被纳入分析
  patterns JSONB,                  -- 识别出的反复模式
  meta_suggestion TEXT,            -- 给用户的元建议
  created_at TIMESTAMP DEFAULT NOW()
);
```

### 5.2 Meta-reflection

- 每周触发一次（Celery beat）
- 拉取过去 N 场面试的 reflection_logs
- 用 LLM 找模式：「这个用户在 X 类型题上反复出现 Y 类错误」
- 输出元建议存 `meta_reflections`
- 前端在仪表盘顶部展示「本周元洞察」

### 5.3 L4 升级为 Neo4j 弱点知识图谱

为什么要图谱：
- 弱点之间有关联（"系统设计-高并发"通常和"性能调优"共现）
- 用图谱能可视化整张"知识盲区地图"
- Cypher 查询「我哪些盲区会同时影响下一场面试」

Schema：
- 节点：`Weakness {tag, category, severity}`
- 边：`CO_OCCUR {weight}` / `IMPROVED_BY {strategy}` / `RELATED_TO`

### 5.4 知识图谱可视化

- 前端用 `react-flow` / `cytoscape.js`
- 节点大小 = severity * occurrence_count
- 边粗细 = co_occurrence weight
- 可点节点查看相关 message_ids

### 5.5 记忆遗忘衰减

- 每个记忆条目维护 `decay_score`
- 公式：`decay_score = exp(-Δt / τ)`, τ 按类型不同（L3 故事 τ=180d，L4 弱点 τ=30d）
- decay_score < 阈值 → 标记 archived（不删除）

### 5.6 冲突解决

升级 M2 的"最后写入"策略：
- 检测 L3 同项目不同版本 → 用 LLM judge 选最优
- L2 画像漂移过大 → 触发 alert + 人工 review
- 冲突日志独立表 `memory_conflicts`，可视化展示

### 5.7 压缩归档

- L1 老 summary 用 LLM 进一步压缩（200 字 → 50 字精华）
- L3 archived 故事压缩到 `archived_stars` 表
- 减少检索时的搜索空间

### 5.8 P7 验收标准

- [ ] Neo4j 部署 + 弱点图谱可查 / 可视化
- [ ] Meta-reflection 每周自动跑 + 出元建议
- [ ] 记忆衰减脚本跑通 + 归档生效
- [ ] LangSmith 全链路追踪可查每一次 Agent 调用

---

## 6. 工期粗估

| Phase | 名义工时 |
|---|---|
| P5 | 30-40h |
| P6 | 40-50h |
| P7 | 40-50h |
| **小计 M3** | **110-140h** |

## 7. 简历兑现点（M3 完成后能写什么）

简历项目栏（150 字）：
> Multi Agent Coach - 工程化的 AI Agent 面试陪练系统。在 M2 多 Agent + 分级记忆基础上：① 实现 LLM-as-Judge 多裁判 Eval 体系 + Benchmark 50 题黄金集 + 量化进步曲线；② 升级到 5 Agent 协作（共享 scratchpad + 动态路由 + HITL + A2A 协议）；③ 引入 Meta-reflection 元认知 + Neo4j 弱点知识图谱 + 记忆衰减/冲突/归档完整生命周期。集成 LangSmith 全链路追踪。

招聘官能 get 的强信号：
- ✅ Eval 工程能力（招聘官最关心的"AI 落地能力"）
- ✅ 协作架构（不是 toy 多 Agent，是真协作）
- ✅ 元认知 / 知识图谱（前沿 + 工程化）
- ✅ 可观测性（LangSmith）

## 8. 关键风险

| 风险 | 应对 |
|---|---|
| Neo4j 部署 / 运维复杂 | 用 Neo4j AuraDB 托管 |
| Meta-reflection LLM 成本高 | 用 gpt-4o-mini + cache |
| 5 Agent 协作 token 爆炸 | 上下文裁剪 + scratchpad 摘要 |
| Judge 模型偏见 | 多 Judge 共识 + Benchmark 监控 |
| LangSmith 数据隐私 | self-host Langfuse 替代 |
