# 设计文档：面试官单轮流式问答（一问一答打通）

- 日期：2026-05-24
- 分支：`feat/interview-chat`
- 状态：待评审

## 1. 目标与范围

打通「前端发问 → 后端调 LLM → 流式回复」的最短可用链路，让 `interview` 页面出现真实的一问一答。对应项目知识文档「推荐开发顺序」的第一步（跑通流式对话基础链路）+ 第二步雏形（单一面试官 Agent）。

**这一步要做的：**

- 后端新增一个 SSE 流式对话接口，用「面试官」system prompt 调 OpenAI `gpt-4o`。
- 前端把 `interview` 页面从占位页换成真实聊天界面，照 `html/interview.html` 的聊天外壳视觉，用 Tailwind/shadcn 重写。
- 前端持有对话历史，每次请求带上完整历史；后端无状态、不落库。

**明确不做（YAGNI）：**

- 不建任何数据库表、不存对话历史、不做服务端记忆。
- 不引入 LangGraph / LangChain（留到后续多 Agent 编排）。
- 不实现 `interview.html` 里的多 Agent 演示层：Trace 执行面板、评分卡、记忆卡、顶部题目进度 pills、状态机、写死的题库与追问。
- 不动 `coach` / `dashboard` / `reports` 页面。
- 不切换到 Anthropic（沿用已配好的 OpenAI）。

## 2. 架构与数据流

```
interview 页面（client component）
  │  fetch POST，Authorization: Bearer <clerk token>，body={messages:[...]}
  ▼
FastAPI  POST /api/v1/interview/chat   ← Depends(get_current_user_id) 鉴权
  │  调用 services/interview_chat.py
  ▼
chat service：面试官 system prompt + messages → AsyncOpenAI(stream=True)
  │  逐 chunk yield
  ▼
EventSourceResponse(SSE) ──delta/done/error──▶ 前端 fetch 流式读取 ──▶ 逐字渲染气泡
```

- **无状态多轮**：服务端不保存任何东西，「记忆」由前端持有的 `messages` 数组提供，每次请求重新发全量历史。
- **单次请求生命周期**：建流 → 逐 chunk 转 SSE → 结束。出错在流内以 `error` 事件返回，普通 HTTP 错误（401/422）仍走统一 `Response` 结构。

## 3. 后端设计

### 3.1 接口契约

`POST /api/v1/interview/chat`

- 鉴权：`Depends(get_current_user_id)`，复用现有 Clerk 校验。
- 请求体（新增 `app/schemas/interview.py`）：

  ```json
  { "messages": [ { "role": "user", "content": "..." }, { "role": "assistant", "content": "..." } ] }
  ```

  校验规则：
  - `messages` 非空，条数上限 50（防滥用 / 防超长上下文）。
  - `role` ∈ {`user`, `assistant`}。
  - 每条 `content` 去空白后非空，单条长度上限 4000 字符。
  - 最后一条必须是 `user`（否则 422）。

- 响应：`text/event-stream`（`sse-starlette` 的 `EventSourceResponse`），事件类型：
  - `delta`：`{ "text": "<增量文本>" }`，每收到一个模型 chunk 推一次。
  - `done`：`{}`，正常结束。
  - `error`：`{ "message": "<面向用户的错误文案>" }`，建流失败或流中途异常时推送，前端据此展示错误态。

校验失败/未登录走全局异常处理器，返回统一 `Response{code,msg,data}`（422 / 401）。

### 3.2 LLM 调用封装：`app/services/interview_chat.py`

直连 `openai` 的 `AsyncOpenAI`，不经 LangChain。该模块满足 CLAUDE.md 对 LLM 调用的三条硬性要求：

- **timeout**：调用设超时（新增配置 `llm_timeout_seconds`，默认 30）。
- **retry**：用 `tenacity` 仅包裹「建立流之前」的步骤（创建 stream）。一旦开始逐 chunk yield 就**不再重试**——否则重试会让已输出的内容重复。重试 2 次、指数退避，仅对可重试错误（连接错误 / 超时 / 5xx）生效。代码注释会写明此约束。
- **失败日志**：建流失败（重试耗尽）与流中途异常都记 `structlog` 的 `error` 日志，含 `user_id`、错误类型；绝不静默吞，绝不 `except Exception: pass`。

对外暴露一个异步生成器，逐个 yield 文本增量；建流阶段失败抛出业务异常由路由转 `error` 事件，迭代阶段异常在生成器内捕获并以 `error` 事件结束。

system prompt（中文面试官，定为模块常量）：

> 你是一位资深技术面试官，正在对候选人进行中文模拟面试。请根据候选人最新的回答，提出有针对性的面试问题或追问，一次只问一个问题，语气专业、简洁、克制，不要替候选人作答，也不要长篇大论的点评。

### 3.3 配置

复用现有 `openai_api_key`、`openai_model_chat`（`gpt-4o`）。`app/core/config.py` 新增：

- `llm_timeout_seconds: int = 30`

不硬编码任何密钥（沿用 pydantic-settings）。

### 3.4 路由注册

`app/api/v1/interview.py` 新建 `router`，在 `app/main.py` 以 `prefix="/api/v1"` 挂载（与 health/auth 一致）。

## 4. 前端设计

### 4.1 页面与组件

- `frontend/app/interview/page.tsx`：从 `PlaceholderPage` 换成真实聊天页，保留现有 `AppShell` 顶部导航与登录态外壳，主内容区嵌入聊天舱。
- 拆分组件（职责单一）：
  - `InterviewChat`：页面主体，持有 `messages` 状态与发送逻辑。
  - `MessageBubble`：单条消息气泡（user / assistant 两种样式）。
  - `TypingIndicator`：三点跳动动画（等待首个 delta 时显示）。
  - 输入区：复用 shadcn 的 `Input` + 圆形发送 `Button`（无需新增依赖）。
- 数据获取逻辑放 `frontend/lib/interview-chat.ts`（一个 `streamInterviewChat()` 函数 / hook），不堆在组件里。

### 4.2 视觉规格（用 Tailwind 还原 `interview.html`）

把 html 里的 CSS 变量映射到 Tailwind（含 `dark:` 暗色）：

- 主色紫 `#534AB7`；用户气泡：紫→`#7c3aed` 渐变、白字、圆角 `14px 14px 3px 14px`、右对齐。
- AI 气泡：浅灰底（`--bg2`）、细边框、圆角 `14px 14px 14px 3px`、左对齐。
- 顶部品牌栏：`AI 模拟面试舱 · Agent Cabin`，紫→玫红渐变文字（右侧的 pills / 题号**不做**）。
- 极光背景：右上角 `radial-gradient` + `blur`，绝对定位、`pointer-events:none`。
- 输入框：圆角 pill，聚焦时紫色描边 + 光晕；发送钮 44px 圆形，有内容时切紫色激活态。
- typing：三个小圆点错位 `bounce`。
- 消息进入：轻微上移淡入。
- 暗色模式：跟随 `prefers-color-scheme`（Tailwind `dark:`）。

### 4.3 流式读取与渲染

- 用 `fetch`（**不用 `EventSource`**，因为它无法带 `Authorization` header）：
  - URL：`${NEXT_PUBLIC_API_URL}/api/v1/interview/chat`。
  - 前端直连后端接口，不走 Next rewrite 代理；依赖后端 CORS 已允许本地前端域名。
  - headers：`Authorization: Bearer ${await getToken()}`、`Content-Type: application/json`。
  - body：当前 `messages` 全量。
- 读 `response.body.getReader()`，手写一个最小 SSE 解析（按 `\n\n` 切事件，解析 `event:` 与 `data:` 行），按事件类型处理 `delta` / `done` / `error`。不新增 SSE 库。
- 渲染：发送后立即追加用户气泡 + 一个空的 assistant 气泡占位并显示 typing；收到首个 `delta` 移除 typing 并开始把增量追加进该气泡；`done` 收尾；`error` 把该气泡替换为错误提示。
- 用 `AbortController`，组件卸载 / 重新发送时中止上一个请求。

### 4.4 状态处理

- empty：进页面只有一条静态开场白（assistant）：「你好，说说你想练什么方向的面试题？可以直接说方向（比如「分布式系统」「JVM 调优」），也可以粘贴 JD。」
- loading：流式进行中，输入框与发送钮禁用，AI 气泡显示 typing / 正在长出的文本。
- error：请求失败或收到 `error` 事件，气泡显示明确错误文案，允许重试（重新发送）。

## 5. 测试计划

### 5.1 后端（pytest，mock 掉 `AsyncOpenAI`，不连真实服务）

- 正常：mock stream 产出多个 chunk → 响应含若干 `delta` + 一个 `done`，拼接文本正确。
- 建流失败重试：mock create 连续抛可重试错误致重试耗尽 → 收到 `error` 事件 + 记 error 日志（覆盖 retry 路径）。
- timeout：mock 抛 `APITimeoutError` → `error` 事件（覆盖 timeout 路径）。
- 流中途异常：mock 迭代到一半抛错 → 已发的 `delta` 之后补一个 `error` 事件，不抛 500。
- 鉴权：无 / 非法 token → 401。
- 入参校验：空 `messages`、空 `content`、最后一条非 `user`、超长 → 422。

### 5.2 前端（vitest + testing-library，mock `fetch`）

- 渲染开场白（empty 态）。
- 发送后出现用户气泡 + typing；mock 一个返回 SSE 文本的 `ReadableStream`，断言 AI 气泡最终文本正确。
- `error` 事件 / fetch 失败 → 显示错误态。
- 避免真实定时器与不稳定时间依赖。

## 6. 风险与缓解

- **EventSource 不能带 header** → 用 `fetch` + `ReadableStream`（已定）。
- **流式重试会重复输出** → 仅在建流前重试，迭代中只记日志 + `error` 事件（已定）。
- **Tailwind 还原度** → 用户选择重写而非直接搬 CSS，气泡 / 极光 / 动画需手工对齐，验收以 `interview.html` 视觉为准。
- **CORS / SSE**：后端 `cors_origins` 已含 `http://localhost:3000`、`allow_headers=*`；前端用 Bearer header、不依赖 cookie，无需 `credentials`。
- **token 过期**：每次发送前 `getToken()` 取新 token。
- **未来多轮上下文增长**：本步靠条数 / 长度上限兜底；服务端记忆留到后续建表阶段。

## 7. 涉及文件清单

新增：

- `backend/app/schemas/interview.py`（请求体模型）
- `backend/app/services/interview_chat.py`（LLM 流式封装 + system prompt）
- `backend/app/api/v1/interview.py`（SSE 路由）
- `backend/tests/test_interview_chat.py`（后端测试）
- `frontend/lib/interview-chat.ts`（流式请求逻辑）
- `frontend/app/interview/_components/*`（聊天 UI 组件）
- 前端对应测试文件

修改：

- `backend/app/core/config.py`（新增 `llm_timeout_seconds`）
- `backend/app/main.py`（挂载 interview 路由）
- `frontend/app/interview/page.tsx`（替换占位页）
