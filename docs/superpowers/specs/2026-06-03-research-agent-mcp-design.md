# Prepare 阶段调研 Agent（MCP 接入 job-intel）设计文档

- 日期：2026-06-03
- 分支：feature/research-agent-mcp（实现期创建）
- 范围：Prepare 阶段新增 research_agent 节点 + job-intel 项目暴露 MCP server + 两节点并行 + 下游 Agent 消费 job_intel 数据

---

## 一、背景与问题

### 1.1 当前状态

multi-agent-coach 的 Prepare 阶段当前由 Supervisor 调度 3 个固定节点：

- `memory_search` — 查候选人历史 session 薄弱点 + 简历摘要兜底
- `jd_analysis` — 把 `jd_raw` 文本走一次 LLM 调用变结构化（5 字段 `JDContext`：company / role / key_skills / focus_areas / difficulty）
- `question_gen` — 综合 direction + JD + weak_areas + background 出 5 道题

这套流程**只在"候选人内部世界"运行**：用户简历、历史表现、用户粘贴的 JD 文本。**没有任何外部世界信息**——没有公司背景、没有团队画像、没有候选人简历对此岗位的 Gap 分析、没有针对性的准备建议。

姊妹项目 `job-intel-agent` 已经具备这些能力：

- 抓 JD URL（Firecrawl）
- 联网搜公司背景（Tavily）
- 简历 × JD 对照分析
- 产出 6 模块结构化报告（职位解读 / 简历匹配 / 公司画像 / 面试题预测 / 薪资参考 / 准备建议）

### 1.2 两个产品的关系

两者面向同一类用户（求职者），解决求职链路上**前后衔接但独立**的环节：

| 产品                | 业务定位                                                          |
| ------------------- | ----------------------------------------------------------------- |
| `job-intel-agent`   | 面试前的"调研工具" — 输入岗位 → 输出情报报告                      |
| `multi-agent-coach` | 面试演练系统 — 输入岗位 + 简历 → 走完五阶段 → 输出评分 + 成长建议 |

业务关系：**multi 把 job-intel 当作备课阶段的"情报供应商"**。单向消费，不共享数据库，两个系统在生命周期上完全独立。

### 1.3 为什么本期值得做

本期本质上要解决两件事：

1. **业务上**：把 multi 从"只看候选人内部世界"扩展到"也看目标岗位外部世界"。让 Designer 出题方向更贴岗位、Evaluator 评分更贴岗位门槛、Coach 反馈更针对岗位 Gap、Interviewer 面试官 persona 更像目标公司
2. **架构上**：突出 multi 通过 **MCP 协议**接入外部 Agent 系统的能力，并让这种接入发生在**Agent 自主"工具思考"**链路里——不是硬编码 RPC，是 LLM 决策的 ReAct loop

### 1.4 本期目标

- 在 job-intel 项目里新增一个 MCP server，把现有 service 函数标准化暴露为 5-6 个 MCP 工具
- 在 multi 的 Prepare 阶段新增 `research_agent` 节点——内部是 ReAct sub-agent，工具来自 job-intel MCP，自主决策何时调哪个、什么时候停
- `research_agent` 与 `memory_search` **并行执行**（数据源完全独立）
- `jd_analysis` 节点**退化为降级兜底**（research_agent 失败时启用）
- 下游 Designer / Evaluator / Coach / Interviewer 各自从 `job_intel` State 字段消费自己关心的数据
- 工具调用过程接入 multi 现有 trace 基础设施，可视化"Agent 工具思考"链路

---

## 二、设计原则

1. **真工具思考**：research_agent 内部是标准 ReAct loop（`bind_tools` + think/tool_call/observe），不是写死的"调 A 再调 B"
2. **跨系统解耦**：job-intel 和 multi 在数据库、生命周期、部署上完全独立；只通过 MCP 通信
3. **业务边界清晰**：job-intel 只负责"产情报"，multi 负责"用情报开展面试"；两侧不替对方做业务决策
4. **会话级一次写**：research_agent 在备课阶段写入 `job_intel` 后，**整场面试只读不写不回查**，下游所有 Agent 读同一份
5. **降级必须无感**：MCP 不可用时，Prepare 自动走 `jd_analysis` 兜底路径，用户感知不到差异
6. **不做的事**：
   - 不在面试阶段挂任何 job-intel 工具（破坏沉浸感）
   - 不让 multi 接管 job-intel 已有的简历/JD 处理能力（不做"中台化"重构）
   - 不让 `interview_qa`（LLM 编的题预测）进入 Designer 出题链路（避免 LLM 自循环）
   - 不让 `salary_range`（LLM 编的薪资数字）进入任何 Agent prompt（避免假数据误导）
   - 不做 Human-in-the-Loop 让用户审核 / 修改备课笔记（留给后续 V2）

---

## 三、架构

### 3.1 整体结构

```
┌─────────────────────────────────────────────────────────────┐
│                  multi-agent-coach                            │
│                                                               │
│  Prepare Supervisor (中央调度，决策 next_action)               │
│        │                                                      │
│        │ 第一次决策：fan-out                                   │
│        ▼                                                      │
│   ┌────┴────────────────────────────┐                         │
│   │                                 │                         │
│   ▼                                 ▼                         │
│ memory_search              research_agent ★新增               │
│ (内部 DB 查询)              (ReAct sub-agent)                  │
│ ~ 1-3s                      ~ 20-60s                          │
│                                  │                            │
│                                  │ MCP streamable HTTP        │
│   │                              ▼                            │
│   │                       ┌──────────────────────────────┐    │
│   │                       │   job-intel MCP Server        │    │
│   │                       │   暴露 5-6 个工具：            │    │
│   │                       │   • extract_jd_text           │    │
│   │                       │   • web_search                │    │
│   │                       │   • analyze_position          │    │
│   │                       │   • generate_position_report  │    │
│   │                       │   • scrape_jd_url (可选)      │    │
│   │                       │   • extract_resume (可选)     │    │
│   │                       └──────────────────────────────┘    │
│   │                              │                            │
│   └─────────────┬────────────────┘                            │
│                 ▼ 两路汇合                                     │
│           Supervisor (第二次决策)                              │
│                 │                                              │
│                 ▼                                              │
│           question_gen                                         │
│           (读 weak_areas + job_intel.job_interpretation)       │
│                 │                                              │
│                 ▼                                              │
│                END                                             │
│                 │                                              │
│                 ▼ State 透传                                   │
│                                                                │
│  Interview / Evaluate / Coach 阶段                            │
│  各 Agent 从 State 读 job_intel 对应字段                      │
└───────────────────────────────────────────────────────────────┘
```

### 3.2 业务上的并行依据

`memory_search` 与 `research_agent` 满足"教科书式可并行"的全部条件：

| 维度       | memory_search                    | research_agent                  |
| ---------- | -------------------------------- | ------------------------------- |
| 数据源     | multi 自家 Postgres              | 外部 MCP（job-intel）           |
| 关心的对象 | 候选人自己（过去表现）           | 目标岗位（外部世界）            |
| 依赖输入   | `user_id`                        | `jd_raw` / `user_background`    |
| 产出字段   | `weak_areas` + `user_background` | `job_intel`                     |
| 消费者     | `question_gen`                   | `question_gen` 和下游所有 Agent |

输入不重叠、产出不重叠、彼此不依赖。

### 3.3 Supervisor 决策升级

Supervisor 从"每次决策一个 next_action"升级为"支持 fan-out 多 action"：

```
第一次决策（备课开始）：
  ┌ 有 user_id            → 启动 memory_search
  ├ 有 jd_raw 或 jd_url    → 同时启动 research_agent
  ├ 无 jd_raw 且无 jd_url  → 跳过 research_agent
  └ 两路并行启动

第二次决策（两路汇合后）：
  ┌ research_agent 成功      → 直接 question_gen（跳过 jd_analysis）
  ├ research_agent 失败/未跑 → jd_analysis 兜底
  └ jd_analysis 完成        → question_gen → END
```

---

## 四、job-intel 端设计

### 4.1 新增 MCP server

在 job-intel 项目下新增独立 ASGI 进程：

- 文件位置：`backend/app/mcp_server.py`
- 使用：FastMCP（官方 `mcp` Python SDK 内置）
- 传输：streamable HTTP，默认监听 `http://localhost:9001/mcp`
- 进程独立于现有 FastAPI 主应用，避免互相影响

### 4.2 暴露的工具清单

复用现有 service 函数，做无状态包装。**不写 jobs/reports 表**（绕开 user_id 上下文与 LangGraph interrupt）。

| 工具名                     | 底层函数                            | 业务作用                     | 必选/可选 |
| -------------------------- | ----------------------------------- | ---------------------------- | --------- |
| `extract_jd_text`          | `llm_service.extract_job_info`      | JD 文本 → 结构化字段         | 必选      |
| `web_search`               | `search_service.search`             | Tavily 搜公司背景            | 必选      |
| `analyze_position`         | `graphs/nodes.analyze_node`         | 综合 JD + 搜索结果出分析摘要 | 必选      |
| `generate_position_report` | `graphs/nodes.generate_report_node` | 最终 6 模块完整报告          | 必选      |
| `scrape_jd_url`            | `crawler_service.scrape_url`        | Firecrawl 抓 JD 网页         | 可选      |
| `extract_resume`           | `llm_service.extract_resume_info`   | 简历文本结构化               | 可选      |

### 4.3 关键技术决策

- **绕开现有 LangGraph 单例**：`get_research_graph()` 包含 `review_draft` 节点会触发 `interrupt()`，对外 MCP 工具不能等 HIL。MCP server 直接调底层节点函数（`analyze_node` / `generate_report_node`），不走完整 graph
- **绕开 Celery**：MCP 工具是同步调用语义（最长 60-90s），不进 Celery 队列
- **不写 DB**：MCP 工具是无状态的，不绑定 user_id，写库会污染 job-intel 原系统数据

### 4.4 启动方式

- 开发环境：`uv run python -m app.mcp_server`（独立进程）
- `dev.sh` 同步追加启动行
- 依赖：`pyproject.toml` 加 `mcp[cli]>=1.0.0`

---

## 五、multi 端设计

### 5.1 新增 research_agent 节点

**职责定位**：Prepare 阶段的"调研专员"，研究目标岗位的外部世界。与 `memory_search`（查内部历史）形成业务分工。

**内部模式**：标准 LangChain ReAct loop

```
research_agent 节点内部：

  初始化 chief LLM + bind_tools(MCP 工具列表)
        │
        ▼
  ┌────────────────────────────────────────┐
  │  ReAct iteration (max 6 iter, 90s)    │
  │                                        │
  │  think  → 当前手上有什么？还缺什么？      │
  │     │                                  │
  │     ▼                                  │
  │  tool_call → 调一个 MCP 工具            │
  │     │                                  │
  │     ▼                                  │
  │  observe → 看工具返回                   │
  │     │                                  │
  │     ▼                                  │
  │  think → 信息够吗？                     │
  │     │                                  │
  │     ├─ 不够 → 继续下一轮                 │
  │     └─ 够了 → 调 generate_position_report
  │                  → 写 State → 结束     │
  └────────────────────────────────────────┘
```

**决策由 LLM 自主**：先抓 JD 还是先搜公司、什么时候信息够了、最后是否补一次综合调用——全部 LLM 决定。

### 5.2 工具清单与启动条件

```
启动条件：jd_raw 存在 或 jd_url 存在
工具列表：4 必选 + 2 可选 = 最多 6 个
最大迭代数：6
总超时：90s
```

工具数量上限 6 个的依据：超过 6 个 LLM 选择困难、决策质量下降；4 必选已覆盖核心路径（结构化 → 搜索 → 分析 → 综合）。

### 5.3 止步条件（兜底，不依赖 LLM 判断）

| 条件                                                       | 行为                                                              |
| ---------------------------------------------------------- | ----------------------------------------------------------------- |
| LLM 主动决定"信息够了" + 已调用 `generate_position_report` | 正常结束，写 State                                                |
| 工具调用次数超 6 次                                        | 强制收尾：用已有数据再调一次 `generate_position_report`           |
| 总耗时超 90s                                               | 超时结束，写 `job_intel: None` → Supervisor 走 `jd_analysis` 兜底 |
| MCP 连接失败 / 任何工具异常                                | 同上                                                              |

### 5.4 State 字段设计

在 `agents/prepare/state.py` 的 `PrepareState` 新增：

```python
class JobIntel(TypedDict, total=False):
    # 来自 generate_position_report 的 6 模块（4 用 2 砍）
    job_interpretation: dict    # 下游 Designer + Evaluator 消费
    resume_match: dict          # 下游 Designer + Coach 消费
    company_profile: dict       # 下游 Interviewer persona 消费
    prep_suggestions: list[dict] # 下游 Coach 消费
    interview_qa: list[dict]    # ★ 保留字段但下游不消费（避免 LLM 自循环）
    salary_range: dict          # ★ 保留字段但下游不消费（避免假数据误导）

    # research_agent 的过程产物（用于 trace 展示和故障排查）
    _trace: dict
```

`_trace` 子字段：

- `tools_used: list[str]` — 实际调用过的工具名序列
- `iterations: int` — ReAct 总轮次
- `elapsed_ms: int` — 实际耗时
- `final_thought: str` — Agent 最后一次 think 内容

### 5.5 跨阶段透传

`InterviewState` / `EvaluatorState` / `CoachState` 各加 `job_intel: JobIntel | None` 字段，从 PrepareState 透传。

实现路径：现有的 Prepare → Interview 的 transition 函数里加一行 `job_intel: prepare_state.get("job_intel")`。

---

## 六、下游 Agent 消费方式

### 6.1 消费映射表

| 下游 Agent                  | 读 job_intel 哪些字段                                  | 怎么用                                                                        |
| --------------------------- | ------------------------------------------------------ | ----------------------------------------------------------------------------- |
| `question_gen` (Prepare 末) | `job_interpretation.hard_requirements` + `focus_areas` | 出题 prompt 注入"这岗位硬要求是 X，重点考察 Y"                                |
| Interviewer `chief`         | `company_profile.summary` + `company_profile.tags`     | system prompt 加 "你是一位 [tags] 风格的面试官"                               |
| Designer                    | `job_interpretation` + `resume_match`                  | 出题时决定"问哪个硬要求"、"探测候选人哪个 strength"                           |
| Evaluator                   | `job_interpretation.hard_requirements`                 | 评分 prompt 加 "按这岗位的真实门槛打分，特别关注是否触及 [hard_requirements]" |
| Coach (反馈阶段)            | `resume_match.gaps` + `prep_suggestions`               | 反馈 prompt 加 "候选人针对此岗位的 Gap 是 X，建议方向是 Y"                    |

### 6.2 消费防御

所有下游 Agent 用 `state.get("job_intel", {}).get("xxx")` 安全取值。`job_intel` 为 `None` 时（MCP 不可用），下游 prompt 回退到现有逻辑，不抛错、不阻断。

### 6.3 显式不消费的字段

- ❌ `interview_qa`（LLM 编的题预测）：Designer 现场基于候选人画像生成题目，比静态预测题更准；引入会让系统变成 LLM 出题 → LLM 答题 → LLM 评分的自循环
- ❌ `salary_range`（LLM 编的薪资数字）：教练业务跟薪资咨询无关；假数字进入 prompt 反而误导

字段在 State 里保留，是为了 trace 展示完整性（用户能看到 research_agent 调研出了什么），但不进入任何 Agent 的决策链路。

---

## 七、跨系统通信细节

### 7.1 协议选型

- **传输**：MCP streamable HTTP
- **不用 stdio**：multi 是长进程 ASGI app，stdio 模式每次 multi 重启都要 spawn 新子进程，且子进程与 job-intel 主服务的 DB/Redis 连接无法复用
- **不用 SSE 传输**：streamable HTTP 是 MCP 协议 2025 推荐方案，兼容性更好

### 7.2 客户端库

multi 端使用 `langchain-mcp-adapters`（langchain-ai 官方）：

- `MultiServerMCPClient` 应用启动期建立连接，缓存工具列表
- `client.get_tools()` 返回 LangChain `BaseTool` 列表
- 直接 `bind_tools(mcp_tools)` 挂入 research_agent 的 LLM，**与现有 ReAct 模式完全兼容**

### 7.3 配置

multi 端 `.env` 新增：

```
MCP_JOB_INTEL_URL=http://localhost:9001/mcp
MCP_JOB_INTEL_TIMEOUT_SECONDS=90
```

### 7.4 部署模式

- 本地开发：`dev.sh` 同时启动 multi + job-intel API + job-intel MCP server（独立端口）
- 生产环境：见 7.5

### 7.5 生产部署模式（Railway）

后端在 Railway 部署。Railway 的部署单位是 Service（一个进程一个 Service），同 Project 内的 Service 之间可以走**私有网络**（Private Networking）通信，不暴露公网、零延迟、不计费。

#### 7.5.1 Railway Project 内的服务拆分

本期上线后，multi 所在的 Railway Project 会包含 3 个后端 Service：

```
Railway Project: multi-coach
├── multi-coach-api          ← 现有，FastAPI 主服务
├── job-intel-api            ← 现有/新增，FastAPI 主服务（视 job-intel 是否已上 Railway）
└── job-intel-mcp ★新增      ← 本期新增，MCP server 独立 Service
```

**关键决策**：job-intel-mcp 作为**独立 Service** 部署，不和 job-intel-api 同进程。理由：

- MCP server 与 FastAPI 是不同生命周期（崩了不互相拖累）
- Railway 单 Service 单进程，强制独立
- 长任务（research_agent 调用最长 90s）独占进程，不抢 API 请求资源

#### 7.5.2 私有网络通信

Railway 私有网络通过 `<service-name>.railway.internal` 内部 DNS 解析，**仅 IPv6**。

multi 的环境变量：

```
MCP_JOB_INTEL_URL=http://job-intel-mcp.railway.internal:9001/mcp
```

**MCP server 启动时必须监听 IPv6**：

```python
# job-intel/backend/app/mcp_server.py
mcp = FastMCP("job-intel", host="::", port=int(os.getenv("PORT", "9001")))
```

监听 `0.0.0.0`（仅 IPv4）在 Railway 私有网络里会**连接不上**——这是 Railway 部署的常见坑，必须显式写在文档里。

Railway 会自动注入 `PORT` 环境变量给每个 Service，MCP server 用它而不是写死 9001。

#### 7.5.3 网络隔离与鉴权

- job-intel-mcp Service **不绑定公网域名**（Railway 默认不暴露，除非手动开 Public Networking）
- multi-coach-api **绑定公网域名**（用户访问）
- 鉴权：靠 Railway 私有网络的物理隔离，**本期不做应用层鉴权**
- V2 如果 job-intel-mcp 要对外（比如给其他项目用），再加 Bearer token 中间件

#### 7.5.4 部署配置清单

job-intel-mcp Service（新建）的 Railway 配置：

| 项                 | 值                                                                                 |
| ------------------ | ---------------------------------------------------------------------------------- |
| Source             | 同 job-intel-api 的仓库                                                            |
| Build              | 复用现有 Dockerfile 或 `uv sync`                                                   |
| Start command      | `uv run python -m app.mcp_server`                                                  |
| Internal port      | 由 Railway 注入 `PORT`                                                             |
| Public networking  | **关闭**                                                                           |
| Private networking | **开启**                                                                           |
| 共享环境变量       | `OPENAI_API_KEY` / `TAVILY_API_KEY` / `FIRECRAWL_API_KEY`（与 job-intel-api 同源） |

multi-coach-api Service（现有，新增环境变量）：

| 新增环境变量                    | 值                                                                  |
| ------------------------------- | ------------------------------------------------------------------- |
| `MCP_JOB_INTEL_URL`             | `http://job-intel-mcp.railway.internal:${{job-intel-mcp.PORT}}/mcp` |
| `MCP_JOB_INTEL_TIMEOUT_SECONDS` | `90`                                                                |

注意 `${{job-intel-mcp.PORT}}` 是 Railway 的 Service 间环境变量引用语法，自动拿到目标 Service 的 PORT。

#### 7.5.5 跨 Railway Project 兜底（不在本期范围）

如果未来 multi 和 job-intel 拆到不同 Railway Project（比如 job-intel 要独立给外部用），私有网络不可用，必须：

- job-intel-mcp 绑定公网域名 + HTTPS
- 加 Bearer token 鉴权中间件
- multi 端配置 `MCP_JOB_INTEL_URL=https://job-intel-mcp.xxx.app/mcp` + `MCP_JOB_INTEL_TOKEN=xxx`

本期不实现，但 MCP server 代码结构要预留鉴权 hook（FastMCP 支持 middleware）。

#### 7.5.6 健康检查与冷启动

Railway 会对每个 Service 做 TCP 健康检查。MCP server 监听端口本身即视为健康，不需要额外 `/health` 路径。

Railway 免费 plan 有冷启动行为（无流量休眠）；付费 plan 不会休眠。multi 启动期建立 MCP 连接时，如果 job-intel-mcp 处于冷启动，首次 `get_tools()` 可能 5-10s，需要在 `mcp_client.py` 加重试逻辑（最多 3 次，间隔 2s）。

---

## 八、故障与降级

| 故障                  | 表现                                    | 降级行为                                                 | 用户感知                 |
| --------------------- | --------------------------------------- | -------------------------------------------------------- | ------------------------ |
| MCP server 没启动     | `MultiServerMCPClient` 连接失败         | research_agent 节点失败，Supervisor 走 `jd_analysis`     | 无感（备课流程正常完成） |
| MCP 工具调用超时      | 单工具 30s 无响应                       | 该 iteration 标记失败，LLM 看到错误后决策跳过或重试      | 无感                     |
| research_agent 总超时 | 90s 仍未完成                            | 强制结束，`job_intel: None`，Supervisor 走 `jd_analysis` | 无感（备课略慢）         |
| 报告字段缺失          | `generate_position_report` 返回部分字段 | 下游 `.get()` 安全取值，缺什么 prompt 回退什么           | 无感                     |
| 工具返回非法 JSON     | 解析失败                                | LLM 看到错误后决策跳过                                   | 无感                     |

**核心不变量**：MCP 端任何故障都不能阻断 Prepare 完成；用户始终能拿到出题结果。

---

## 九、Trace 与可视化

multi 现有 trace 基础设施已经支持节点级流转展示（前端 trace panel）。本期新增**工具级 trace**：

### 9.1 SSE 事件类型补充

在现有 `node_start` / `node_token` / `node_done` 基础上，research_agent 内部新增：

- `tool_thinking` — LLM 在 think，流式输出推理内容
- `tool_call_start` — 即将调用某个 MCP 工具，附带工具名 + 入参摘要
- `tool_call_done` — 工具返回，附带返回数据摘要 + 耗时

### 9.2 前端展示

trace panel 中 `research_agent` 节点展开后形如：

```
[research_agent] 调研中...
  ├ think: 用户给了 JD 文本和简历摘要，先把 JD 嚼结构化
  ├ tool: extract_jd_text(...) → {company:"字节",title:"国际化前端"} (1.2s)
  ├ think: 字节国际化团队我不熟，搜一下背景
  ├ tool: web_search("字节 飞书 国际化团队") → [5 条结果] (3.5s)
  ├ think: 信息够了，可以生成报告
  ├ tool: generate_position_report(...) → {6 模块} (18.1s)
  └ done (3 iterations, 23s)
```

### 9.3 演示价值

这个面板是本期的核心展示产物——直观证明：

1. multi 通过 MCP 协议接入了**另一个独立 Agent 系统**
2. 接入后这些工具是**Agent 自主决策调用**的，不是硬编码
3. 整个决策过程对用户可见

---

## 十、验收口径

### 10.1 功能验收

- [ ] job-intel MCP server 能独立启动、监听 9001 端口、`http://localhost:9001/mcp` 返回工具列表
- [ ] multi 启动期成功建立 MCP 连接，缓存到至少 4 个工具（必选工具）
- [ ] 用户在前端启动备课（提供 JD 文本），research_agent 节点能跑通完整 ReAct loop
- [ ] research_agent 与 memory_search 真正并行（trace 显示两者时间重叠）
- [ ] 最终 PrepareState["job_intel"] 包含 4 个必选模块（job_interpretation / resume_match / company_profile / prep_suggestions）
- [ ] Designer 出题 prompt 能引用 `hard_requirements`（日志可验证）
- [ ] Coach 反馈 prompt 能引用 `resume_match.gaps`（日志可验证）

### 10.2 降级验收

- [ ] MCP server 不启动时，multi 端 Prepare 流程仍能完成（走 jd_analysis 路径）
- [ ] research_agent 超时（人工 mock 一个 60s 卡死工具）时，Prepare 在 90s 内结束并兜底
- [ ] 不提供 jd_raw 也不提供 jd_url 时，Supervisor 跳过 research_agent，走 jd_analysis

### 10.3 Trace 验收

- [ ] 前端 trace panel 能展示 research_agent 节点
- [ ] 展开后能看到 think → tool_call → observe 三类事件
- [ ] 工具调用名称 + 耗时清晰可见

### 10.4 非验收范围（本期不做）

- 用户审核 / 修改备课笔记的 HIL 流程
- research_agent 工具调用结果回流 job-intel 数据库
- 跨 session 长期记忆中包含 `job_intel`
- 在 Interviewer chief 上挂任何 job-intel 工具
- job-intel MCP 工具的鉴权（本期 localhost 信任）

---

## 十一、未来演化路径

| 阶段       | 业务能力                                           | 触发条件             |
| ---------- | -------------------------------------------------- | -------------------- |
| V1（本期） | 备课时拿一份岗位情报，写入 State 整场复用          | 第一版上线           |
| V2         | 备课笔记可在前端编辑，候选人审核后再开始面试       | 用户反馈调研结果有误 |
| V3         | 面试结果回流 job-intel：标记情报里哪些点被实战验证 | 多场面试数据积累     |
| V4         | 同一公司多次面试，job-intel 提供"版本化"演化情报   | 用户重复练同一目标   |

---

## 十二、文件改动清单（实现期参考）

### job-intel-agent 仓库

新增：

- `backend/app/mcp_server.py` — MCP server 入口
- `backend/pyproject.toml` — 加 `mcp[cli]` 依赖
- `dev.sh` — 启动行追加

### multi-agent-coach 仓库

新增：

- `backend/app/services/mcp_client.py` — MCP client 单例
- `backend/app/agents/prepare/research_agent.py` — research_agent 节点实现（ReAct loop）

修改：

- `backend/pyproject.toml` — 加 `langchain-mcp-adapters` 依赖
- `backend/app/agents/prepare/state.py` — `PrepareState` 加 `job_intel` 字段、新增 `JobIntel` TypedDict
- `backend/app/agents/prepare/graph.py` — 注册 research_agent 节点 + Supervisor fan-out 边
- `backend/app/agents/prepare/nodes.py` — Supervisor 决策逻辑升级（fan-out + 汇合）
- `backend/app/agents/prepare/prompts.py` — Supervisor prompt 加 research_agent 决策规则
- `backend/app/agents/interviewer/state.py` — `InterviewState` 加 `job_intel` 字段
- `backend/app/agents/interviewer/chief_prompts.py` — 注入 `company_profile` 到 persona
- `backend/app/agents/designer/prompts.py` — 出题 prompt 消费 `hard_requirements` / `resume_match`
- `backend/app/agents/evaluator/prompts.py` — 评分 prompt 消费 `hard_requirements`
- `backend/app/agents/coach/prompts.py` — 反馈 prompt 消费 `gaps` / `prep_suggestions`
- `backend/.env.example` — 新增 `MCP_JOB_INTEL_URL`

测试：

- `backend/tests/unit/test_research_agent.py` — research_agent ReAct loop 单测
- `backend/tests/unit/test_mcp_client.py` — MCP client 连接/降级单测
- `backend/tests/integration/test_prepare_with_mcp.py` — Prepare 端到端集成测试

### 实现期分支

- 切 `feature/research-agent-mcp` 新分支
- 先处理 `main` 上的 3 个 WIP（commit 或 stash）
- 实现按"先 job-intel MCP server → 再 multi MCP client → 再 research_agent 节点 → 最后下游消费"顺序，每步可独立验证

---

## 十三、面试可讲性

本设计在面试讲故事时的几个关键卖点：

1. **MCP 作为 Agent-to-Agent 协议**：MCP 不只用于 LLM Client 接入工具，**两个独立 Agent 系统之间**也能通过 MCP 通信——展示对协议本质的理解
2. **工具思考与硬编码的边界**：明确区分"包接口成 MCP（RPC）"和"Agent 自主调度 MCP 工具（工具思考）"两种模式，并选择后者
3. **并行调度**：memory_search（内查）与 research_agent（外调 ReAct）并行，体现多 Agent 系统的并发编排能力
4. **决策粒度的取舍**：6 模块报告里只用 4 块、砍掉 2 块（interview_qa / salary_range），体现"知道 LLM 编的什么能用、什么不能用"的判断力
5. **降级路径**：MCP 不可用时自动回退，体现外部依赖不应该是单点的工程思考
6. **State 一次写多处读**：Prepare 写一次，下游 4 个 Agent 各取所需，体现"状态机思维"
