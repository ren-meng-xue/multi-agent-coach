# 阶段 3：JD 分析 + 出题 Agent · 设计文档

**日期**：2026-05-25
**状态**：待实施
**范围**：MASTER Orchestrator · 记忆检索 · JD分析 · 出题 · 准备卡 UI

---

## 背景

阶段 1+2 实现了单 Interviewer Agent 的完整面试对话与 Coach 集成。
阶段 3 在面试开始前加入「准备阶段」：MASTER Orchestrator 根据上下文动态调度子 Agent，生成个性化题目，结果以可折叠准备卡的形式嵌入 `/interview` 页面。

---

## 产品目标

| 目标 | 衡量标准 |
|------|----------|
| 面试题目与 JD 强相关 | 准备题目中 ≥3 道可在 JD 中找到对应技能点 |
| 薄弱点优先考察 | 出题 Agent 将历史弱项题目排在前2题 |
| 用户可感知 Agent 协作过程 | 准备卡展示动态 Trace，用户可展开查看 |
| 无 JD 时也能正常使用 | MASTER 自动降级，仅跑记忆检索 + 出题 |

---

## UX 流程

```
Coach 页 / /interview 页
  └─ 用户可选择：粘贴 JD 文本 / 上传文件(PDF·Word·图片) / 贴 URL
        ↓ (也可不提供，直接进入)
  /interview 页加载
  ├─ 顶部：准备卡（自动开始运行）
  │     运行中：显示动态 Agent Trace（节点随调度逐个出现）
  │     完成后折叠：● 准备完成  就绪 ∨
  │                摘要："根据「分布式系统」为你定制了 5 道题..."
  │                [▷ 开始第1题]  [≡ 先看题目列表]
  │     展开：完整 Agent Trace Timeline
  └─ 下方：聊天区（准备完成前输入框锁定）
```

### 准备卡三种状态

```
running  → "准备中..."  + Trace 节点动态出现 (pending→running→done)
done     → 折叠态：摘要 + 两个按钮
expanded → 展开态：完整 Trace（点 就绪∨/∧ 切换）
```

---

## MASTER 的三个独立输入

```
① user_direction  ← 用户当前会话主动输入："我想练 AI Agent 开发工程师方向"
                    （来自 Coach 对话 或 /interview 准备区直接填写）
                    ★ 这是当前意图，不是从记忆里查出来的

② jd_raw          ← 可选，用户上传的 JD 内容（文本/文件/URL/图片提取后的纯文本）
                    如有则 JD分析 Agent 从中提炼考点，使出题更精准

③ user_id         ← 用于查询两类记忆数据（见记忆检索 Agent 章节）
```

## MASTER 动态调度逻辑

MASTER 是一次轻量 LLM 调用，综合三个输入后决定调用链，并识别「方向」（如「分布式系统」）：

| 条件 | 调度链 |
|------|--------|
| 有 user_direction + 有JD + 有历史 | 记忆检索 → JD分析 → 出题 |
| 有 user_direction + 有JD + 无历史 | JD分析 → 出题 |
| 有 user_direction + 无JD + 有历史 | 记忆检索 → 出题 |
| 有 user_direction + 无JD + 无历史 | 出题 |
| 无 user_direction + 有JD | JD分析 → 出题（从JD提取方向） |

**MASTER 的第一个 SSE 事件**输出 `direction` + `chain` 字段，前端收到后才知道后续节点。

---

## JD 内容提取

三种来源统一转为纯文本字符串，交给 JD分析 Agent：

| 来源 | 提取方式 |
|------|----------|
| 文本粘贴 | 直接使用 |
| PDF / Word 文件 | pypdf2（PDF）/ mammoth（DOCX）→ 纯文本 |
| URL | httpx + BeautifulSoup 抓正文；失败时返回 `need_manual_input` 错误，提示用户改为粘贴 |
| 图片截图 PNG/JPG | Claude Vision API 提取文字 |

提取层在 MASTER 运行前完成，MASTER 拿到的已经是纯文本（或 None）。

---

## 后端架构

### 新增目录

```
backend/app/agents/prepare/
  __init__.py
  state.py       # PrepareState
  nodes.py       # master_node, memory_search_node, jd_analysis_node, question_gen_node
  graph.py       # 顺序 StateGraph，MASTER 决定路由

backend/app/services/
  jd_extractor.py  # extract_jd_text(source) -> str | None
```

### PrepareState

```python
class PrepareState(TypedDict, total=False):
    session_id: str
    user_id: str
    user_direction: str         # ★ 用户当前意图："AI Agent 开发工程师"（当前输入，非记忆）
    target_role: str            # 用户档案里的目标岗位（可与 user_direction 相同）
    user_background: str
    jd_raw: str | None          # JD 原始文本（已提取）
    has_jd: bool
    has_history: bool
    chain: list[str]            # MASTER 决定的子 Agent 列表
    direction: str              # MASTER 识别的方向（如"分布式系统"）
    # 记忆检索结果（两个数据源）
    weak_areas: list[str]       # 来自历史面试表现（InterviewSession）
    star_stories: list[dict]    # 来自故事库（UserStory，已有 DB 模型）
    jd_context: JDContext | None
    prepared_questions: list[PreparedQuestion]
```

```python
class JDContext(TypedDict):
    company: str
    role: str
    key_skills: list[str]
    focus_areas: list[str]
    difficulty: str             # easy / medium / hard / faang

class PreparedQuestion(TypedDict):
    id: int
    question: str
    category: str               # technical / behavioral / system_design
    focus_area: str
    priority: int               # 1=最高，薄弱点相关题排前
```

### 新增 API 端点

```
POST /api/v1/prepare/start
Content-Type: multipart/form-data

Body:
  user_direction: str              # ★ 用户当前想练的方向（必填）
  target_role: str
  user_background: str (optional)
  jd_text: str (optional)          # 文本粘贴
  jd_file: File (optional)         # PDF/Word/图片上传
  jd_url: str (optional)           # URL

Response: text/event-stream
```

### 记忆检索 Agent 数据源

查询两个已有 DB 表：

| 数据源 | 表 | 提取内容 |
|--------|------|----------|
| 历史面试表现 | `interview_sessions` + `interview_messages` | 薄弱点、得分、高频错误 |
| 故事库 | `user_stories`（UserStory 模型已存在）| title, role, tags, content_json |

输出给出题 Agent 的 `star_stories` 使出题具体化：
- 不是「描述一个分布式系统项目」
- 而是「你在 LangGraph 多 Agent 工单系统里，如何解决一致性问题？」

**长短期记忆（爱好/偏好/练习历史）= 未来规划，Phase 3 不实现，架构预留。**

## 出题 Agent 工具调用（架构预留）

截图中「真题库 获取近期真题 · 超时 重试 成功」是一次工具调用。
Phase 3 出题 Agent 预留 tool calling 结构，工具先 mock，后续接 MCP 不改框架：

```python
# question_gen_node 内部
tools = [
    search_question_bank,    # Phase 3: mock 返回空列表
                             # Phase 4+: 接真实 MCP server
]
# 工具调用需有 retry 装饰器 + timeout（对应截图的"超时 重试 成功"行为）
```

### SSE 事件流设计

**所有 bullet 文案均为 LLM 动态生成，通过 `node_token` 流式传输，前端逐字渲染（类似 Claude thinking 展开效果）。没有任何硬编码字符串。**

```
# MASTER 开始（立即触发，无需等待用户输入）
data: {"event": "node_start", "node": "master"}

# MASTER 流式输出 bullets（动态，内容由 LLM 实际判断决定）
data: {"event": "node_token", "node": "master", "text": "检查用户档案："}
data: {"event": "node_token", "node": "master", "text": "找到目标岗位 AI Agent 工程师"}
  # 或者输出："未设置，需要用户确认方向"

data: {"event": "node_token", "node": "master", "text": "\n检查历史记录："}
data: {"event": "node_token", "node": "master", "text": "发现 3 场面试，一致性哈希是高频弱点"}
  # 或者输出："新用户，暂无历史数据"

# MASTER 完成，输出 chain（前端据此知道后续节点）
# 若 MASTER 发现需要询问方向，额外发 need_direction 事件
data: {"event": "node_done", "node": "master", "elapsed_ms": 8,
       "chain": ["memory_search", "jd_analysis", "question_gen"],
       "need_direction": false}
  # 若需询问：need_direction: true → 前端在聊天区插入 AI 提问，等用户回答后发 resume 事件

# 子 Agent（只有 MASTER chain 里包含的才出现）
data: {"event": "node_start",  "node": "memory_search"}
data: {"event": "node_token",  "node": "memory_search", "text": "薄弱点：一致性哈希（上次62分）"}
data: {"event": "node_token",  "node": "memory_search", "text": "\n加入重点考察列表"}
data: {"event": "node_done",   "node": "memory_search", "elapsed_ms": 62}

data: {"event": "node_start",  "node": "jd_analysis"}
data: {"event": "node_token",  "node": "jd_analysis", "text": "高频考点：CAP、一致性、分布式锁"}
data: {"event": "node_token",  "node": "jd_analysis", "text": "\n难度：hard · 偏FAANG"}
data: {"event": "node_done",   "node": "jd_analysis", "elapsed_ms": 280}

data: {"event": "node_start",  "node": "question_gen"}
data: {"event": "node_token",  "node": "question_gen", "text": "第1题生成中..."}
data: {"event": "node_token",  "node": "question_gen", "text": "\n第2题生成中..."}
data: {"event": "node_done",   "node": "question_gen", "elapsed_ms": 1200}

# 全部完成（summary 也是 LLM 生成，非固定文案）
data: {"event": "done", "jd_context": {...}, "prepared_questions": [...],
       "summary": "..."}  # LLM 生成的一句话摘要
```

### MASTER 无方向时的交互流程

```
MASTER 流式输出 → 发现无 target_role → node_done 含 need_direction: true
    ↓
前端在聊天区插入 AI 消息（也是 LLM 生成，非固定文案）
    ↓
用户在底部输入框回答
    ↓
前端 POST /api/v1/prepare/resume { direction: "AI Agent 工程师" }
    ↓
MASTER 继续，输出 chain，后续子 Agent 正常运行
```

### 现有 InterviewState 扩展

```python
# 在 state.py 追加
jd_context: dict[str, Any] | None
prepared_questions: list[dict[str, Any]]
```

### 现有 ask_question_node 改动

有 `prepared_questions` 时：按 `priority` 顺序取题，不再 LLM 随机出题。
列表取完后退回现有随机出题逻辑。

### 现有面试流程改动

有 `prepared_questions` 时，跳过 `opening` / `briefing` 阶段，直接到 `ask_question`。
路由逻辑在 `route_after_load` 中判断 `prepared_questions` 是否非空。

---

## 前端架构

### 新增组件

```
frontend/app/interview/_components/
  preparation-card.tsx      # 准备卡容器（三态：running/done/expanded）
  agent-trace.tsx           # Agent Trace Timeline（动态节点列表）
  trace-node.tsx            # 单个节点（pending/running/done 三态圆圈 + bullets + 耗时）
  question-list-modal.tsx   # "先看题目列表" Modal
```

### 准备卡组件状态

```ts
type PrepCardState = "idle" | "running" | "done"
type TraceNode = {
  id: string
  label: string        // "MASTER" | "记忆检索" | "JD分析" | "出题"
  title: string        // "识别方向，启动准备"
  status: "pending" | "running" | "done"
  bullets: string[]
  elapsed_ms?: number
}
```

### SessionStorage 扩展

```ts
// 现有
{ target_role: string, user_background: string }

// 阶段3 新增字段（可选）
{
  ...
  jd_source?: { type: "text"|"file"|"url"|"image", content: string }
  jd_context?: JDContext
  prepared_questions?: PreparedQuestion[]
  prepare_summary?: string
}
```

### 页面布局改动

```
/interview 页
  ├─ PreparationCard（顶部，准备阶段可见，准备完成后可折叠）
  └─ 聊天区（现有，准备完成前 input 禁用）
```

### Coach 页改动

现有 CTA 旁新增「我有 JD」入口：
- 点击展开 JD 输入区（文本框 + 文件上传按钮）
- 提交后写入 sessionStorage `jd_source`，再跳 /interview
- 不提供 JD 也可以直接进（现有流程不变）

### /interview 页加载逻辑

```
1. 读 sessionStorage["interview_context"]
2. 若有 jd_source → 调用 POST /api/v1/prepare/start → 渲染 PreparationCard + 流式 Trace
3. 若无 jd_source → 直接调用 POST /api/v1/prepare/start（无 JD，MASTER 决定最短链）
   或跳过准备阶段，走现有 opening 流程（待定：是否强制走准备阶段）
```

### 两个按钮行为

**「▷ 开始第1题」**
- 触发 `/api/v1/interview/stream`，携带 `{ prepared_questions, jd_context }` 作为 context
- 后端直接进入 `ask_question` 阶段，输出第1道题
- 聊天区解锁，显示第1道题

**「≡ 先看题目列表」**
- 打开 QuestionListModal
- 展示5道题的序号、题目摘要、category tag
- Modal 关闭后回到准备卡

---

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| URL 爬取失败 | SSE 返回 `need_manual_input` 事件，前端提示「此链接需要登录，请直接粘贴 JD 文本」 |
| 文件解析失败 | 返回具体错误，前端提示重新上传或改为粘贴 |
| Vision 提取失败 | 降级提示手动粘贴 |
| 准备阶段超时（>30s）| SSE 发 `timeout` 事件，提示用户选择「跳过准备，直接开始」 |
| 出题 Agent 失败 | 降级为现有随机出题，不阻断面试入口 |

---

## 测试要求

### 后端

| 测试 | 类型 |
|------|------|
| `extract_jd_text` 四种来源各一条成功路径 | 单元测试 |
| URL 爬取失败返回 `NeedManualInput` | 单元测试 |
| `master_node` 四种 chain 决策覆盖 | 单元测试 |
| `jd_analysis_node` 输出结构校验 | 单元测试 |
| `question_gen_node` 输出 ≥1 道题 | 单元测试 |
| `question_gen_node` 有弱点时弱点题排前2 | 单元测试 |
| `ask_question_node` 有 prepared_questions 时按序取题 | 单元测试 |
| `route_after_load` 有 prepared_questions 时跳过 opening | 单元测试 |
| `/api/v1/prepare/start` 完整 SSE 流 | 集成测试 |

### 前端

| 测试 | 类型 |
|------|------|
| `trace-node` 三态渲染 | 单元测试 |
| `preparation-card` 收到 done 事件后显示按钮 | 单元测试 |
| `question-list-modal` 渲染题目列表 | 单元测试 |
| 「开始第1题」触发 stream 调用 | 集成测试 |

---

## 阶段4 预留

阶段4 加入评估 Agent（并行打分）。实现时：
- `PrepareState.chain` 追加 `"evaluation"` 节点（面试结束时）
- Trace Timeline 底部分割线下方已预留「面试官 待命」「评估 后台静默打分」两个节点的展示位
- 不需要改 MASTER 逻辑，评估 Agent 由面试结束事件触发

---

## 风险

| 风险 | 缓解 |
|------|------|
| JD分析/出题 LLM 调用慢（>10s）| streaming token 展示出题进度，用户感知有响应 |
| Vision 提取图片准确率 | 提取结果后在前端展示预览，用户可确认或修改 |
| prepared_questions 与现有 InterviewState 兼容 | 字段设为 optional，有值才改变路由，无值走原有流程 |
