# Coach–Interview UX 集成设计

**日期**：2026-05-25  
**范围**：前端衔接层 + 1 个只读 API  
**目标**：打通 `/coach` 与 `/interview` 的上下文传递，消除面试房间每次重复问开场白的问题，并用真实后端数据驱动 Coach 页面的新/老用户状态。

---

## 一、背景与问题

### 当前痛点

1. **重复问候**：用户在 `/coach` 已告知岗位方向，进入 `/interview` 后前端硬编码的 `OPENING_MESSAGE` 又问一遍"请告诉我你想练习的岗位"，体验断裂。
2. **Mock 数据**：`/coach` 的新/老用户 toggle 只是 Demo 状态，没有连接真实数据，无法做个性化欢迎。

### 依赖前提

本设计依赖 `2026-05-25-interviewer-agent-design.md` 中已实现的：
- `interview_sessions` 表（含 `target_role`, `target_company`, `user_background`, `status` 字段）
- `POST /api/v1/interview/reset` 接口（可扩展参数）
- LangGraph `opening` 节点负责后端的开场收集逻辑

---

## 二、新老用户定义

**老用户**：该 `user_id` 在 `interview_sessions` 表中有至少一条 `target_role IS NOT NULL` 的记录，说明系统已知道用户想练习的方向。

**新用户**：无任何历史 session，或所有 session 的 `target_role` 均为空。

> 注：是否完成过完整面试不作为判断依据——用户可能进来填了岗位然后中途放弃，但系统已记住方向，仍视为老用户。

---

## 三、API 设计

### 新增：`GET /api/v1/interview/context`

从该用户最近一条 `target_role IS NOT NULL` 的 session 中读取上下文，供 `/coach` 页面判断新老用户并展示历史信息。

**Response：**

```json
{
  "is_returning": true,
  "target_role": "AI Agent 工程师",
  "target_company": "字节跳动",
  "user_background": "做过 LangGraph 多 Agent 系统，想练分布式架构方向",
  "session_count": 7
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `is_returning` | bool | `target_role IS NOT NULL` 的 session 存在则为 true |
| `target_role` | str \| null | 最近有效 session 的岗位，新用户为 null |
| `target_company` | str \| null | 最近有效 session 的目标公司 |
| `user_background` | str \| null | 最近有效 session 的背景描述 |
| `session_count` | int | 该用户历史 session 总数（含 abandoned） |

**查询逻辑（伪代码）：**

```python
latest = (
    SELECT * FROM interview_sessions
    WHERE user_id = :user_id AND target_role IS NOT NULL
    ORDER BY started_at DESC
    LIMIT 1
)
count = SELECT COUNT(*) FROM interview_sessions WHERE user_id = :user_id
```

**鉴权**：Bearer token（Clerk JWT），与现有接口一致。

### 扩展：`POST /api/v1/interview/reset`

在现有签名上增加两个**可选**参数，用于接收 coach 传来的上下文：

```json
{
  "target_role": "AI Agent 工程师",
  "user_background": "LangGraph 多 Agent 系统"
}
```

后端收到后写入新建 session 的对应字段，LangGraph `opening` 节点可直接跳过重新收集这两项。

---

## 四、前端设计

### 4.1 `/coach` 页面：读真实数据

**加载时序：**

```
CoachDashboard mount
  → GET /api/v1/interview/context (带 Clerk token)
  → 根据 is_returning 切换 UI 状态
  → 展示真实的 target_role / session_count
```

**UI 变更：**
- 移除右上角 Demo toggle（"老用户 · 已 7 场" / "新用户 · 第 0 场"）
- 老用户开场语中的"过去 7 场"改为读 `session_count`
- 老用户开场语中提到"量化结果"等弱点的部分，本期保持静态文案（个性化分析是第五步 Coach Agent 的范围）
- 新用户展示岗位选择快捷按钮，不变

**加载状态：** API 返回前显示骨架屏（`isLoading` 状态），防止 UI 闪烁。

### 4.2 Context 传递：Coach → Interview

**点击"进入考场"时：**

```typescript
// coach-dashboard.tsx
const context = { target_role: selectedRole, user_background: userBackground };
sessionStorage.setItem("interview_context", JSON.stringify(context));
router.push("/interview");
```

**`/interview` 加载时：**

```typescript
// interview-chat.tsx，在现有 resetInterviewSession 调用处
const raw = sessionStorage.getItem("interview_context");
const context = raw ? JSON.parse(raw) : null;
sessionStorage.removeItem("interview_context"); // 读一次即清除

if (token) await resetInterviewSession({ token, ...context });
```

### 4.3 动态化前端开场白

**当前问题：** `OPENING_MESSAGE` 是静态字符串，每次进入都显示通用问候，与 coach 传来的上下文割裂。

**约束：** 后端 `/turn` 接口是 request-response 模型，必须由用户先发消息才能触发 Agent 响应。因此前端仍需显示一条开场消息，但内容改为**动态生成**：

| 场景 | 前端显示的开场消息 |
|---|---|
| 从 coach 跳转，携带 `target_role` | `"好，今天练 {target_role}。{user_background 摘要（如有）}准备好了发消息开始。"` |
| 直接访问 `/interview`，无 sessionStorage | 显示引导信息：`"你好！在开始之前，请告诉我你想练习的面试岗位..."` (包含列表形式的示例) |

**实现：**

```typescript
function buildOpeningMessage(context: { target_role?: string; user_background?: string } | null) {
  if (context?.target_role) {
    // ... (处理已有上下文逻辑)
  }
  return "你好！在开始之前，请告诉我你想练习的面试岗位、公司，或特定的技术主题。\n\n**你可以这样发起：**\n\n**前端开发**（例如：React 性能优化）\n\n**后端开发**（例如：Java/Go 微服务）\n\n**移动端开发**（例如：iOS/Android 实战）\n\n**Python AI Agent**（例如：RAG 优化）\n\n请直接输入你的目标，我们将立即开始。";
}
```

用户发出第一条消息后，LangGraph `opening` 节点从 session 中读到已有的 `target_role`，**直接跳过重新收集岗位**，进入面试主循环。

---

## 五、数据流全景

```
用户在 /coach 选择岗位
  ↓ 点击"进入考场"
  ↓ sessionStorage.setItem("interview_context", { target_role, user_background })
  ↓ router.push("/interview")

/interview 加载
  ↓ 读 sessionStorage → 清除
  ↓ POST /api/v1/interview/reset  { target_role, user_background }
  ↓ 后端创建新 session，写入 target_role / user_background
  ↓ 用户发第一条消息（或后端 opening 节点主动开口）
  ↓ LangGraph opening 节点读到 target_role 已有值
  ↓ 老用户：跳过收集，直接确认今日方向
  ↓ 新用户：无 target_role，正常开始收集
```

---

## 六、对现有代码的影响

| 文件 | 变更类型 | 说明 |
|---|---|---|
| `backend/app/api/v1/interview.py` | 新增路由 | `GET /interview/context` |
| `backend/app/schemas/interview.py` | 扩展 | 新增 `UserContextResponse`, 扩展 `ResetRequest` |
| `frontend/app/coach/coach-dashboard.tsx` | 修改 | 替换 mock 数据为 API 调用，移除 Demo toggle |
| `frontend/lib/interview-chat.ts` | 扩展 | `resetInterviewSession` 增加可选 `target_role / user_background` 参数 |
| `frontend/app/interview/_components/interview-chat.tsx` | 修改 | `OPENING_MESSAGE` 改为动态生成，读 sessionStorage context |

---

## 七、测试策略

| 测试类型 | 覆盖点 |
|---|---|
| 后端单元测试 | `GET /interview/context`：有历史 session / 无历史 session / target_role 为空的 session |
| 后端单元测试 | `POST /reset` 扩展参数：带 target_role 写入 / 不带仍正常创建 |
| 前端单元测试 | `CoachDashboard`：加载中骨架屏、老用户 UI、新用户 UI |
| 前端单元测试 | `InterviewChat`：空消息初始态、sessionStorage 读取并清除 |
| 手动验收 | coach → 进入考场 → interview 首条消息来自后端（不是前端硬编码） |
| 手动验收 | 直接访问 `/interview` 不经过 coach → 后端正常按新用户流程开场 |

---

## 八、不在本设计范围内

- Coach Agent 的个性化历史分析（"你过去 7 场有个规律..."）→ 第五步
- UserProfile / 偏好持久化表 → 随长短期记忆迭代引入
- 面试记忆（长期/短期）→ 独立 spec
- 多 Agent 配置 → 独立 spec
- 评估写入 DB → 第四步
