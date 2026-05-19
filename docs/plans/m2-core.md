# M2 里程碑计划：有记忆的多 Agent + 自反思（核心叙事）

> 覆盖 Phase：**P2 + P3 + P4**
> 简历卖点：**"MemGPT 分级记忆 + Reflexion 多 Agent 系统"**
> 状态：v0.1（初版）
> 📍 全景位置：见 [`../product-vision.md` §6.5 M↔Phase↔功能模块总览图](../product-vision.md)
> 🌟 **整个项目最重要的里程碑，简历兑现的关键节点**

---

## 1. 里程碑目标

把 M1 的"单 Agent 单轮问答"升级为「**多 Agent 顺序编排 + 分级长期记忆 + 单轮自反思**」的完整闭环。完成后用户能跨会话感受到"AI 越用越懂我"。

## 2. 范围

| 包含 | 不包含（属于 M3+） |
|---|---|
| ✅ HR + 技术 + Coach 3 Agent | ❌ BOSS 终面 / 记忆管家 / 出题升级 Agent（→ M3） |
| ✅ LangGraph StateGraph 编排（顺序流转） | ❌ 共享 scratchpad / 动态路由 / A2A（→ M3） |
| ✅ 分级记忆 L0 + L1 + L2 + L3 + L4 | ❌ L5 反思日志 / Meta-reflection（→ M3） |
| ✅ Reflexion 单轮（评分 + 反思 + 回写） | ❌ 闭环出题升级 / 反思质量评测（→ M3） |
| ✅ 复盘报告页（首版） | ❌ 量化进步曲线 / LLM-as-Judge 体系（→ M3） |
| ✅ L4 用 `weakness_tags` 简化表 | ❌ Neo4j 知识图谱（→ M3） |

---

## 3. P2 — 多 Agent 顺序编排

### 3.1 LangGraph StateGraph 设计

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Literal

class InterviewState(TypedDict):
    session_id: str
    user_id: int
    phase: Literal["hr", "tech", "coach", "done"]
    current_question: str
    user_answer: str
    retrieved_memory: dict       # 从 L2/L3/L4 检索到的记忆
    retrieved_rag: list          # RAG 检索结果
    reflexion_result: dict       # P4 才填
    messages: list               # 完整消息历史

graph = StateGraph(InterviewState)
graph.add_node("hr_agent", hr_agent_node)
graph.add_node("tech_agent", tech_agent_node)
graph.add_node("coach_agent", coach_agent_node)
graph.add_node("reflexion", reflexion_node)   # P4
graph.add_node("memory_writer", memory_writer_node)

graph.add_edge(START, "hr_agent")
graph.add_edge("hr_agent", "tech_agent")
graph.add_edge("tech_agent", "reflexion")
graph.add_edge("reflexion", "memory_writer")
graph.add_edge("memory_writer", "coach_agent")
graph.add_edge("coach_agent", END)
```

### 3.2 InterviewState 数据结构

- `session_id`: 当前面试场次
- `phase`: 当前阶段
- `messages`: 标准 LangChain Message 列表（HumanMessage / AIMessage）
- `retrieved_memory`: 在每个 Agent 节点开场注入，包含：
  - `profile`: L2 长期画像快照
  - `relevant_stars`: 与当前主题相关的 STAR 故事
  - `relevant_weaknesses`: 相关弱点标签
- `reflexion_result`: P4 完成后填入

### 3.3 3 Agent 节点设计

#### HR Agent 节点
- 角色：行为面 / 自我介绍 / 项目背景 / STAR 引导
- 调用 LLM 前注入：L2 画像 + 历史 STAR 故事
- 出 3 题左右后切换到 tech Agent

#### 技术 Agent 节点
- 角色：技术深挖（围绕 LangGraph / RAG / Eval / 多 Agent 等）
- 注入：L2 画像（特别是 `tech_strengths` / `weaknesses`）+ RAG 题库检索
- 出 3-5 题，每题 Reflexion 一次

#### Coach 复盘 Agent 节点
- 角色：本场综合复盘 + 鼓励 + 下次建议
- 注入：本场所有 Reflexion 结果 + 历史画像
- 输出复盘报告（JSON + 自然语言）

### 3.4 Conditional Edges（M2 不做，留给 M3）

M2 阶段固定顺序：HR → 技术 → Coach
M3 引入动态路由：根据用户表现切换或跳过阶段

### 3.5 短期记忆 L0

- 存在 `InterviewState.messages` 中
- LangGraph state 自动维护
- 不持久化（仅本场会话）

### 3.6 面试房间前端完整版

页面结构：
```
┌─────────────────────────────────────────────┐
│ [当前阶段：HR 面] [进度：3/10]              │ <- 头部
├─────────────────────────────────────────────┤
│                                             │
│   [Agent: HR 面试官]                        │
│   "你好，介绍一下你最近做过的 AI 项目..."   │
│                                             │
│   [User]                                    │
│   "我做过一个 LangGraph 多步调研 Agent..."  │
│                                             │
│   [Agent: HR 面试官]                        │
│   "听起来很有意思，里面 ...（流式）"        │ <- 流式渲染
│                                             │
├─────────────────────────────────────────────┤
│ [输入你的回答...]                  [发送]   │
└─────────────────────────────────────────────┘
                                      [💡 复盘抽屉] <- 右下浮动按钮
```

技术选型：
- shadcn `<Sheet>` 抽屉显示复盘
- 流式渲染：受控 `<textarea>` + token 追加
- Agent 角色切换：顶部色块切换 + 头像

### 3.7 P2 验收标准

- [ ] LangGraph 编排 3 Agent 顺序流转无错
- [ ] 浏览器能完整走完一次面试（HR 3 题 → 技术 3-5 题 → Coach 复盘）
- [ ] 每个 Agent 节点的 system prompt 注入正常
- [ ] SSE 流式不中断（包括 Agent 切换时）

---

## 4. P3 — 分级长期记忆系统

### 4.1 记忆层级总览（M2 范围）

| 层 | 状态 | 存储 |
|---|---|---|
| L0 短期 | ✅ M2 实现 | LangGraph state |
| L1 工作记忆 | ✅ M2 实现 | PG `interview_session.summary` |
| L2 长期画像 | ✅ M2 实现 | PG `user_profile`（结构化 + 向量） |
| L3 STAR 故事库 | ✅ M2 实现 | PG `star_stories` + pgvector |
| L4 弱点标签 | ✅ M2 简化版 | PG `weakness_tags` |
| L5 反思日志 | ⏸️ M3 实现 | PG `reflection_logs` |

### 4.2 数据模型

```sql
-- L1 + L2 base
CREATE TABLE user_profile (
  user_id INT PRIMARY KEY,
  goals TEXT,                       -- 求职目标（如：AI Agent 工程师 / 大厂）
  experience_summary TEXT,          -- 工作年限/方向摘要
  tech_strengths JSONB,             -- {"LangGraph": 0.8, "RAG": 0.7, ...}
  tech_weaknesses JSONB,            -- {"系统设计": 0.3, "高并发": 0.4}
  soft_strengths JSONB,             -- {"沟通表达": 0.7, ...}
  star_completeness_score FLOAT,    -- 平均 STAR 完整度
  total_interviews INT DEFAULT 0,
  profile_embedding vector(1536),   -- 用于跨用户匿名学习（M3+）
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE interview_session (
  id UUID PRIMARY KEY,
  user_id INT REFERENCES user_profile(user_id),
  started_at TIMESTAMP DEFAULT NOW(),
  ended_at TIMESTAMP,
  summary TEXT,                     -- L1 工作记忆：本场摘要
  scores JSONB,                     -- 本场各维度分数
  phase_completed JSONB             -- {"hr": true, "tech": true, "coach": true}
);

CREATE TABLE interview_message (
  id UUID PRIMARY KEY,
  session_id UUID REFERENCES interview_session(id),
  role VARCHAR(20),                 -- "user" / "hr_agent" / "tech_agent" / "coach"
  content TEXT,
  retrieved_context JSONB,          -- 当时注入的记忆/RAG 引用
  created_at TIMESTAMP DEFAULT NOW()
);

-- L3 STAR 故事库
CREATE TABLE star_stories (
  id UUID PRIMARY KEY,
  user_id INT REFERENCES user_profile(user_id),
  project_name VARCHAR(255),
  situation TEXT,
  task TEXT,
  action TEXT,
  result TEXT,
  quantified_results TEXT,          -- "提升 30% 召回率" 这类量化句
  tech_stack JSONB,                 -- ["LangGraph", "FastAPI"]
  quality_score FLOAT,              -- Reflexion 给出的故事质量
  source_message_id UUID REFERENCES interview_message(id),
  embedding vector(1536),
  created_at TIMESTAMP DEFAULT NOW()
);

-- L4 弱点标签（简化版）
CREATE TABLE weakness_tags (
  id UUID PRIMARY KEY,
  user_id INT REFERENCES user_profile(user_id),
  tag VARCHAR(100),                 -- "系统设计-高并发" / "STAR-缺量化"
  category VARCHAR(50),             -- "tech" / "soft" / "star"
  severity FLOAT,                   -- 0-1，严重度
  occurrence_count INT DEFAULT 1,
  last_occurred_session UUID,
  related_message_ids JSONB,        -- [uuid, uuid, ...]
  status VARCHAR(20) DEFAULT 'active',  -- "active" / "improved"
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

### 4.3 L1 工作记忆（本场摘要）

- 写时机：`coach_agent` 节点结束后，触发 Celery 任务异步生成
- 写内容：调 LLM 总结本场，输出 200-400 字摘要 + 关键 takeaways
- 读时机：下次面试开场前，注入到 HR Agent 的 prompt（"上次你提到了 X，今天我们继续聊"）

### 4.4 L2 长期画像

- 写时机：每次 Reflexion 完成后增量更新
- 写策略：
  - 结构化字段：用 LLM 抽取后 merge（最新覆盖，但保留历史快照）
  - `tech_strengths` / `weaknesses` 是 EMA 平均（α=0.3）
  - `profile_embedding`: 用 `goals + experience_summary + strengths` 拼接后 embedding
- 读时机：每个 Agent 节点开场注入

### 4.5 L3 STAR 故事库

- 写时机：用户回答含项目经历时，Coach Agent 调用 LLM 抽 STAR 结构
- 写策略：
  - 结构化 JSON 输出（pydantic + LLM Function Call）
  - pgvector 索引 `embedding`（基于 `project_name + situation + action`）
  - 同一项目去重：`project_name` 模糊匹配 + embedding 相似度 > 0.85 → 更新而非新建
- 读时机：HR/技术 Agent 出题前检索（"上次你讲过 X 项目，这次能深入聊吗"）

### 4.6 L4 弱点标签（简化版）

- 写时机：Reflexion 给某维度低分（< 5/10）时，自动打标
- 标签命名：分类层级 `category - subcategory`，如 `tech-系统设计-高并发`
- 读时机：出题时优先选弱点相关题（在 RAG 检索后做加权 boost）

### 4.7 读策略

每个 Agent 节点开场前的统一读取：
```python
def load_memory(user_id, current_topic):
    return {
        "profile": get_user_profile(user_id),       # L2
        "relevant_stars": search_stars(             # L3
            user_id, current_topic, top_k=3
        ),
        "active_weaknesses": get_active_weaknesses(  # L4
            user_id, severity_gt=0.5
        ),
        "last_session_summary": get_last_session_summary(user_id),  # L1
    }
```

### 4.8 写策略（Celery 异步）

- 用户答完一题 → 流式 SSE 推回前端（立即响应）
- **同时**派发 Celery 任务做：
  1. STAR 抽取（如适用）→ 写 L3
  2. 弱点标签判定 → 写 L4
  3. L2 画像增量更新
- 一场面试结束 → Celery 任务生成 L1 摘要

### 4.9 冲突处理 / 膨胀控制

| 问题 | 策略 |
|---|---|
| 同一项目多次描述不一致 | embedding 相似度判定为同项目 → 保留质量分高的版本 + 在 `interview_message.retrieved_context` 留冲突日志 |
| L3 故事库膨胀 | 同一 `project_name` 最多保留 top-3 quality_score 的版本 |
| L2 画像漂移 | EMA 平滑 + 保留 `profile_history` snapshot 表（M3） |
| 每个 Agent 读太多 token | 检索 top-K=3-5 + rerank（M3 加 rerank，M2 只 top-K） |

### 4.10 复盘报告页（首版）

```
┌──────────────────────────────────────────────┐
│ 本场复盘 - 2026-05-25 14:30                  │
├──────────────────────────────────────────────┤
│ 评分（来自 Reflexion）                       │
│   清晰度  ████████░░ 8/10                    │
│   深度    █████░░░░░ 5/10                    │
│   具体度  ██████░░░░ 6/10                    │
│   STAR    ████░░░░░░ 4/10  ← 弱点            │
├──────────────────────────────────────────────┤
│ 改进建议                                     │
│   • 讲项目时缺少量化结果                     │
│   • 系统设计回答深度不够，可以补 ...         │
├──────────────────────────────────────────────┤
│ 新增 STAR 故事 (2)                           │
│   • LangGraph 多步调研 Agent                 │
│   • RAG citation guard 系统                  │
├──────────────────────────────────────────────┤
│ 新弱点标签 (1)                               │
│   • star-缺量化（severity 0.6）              │
└──────────────────────────────────────────────┘
```

### 4.11 P3 验收标准

- [ ] 第 1 次面试 → 写入 L1/L2/L3/L4
- [ ] 第 2 次面试开场，HR Agent 能引用上次提过的项目
- [ ] 复盘报告页能展示评分/建议/新 STAR/新弱点
- [ ] DB 查询：能看到 user_profile 的 EMA 更新轨迹

---

## 5. P4 — Reflexion 自反思

### 5.1 Reflexion Agent 设计

参考 Reflexion (NeurIPS 2023) 的 actor-evaluator-self-reflection 三角，简化为「评分 + 反思 + 改进建议」二步。

```
[技术 Agent 出题] → [用户回答] → [Reflexion Agent 调用]
                                    │
                                    ├── 评分（rubric）
                                    ├── 找出 gaps
                                    ├── 写改进建议
                                    └── 给出 follow_up_question
```

### 5.2 评分维度（rubric）

| 维度 | 描述 | 范围 |
|---|---|---|
| clarity | 表达清晰度 | 1-10 |
| depth | 技术深度 | 1-10 |
| specificity | 具体度 / 量化程度 | 1-10 |
| STAR_completeness | STAR 结构完整度 | 1-10 |

### 5.3 结构化输出

用 LLM Function Call / JSON Schema 约束：
```json
{
  "scores": {"clarity": 7, "depth": 5, "specificity": 6, "STAR_completeness": 4},
  "strengths": ["回答逻辑清晰", "提到了 LangGraph 实现细节"],
  "gaps": ["缺少量化结果", "没有讲 trade-off"],
  "improvement_suggestion": "可以补充：当时考虑过的另一种方案是 X，为什么选了 Y",
  "follow_up_question": "你说用了 pgvector，为什么不用 Pinecone 这类专业向量库？",
  "weakness_tags_to_add": [
    {"tag": "star-缺量化", "category": "star", "severity": 0.6}
  ]
}
```

### 5.4 反向出题（简化版）

- Reflexion 输出的 `follow_up_question` 可直接由技术 Agent 作为下一题
- 同时把 `weakness_tags_to_add` 写入 L4
- **M3 才做真正闭环**（出题 Agent 主动查 L4 弱点出题）

### 5.5 记忆回写链路

```
Reflexion Agent 输出 JSON
    │
    ├── 写 L2 user_profile（tech_weaknesses EMA 更新）
    ├── 写 L4 weakness_tags（新增或 occurrence_count++）
    ├── 写 L3 star_stories（如果用户回答含项目经历）
    └── 写 interview_message.retrieved_context（debug 留痕）
```

### 5.6 P4 验收标准

- [ ] 一题答完后能看到完整 JSON 结构（评分 + 建议 + 追问 + 弱点标签）
- [ ] 弱点连续出现 2 次以上时，`occurrence_count` 累加
- [ ] 复盘报告页展示 Reflexion 结果
- [ ] Reflexion 给低分（< 5）的维度，能正确写入 L4

---

## 6. 工期粗估

| Phase | 名义工时 |
|---|---|
| P2 | 18-24h |
| P3 | 24-32h |
| P4 | 10-14h |
| **小计 M2** | **52-70h** |

## 7. 简历兑现点（M2 完成后能写什么）

简历项目栏（120 字）：
> 独立设计实现 Multi Agent Coach - AI Agent 工程师面试陪练系统。LangGraph 多 Agent 顺序编排（HR / 技术 / Coach），分级长期记忆系统（MemGPT 范式，L0-L4：短期 / 工作 / 画像 / STAR / 弱点）跨会话建模用户能力曲线与盲点；Reflexion 自反思链路（NeurIPS 2023）驱动评分、反向出题、记忆回写。技术栈：FastAPI + Celery + LangGraph + pgvector + Next.js。

招聘官能 get 的强信号：
- ✅ 多 Agent 编排（Agent 工程岗硬需求）
- ✅ MemGPT / Reflexion 论文落地（追前沿能力）
- ✅ 完整工程闭环（pgvector + 异步 + 流式 + 前后端）
- ✅ 数据驱动（跨会话记忆 + EMA + 量化评分）

## 8. 关键风险

| 风险 | 应对 |
|---|---|
| LangGraph state 序列化坑（vector / datetime） | 用 `MessagesState` 基类 + 自定义 reducer |
| L2 画像 EMA 漂移 | 保留 history snapshot；M3 加监控 |
| Reflexion JSON 结构不稳定 | Function Call 强约束 + Pydantic 校验 + 失败重试 |
| 一场面试 LLM 调用太多（成本） | 短期记忆控制 token；Coach 复盘用 gpt-4o-mini |
| 第 2 次面试 Agent 没读到上次记忆 | 集成测试覆盖"双场连环"用例 |
