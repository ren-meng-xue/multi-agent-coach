# Research Agent + Job-Intel MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 multi-agent-coach 的 Prepare 阶段新增 `research_agent`（ReAct sub-agent），通过 MCP 协议接入 job-intel-agent 的 6 个工具，并行 `memory_search`，把"目标岗位情报"写入 State 供下游所有 Agent 复用。

**Architecture:** job-intel 侧新增独立 MCP server（FastMCP, streamable HTTP），暴露 4 必选 + 2 可选工具；multi 侧用 `langchain-mcp-adapters` 拉到工具列表，在 Prepare 阶段新增 `research_agent` 节点（ReAct loop, bind_tools, max 6 iter / 90s），与 `memory_search` 并行；6 模块报告里只用 4 块（砍 `interview_qa` / `salary_range`），写到 `PrepareState["job_intel"]`，跨阶段透传到 Designer / Evaluator / Coach / Interviewer。

**Tech Stack:** Python 3.12 / FastAPI / LangGraph / LangChain / `mcp[cli]` SDK (FastMCP) / `langchain-mcp-adapters` / pytest / uv

**Spec 文档:** `docs/superpowers/specs/2026-06-03-research-agent-mcp-design.md`

---

## File Structure

### 仓库 A：job-intel-agent

| 操作   | 路径                                           | 职责                               |
| ------ | ---------------------------------------------- | ---------------------------------- |
| Create | `backend/app/mcp_server.py`                    | FastMCP server 入口，注册 6 个工具 |
| Create | `backend/tests/unit/test_mcp_server.py`        | 工具注册与返回 schema 单测         |
| Create | `docs/specs/2026-06-03-mcp-server-contract.md` | 精简接口契约文档                   |
| Modify | `backend/pyproject.toml`                       | 加 `mcp[cli]>=1.0.0`               |
| Modify | `dev.sh`                                       | 追加 MCP server 启动行             |

### 仓库 B：multi-agent-coach

| 操作   | 路径                                                 | 职责                                                              |
| ------ | ---------------------------------------------------- | ----------------------------------------------------------------- |
| Create | `backend/app/services/mcp_client.py`                 | MCP client 单例，含重试 / 缓存 / 降级                             |
| Create | `backend/app/agents/prepare/research_agent.py`       | research_agent ReAct loop 节点                                    |
| Create | `backend/app/agents/prepare/research_prompts.py`     | research_agent 系统提示词                                         |
| Create | `backend/tests/unit/test_mcp_client.py`              | mcp_client 连接 / 重试 / 失败降级                                 |
| Create | `backend/tests/unit/test_research_agent.py`          | research_agent ReAct loop（mock tools）                           |
| Create | `backend/tests/integration/test_prepare_with_mcp.py` | Prepare 端到端 + MCP                                              |
| Modify | `backend/pyproject.toml`                             | 加 `langchain-mcp-adapters>=0.1.0`                                |
| Modify | `backend/.env.example`                               | 加 `MCP_JOB_INTEL_URL` / `MCP_JOB_INTEL_TIMEOUT_SECONDS`          |
| Modify | `backend/app/core/config.py`                         | Settings 加 `mcp_job_intel_url` / `mcp_job_intel_timeout_seconds` |
| Modify | `backend/app/agents/prepare/state.py`                | 加 `JobIntel` TypedDict 与 `job_intel` 字段                       |
| Modify | `backend/app/agents/prepare/nodes.py`                | Supervisor 决策加 `intel` 分支 + 路由逻辑                         |
| Modify | `backend/app/agents/prepare/prompts.py`              | Supervisor prompt 加 research_agent 决策规则                      |
| Modify | `backend/app/agents/prepare/graph.py`                | 注册 `research_agent` 节点 + 并行边                               |
| Modify | `backend/app/agents/interviewer/state.py`            | InterviewState 加 `job_intel` 字段                                |
| Modify | `backend/app/agents/interviewer/chief_prompts.py`    | 注入 `company_profile` 到 persona                                 |
| Modify | `backend/app/agents/designer/prompts.py`             | 消费 `job_interpretation` + `resume_match`                        |
| Modify | `backend/app/agents/evaluator/prompts.py`            | 消费 `hard_requirements` 当评分维度                               |
| Modify | `backend/app/agents/coach/prompts.py`                | 消费 `gaps` + `prep_suggestions`                                  |

---

## Phase 0 — 接口契约

### Task 1: job-intel 仓库新增接口契约文档

**Repository:** job-intel-agent

**Files:**

- Create: `docs/specs/2026-06-03-mcp-server-contract.md`

- [ ] **Step 1: 在 job-intel 仓库切分支**

```bash
cd /Users/xuebao/learn/AI项目/job-intel-agent
git status   # 确认工作区干净；如有 WIP 先 stash 或 commit
git checkout -b feature/mcp-server
```

- [ ] **Step 2: 写契约文档**

创建 `docs/specs/2026-06-03-mcp-server-contract.md`：

```markdown
# job-intel MCP Server 接口契约

- 日期：2026-06-03
- 消费方：multi-agent-coach 的 Prepare 阶段 research_agent
- 主设计文档：multi-agent-coach 仓库 `docs/superpowers/specs/2026-06-03-research-agent-mcp-design.md`

## 本期对外承诺

新增独立 ASGI 进程作为 MCP server，复用现有 service 函数，让外部 Agent 系统能在自己的工具思考循环中调用 job-intel 的能力。

## 工具清单

### 必选

| 工具                       | 入参                                                                                                                  | 出参                                                                              | 底层调用                            |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- | ----------------------------------- |
| `extract_jd_text`          | `text: str`                                                                                                           | `{title, company, requirements[], jd_summary, salary_range, location, work_type}` | `llm_service.extract_job_info`      |
| `web_search`               | `query: str, max_results: int = 5`                                                                                    | `[{title, url, content}]`                                                         | `search_service.search`             |
| `analyze_position`         | `title, company, jd_summary, requirements[], search_results: dict, resume_content?: str`                              | `analysis: str (300-500 字)`                                                      | `graphs/nodes.analyze_node`         |
| `generate_position_report` | `title, company, jd_summary, requirements[], search_results: dict, directions[], resume_content?, research_analysis?` | 6 模块 JSON                                                                       | `graphs/nodes.generate_report_node` |

### 可选

| 工具             | 入参               | 出参                                                  | 底层调用                          |
| ---------------- | ------------------ | ----------------------------------------------------- | --------------------------------- |
| `scrape_jd_url`  | `url: str`         | `markdown: str`                                       | `crawler_service.scrape_url`      |
| `extract_resume` | `raw_content: str` | `{summary, skills[], work_experience[], education[]}` | `llm_service.extract_resume_info` |

## 启动方式

- 命令：`uv run python -m app.mcp_server`
- 传输：streamable HTTP
- 监听：`host="::"`（IPv6，Railway 私网必需）+ `port=$PORT`（本地默认 9001）

## SLA

- 单工具超时：30s
- 异常返回：JSON-RPC error
- 不写 DB、无状态、不鉴权（V1 仅 localhost / Railway 私网信任）

## 文件改动

- 新增：`backend/app/mcp_server.py` / `backend/tests/unit/test_mcp_server.py`
- 修改：`backend/pyproject.toml` 加 `mcp[cli]` / `dev.sh` 加启动行
```

- [ ] **Step 3: commit**

```bash
git add docs/specs/2026-06-03-mcp-server-contract.md
git commit -m "docs(spec): job-intel MCP server 接口契约（消费方 multi-coach）"
```

---

## Phase 1 — job-intel MCP Server

### Task 2: 加 mcp 依赖 + server 骨架（boots, 无工具）

**Repository:** job-intel-agent

**Files:**

- Create: `backend/app/mcp_server.py`
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: 加依赖**

修改 `backend/pyproject.toml`，在现有 `dependencies` 列表里追加：

```toml
"mcp[cli]>=1.0.0",
```

- [ ] **Step 2: 安装**

```bash
cd backend
uv sync
```

预期：mcp 包被装上，无报错。

- [ ] **Step 3: 写最小骨架 server**

创建 `backend/app/mcp_server.py`：

```python
"""Job-Intel MCP Server — 让外部 Agent 系统能调用本项目的能力。

V1 暴露 4 必选 + 2 可选工具，复用现有 service 函数，无状态、不写 DB。
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="job-intel",
    host=os.getenv("MCP_HOST", "::"),       # IPv6，兼容 Railway 私网
    port=int(os.getenv("PORT", "9001")),
)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

- [ ] **Step 4: 手动 smoke：能启动**

```bash
cd backend
uv run python -m app.mcp_server
```

预期：进程启动，监听 9001 端口，无报错。**Ctrl+C 停掉**。

- [ ] **Step 5: commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/mcp_server.py
git commit -m "feat(mcp): job-intel MCP server 骨架（FastMCP, streamable HTTP, IPv6）"
```

---

### Task 3: 工具 `extract_jd_text`（TDD）

**Repository:** job-intel-agent

**Files:**

- Modify: `backend/app/mcp_server.py`
- Create: `backend/tests/unit/test_mcp_server.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/unit/test_mcp_server.py`：

```python
"""MCP server 工具单元测试 — 验证注册、调用、返回 schema。"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_extract_jd_text_returns_structured():
    """extract_jd_text 工具应调用 extract_job_info 并返回结构化字段。"""
    from app.mcp_server import extract_jd_text
    from app.schemas.job import ExtractedJobInfo

    fake = ExtractedJobInfo(
        title="后端工程师",
        company="字节",
        requirements=["3年经验", "Python"],
        jd_summary="负责核心业务",
        salary_range="25k-50k",
        location="北京",
        work_type="onsite",
    )

    with patch(
        "app.services.llm_service.extract_job_info",
        new_callable=AsyncMock,
        return_value=fake,
    ):
        result = await extract_jd_text("某 JD 文本")

    assert result["title"] == "后端工程师"
    assert result["company"] == "字节"
    assert result["requirements"] == ["3年经验", "Python"]
    assert result["work_type"] == "onsite"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend
uv run pytest tests/unit/test_mcp_server.py::test_extract_jd_text_returns_structured -v
```

预期：FAIL（`ImportError: cannot import name 'extract_jd_text'`）

- [ ] **Step 3: 在 mcp_server.py 加工具**

修改 `backend/app/mcp_server.py`，在 `mcp = FastMCP(...)` 之后、`if __name__` 之前追加：

```python
from app.services.llm_service import extract_job_info as _extract_job_info


@mcp.tool()
async def extract_jd_text(text: str) -> dict:
    """把 JD 文本变结构化字段。输入：JD 原文；输出：title / company / requirements / jd_summary / salary_range / location / work_type。"""
    info = await _extract_job_info(text)
    return {
        "title": info.title,
        "company": info.company,
        "requirements": info.requirements,
        "jd_summary": info.jd_summary,
        "salary_range": info.salary_range,
        "location": info.location,
        "work_type": info.work_type,
    }
```

- [ ] **Step 4: 跑测试确认通过**

```bash
uv run pytest tests/unit/test_mcp_server.py::test_extract_jd_text_returns_structured -v
```

预期：PASS

- [ ] **Step 5: commit**

```bash
git add backend/app/mcp_server.py backend/tests/unit/test_mcp_server.py
git commit -m "feat(mcp): 工具 extract_jd_text 暴露 JD 文本结构化能力"
```

---

### Task 4: 工具 `web_search`（TDD）

**Repository:** job-intel-agent

**Files:**

- Modify: `backend/app/mcp_server.py`
- Modify: `backend/tests/unit/test_mcp_server.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/unit/test_mcp_server.py` 追加：

```python
@pytest.mark.asyncio
async def test_web_search_returns_results():
    """web_search 透传 Tavily 结果。"""
    from app.mcp_server import web_search

    fake_results = [
        {"title": "字节技术博客", "url": "https://example.com", "content": "摘要"},
    ]

    with patch(
        "app.services.search_service.search",
        new_callable=AsyncMock,
        return_value=fake_results,
    ):
        result = await web_search("字节 后端 技术栈", max_results=3)

    assert result == fake_results
```

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run pytest tests/unit/test_mcp_server.py::test_web_search_returns_results -v
```

预期：FAIL（`ImportError: cannot import name 'web_search'`）

- [ ] **Step 3: 加工具**

在 `mcp_server.py` 追加：

```python
from app.services.search_service import search as _search


@mcp.tool()
async def web_search(query: str, max_results: int = 5) -> list[dict]:
    """联网搜索目标公司/岗位背景。返回 [{title, url, content}] 列表。"""
    return await _search(query, max_results=max_results)
```

- [ ] **Step 4: 跑测试**

```bash
uv run pytest tests/unit/test_mcp_server.py::test_web_search_returns_results -v
```

预期：PASS

- [ ] **Step 5: commit**

```bash
git add backend/app/mcp_server.py backend/tests/unit/test_mcp_server.py
git commit -m "feat(mcp): 工具 web_search 透传 Tavily 联网搜索"
```

---

### Task 5: 工具 `analyze_position`（TDD）

**Repository:** job-intel-agent

**Files:**

- Modify: `backend/app/mcp_server.py`
- Modify: `backend/tests/unit/test_mcp_server.py`

- [ ] **Step 1: 写失败测试**

在测试文件追加：

```python
@pytest.mark.asyncio
async def test_analyze_position_returns_summary():
    """analyze_position 调底层 analyze_node，返回 300-500 字分析。"""
    from app.mcp_server import analyze_position

    fake_node_result = {
        "research_analysis": "字节国际化团队近期在做飞书出海，技术栈以 React + Node.js 为主...",
        "current_step": "review_results",
    }

    with patch(
        "app.graphs.nodes.analyze_node",
        new_callable=AsyncMock,
        return_value=fake_node_result,
    ):
        result = await analyze_position(
            title="国际化前端",
            company="字节",
            jd_summary="负责飞书海外版",
            requirements=["3年 React"],
            search_results={"技术栈": [{"title": "blog", "content": "..."}]},
            resume_content=None,
        )

    assert "国际化团队" in result
    assert isinstance(result, str)
```

- [ ] **Step 2: 跑测试**

```bash
uv run pytest tests/unit/test_mcp_server.py::test_analyze_position_returns_summary -v
```

预期：FAIL

- [ ] **Step 3: 加工具**

在 `mcp_server.py` 追加：

```python
from app.graphs.nodes import analyze_node as _analyze_node


@mcp.tool()
async def analyze_position(
    title: str,
    company: str,
    jd_summary: str,
    requirements: list[str],
    search_results: dict,
    resume_content: str | None = None,
) -> str:
    """综合 JD + 搜索结果 + 简历，产出 300-500 字分析摘要。"""
    state = {
        "title": title,
        "company": company,
        "jd_summary": jd_summary,
        "requirements": requirements,
        "search_results": search_results,
        "resume_content": resume_content,
        "human_feedback": [],
    }
    result = await _analyze_node(state)
    return result["research_analysis"]
```

- [ ] **Step 4: 跑测试**

```bash
uv run pytest tests/unit/test_mcp_server.py::test_analyze_position_returns_summary -v
```

预期：PASS

- [ ] **Step 5: commit**

```bash
git add backend/app/mcp_server.py backend/tests/unit/test_mcp_server.py
git commit -m "feat(mcp): 工具 analyze_position 调用底层 analyze_node 产出综合分析"
```

---

### Task 6: 工具 `generate_position_report`（TDD）

**Repository:** job-intel-agent

**Files:**

- Modify: `backend/app/mcp_server.py`
- Modify: `backend/tests/unit/test_mcp_server.py`

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.asyncio
async def test_generate_position_report_returns_six_modules():
    """generate_position_report 调底层 generate_report_node，返回 6 模块 JSON。"""
    from app.mcp_server import generate_position_report

    fake_node_result = {
        "report_data": {
            "job_interpretation": {"hard_requirements": ["Python"], "soft_requirements": [], "hidden_bonuses": [], "summary": ""},
            "resume_match": {"strengths": ["Python 经验"], "gaps": ["缺分布式"]},
            "company_profile": {"summary": "字节国际化团队", "tags": ["极客", "快节奏"]},
            "interview_qa": [{"question": "Q1", "tip": "T1"}],
            "salary_range": {"market_min": 25000, "market_max": 50000, "median": 35000, "suggested_min": 30000, "suggested_max": 45000},
            "prep_suggestions": [{"title": "3天补分布式", "content": "看 DDIA"}],
        },
        "current_step": "review_draft",
    }

    with patch(
        "app.graphs.nodes.generate_report_node",
        new_callable=AsyncMock,
        return_value=fake_node_result,
    ):
        result = await generate_position_report(
            title="后端", company="字节",
            jd_summary="...", requirements=["Python"],
            search_results={"技术栈": []},
            directions=["技术栈"],
            resume_content="3 年 Python",
            research_analysis="...",
        )

    assert "job_interpretation" in result
    assert "resume_match" in result
    assert "company_profile" in result
    assert "interview_qa" in result
    assert "salary_range" in result
    assert "prep_suggestions" in result
    assert result["resume_match"]["gaps"] == ["缺分布式"]
```

- [ ] **Step 2: 跑测试**

```bash
uv run pytest tests/unit/test_mcp_server.py::test_generate_position_report_returns_six_modules -v
```

预期：FAIL

- [ ] **Step 3: 加工具**

```python
from app.graphs.nodes import generate_report_node as _generate_report_node


@mcp.tool()
async def generate_position_report(
    title: str,
    company: str,
    jd_summary: str,
    requirements: list[str],
    search_results: dict,
    directions: list[str],
    resume_content: str | None = None,
    research_analysis: str | None = None,
    salary_range: str | None = None,
    location: str | None = None,
    work_type: str | None = None,
) -> dict:
    """综合所有素材，产出 6 模块结构化情报报告。"""
    state = {
        "title": title,
        "company": company,
        "jd_summary": jd_summary,
        "requirements": requirements,
        "search_results": search_results,
        "selected_directions": directions,
        "resume_content": resume_content,
        "research_analysis": research_analysis or "",
        "salary_range": salary_range,
        "location": location,
        "work_type": work_type,
        "human_feedback": [],
    }
    result = await _generate_report_node(state)
    return result.get("report_data") or {}
```

- [ ] **Step 4: 跑测试**

```bash
uv run pytest tests/unit/test_mcp_server.py::test_generate_position_report_returns_six_modules -v
```

预期：PASS

- [ ] **Step 5: commit**

```bash
git add backend/app/mcp_server.py backend/tests/unit/test_mcp_server.py
git commit -m "feat(mcp): 工具 generate_position_report 产出 6 模块完整报告"
```

---

### Task 7: 可选工具 `scrape_jd_url` + `extract_resume`

**Repository:** job-intel-agent

**Files:**

- Modify: `backend/app/mcp_server.py`
- Modify: `backend/tests/unit/test_mcp_server.py`

- [ ] **Step 1: 写两个失败测试**

```python
@pytest.mark.asyncio
async def test_scrape_jd_url_returns_markdown():
    """scrape_jd_url 透传 Firecrawl 抓取结果。"""
    from app.mcp_server import scrape_jd_url

    with patch(
        "app.services.crawler_service.scrape_url",
        new_callable=AsyncMock,
        return_value="# 字节 后端工程师\n\n## 职责\n...",
    ):
        result = await scrape_jd_url("https://example.com/job/123")

    assert "字节" in result
    assert "职责" in result


@pytest.mark.asyncio
async def test_extract_resume_returns_structured():
    """extract_resume 透传 LLM 简历解析结果。"""
    from app.mcp_server import extract_resume

    fake = {
        "summary": "3 年 Python 后端",
        "skills": ["Python", "FastAPI"],
        "work_experience": [{"company": "X", "title": "后端", "duration": "2022-2024"}],
        "education": [{"school": "Y", "degree": "本科", "major": "CS"}],
    }

    with patch(
        "app.services.llm_service.extract_resume_info",
        new_callable=AsyncMock,
        return_value=fake,
    ):
        result = await extract_resume("简历原文...")

    assert result["summary"] == "3 年 Python 后端"
    assert result["skills"] == ["Python", "FastAPI"]
```

- [ ] **Step 2: 跑测试**

```bash
uv run pytest tests/unit/test_mcp_server.py -k "scrape_jd_url or extract_resume" -v
```

预期：两条 FAIL

- [ ] **Step 3: 加两个工具**

```python
from app.services.crawler_service import scrape_url as _scrape_url
from app.services.llm_service import extract_resume_info as _extract_resume_info


@mcp.tool()
async def scrape_jd_url(url: str) -> str:
    """抓取 JD 网页正文 markdown。Firecrawl 失败会抛错。"""
    return await _scrape_url(url)


@mcp.tool()
async def extract_resume(raw_content: str) -> dict:
    """简历原文结构化。返回 {summary, skills[], work_experience[], education[]}。"""
    return await _extract_resume_info(raw_content)
```

- [ ] **Step 4: 跑测试**

```bash
uv run pytest tests/unit/test_mcp_server.py -k "scrape_jd_url or extract_resume" -v
```

预期：两条 PASS

- [ ] **Step 5: 跑全部 mcp_server 测试**

```bash
uv run pytest tests/unit/test_mcp_server.py -v
```

预期：6 条全部 PASS

- [ ] **Step 6: commit**

```bash
git add backend/app/mcp_server.py backend/tests/unit/test_mcp_server.py
git commit -m "feat(mcp): 可选工具 scrape_jd_url 与 extract_resume"
```

---

### Task 8: dev.sh 集成 + 端到端 smoke

**Repository:** job-intel-agent

**Files:**

- Modify: `dev.sh`

- [ ] **Step 1: 看 dev.sh 当前格式**

```bash
cd /Users/xuebao/learn/AI项目/job-intel-agent
cat dev.sh
```

留意现有 backend / celery 启动行的语法，仿照它追加。

- [ ] **Step 2: 加 MCP server 启动行**

在 dev.sh 里 backend 启动行之后追加（保持 & 后台、保持日志重定向风格）：

```bash
echo "Starting job-intel MCP server on :9001..."
(cd backend && uv run python -m app.mcp_server) > mcp.log 2>&1 &
MCP_PID=$!
echo "  MCP PID: $MCP_PID"
```

- [ ] **Step 3: 启动 dev.sh 端到端 smoke**

```bash
./dev.sh
```

观察：

- 3 个进程都起来（backend + celery + mcp + frontend）
- `mcp.log` 没有 traceback
- 用 `curl` 验证 MCP server 在监听：

```bash
curl -s http://localhost:9001/mcp -H "Accept: application/json,text/event-stream"
```

预期：返回 MCP 协议响应（不是 connection refused）

- [ ] **Step 4: 停止 dev.sh**

```bash
# Ctrl+C 或者
pkill -f "app.mcp_server"
```

- [ ] **Step 5: commit + 推送 job-intel 分支**

```bash
git add dev.sh
git commit -m "feat(dev): dev.sh 启动 MCP server on :9001"
git push -u origin feature/mcp-server
```

到此 **job-intel 侧改动全部完成**。后续不再切回此仓库。

---

## Phase 2 — multi MCP Client

### Task 9: multi 加依赖 + config + .env

**Repository:** multi-agent-coach

**Files:**

- Modify: `backend/pyproject.toml`
- Modify: `backend/.env.example`
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: 加依赖**

修改 `backend/pyproject.toml`，在 `dependencies` 列表追加：

```toml
"langchain-mcp-adapters>=0.1.0",
```

- [ ] **Step 2: 安装**

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach/backend
uv sync
```

预期：装上 `langchain-mcp-adapters` 及其依赖（包括 `mcp` SDK），无错。

- [ ] **Step 3: 加 .env.example 字段**

修改 `backend/.env.example`，文件末尾追加：

```
# job-intel MCP server（Prepare 阶段 research_agent 使用）
MCP_JOB_INTEL_URL=http://localhost:9001/mcp
MCP_JOB_INTEL_TIMEOUT_SECONDS=90
```

- [ ] **Step 4: 加 Settings 字段**

打开 `backend/app/core/config.py`，在 Settings 类里找到现有字段（如 `openai_api_key`），同位置追加：

```python
    mcp_job_intel_url: str = "http://localhost:9001/mcp"
    mcp_job_intel_timeout_seconds: int = 90
```

- [ ] **Step 5: commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/.env.example backend/app/core/config.py
git commit -m "feat(mcp): 加 langchain-mcp-adapters 依赖与 MCP_JOB_INTEL 配置"
```

---

### Task 10: 写 `mcp_client.py` 单例 + 测试

**Repository:** multi-agent-coach

**Files:**

- Create: `backend/app/services/mcp_client.py`
- Create: `backend/tests/unit/test_mcp_client.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/unit/test_mcp_client.py`：

```python
"""MCP client 单例 / 重试 / 降级测试。"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_mcp_tools_caches_after_first_call():
    """get_mcp_tools 应只建立一次连接，第二次直接拿缓存。"""
    from app.services import mcp_client

    # 复位模块级缓存
    mcp_client._tools_cache = None
    mcp_client._client = None

    fake_tool = MagicMock(name="extract_jd_text")
    fake_tool.name = "extract_jd_text"

    mock_client = MagicMock()
    mock_client.get_tools = AsyncMock(return_value=[fake_tool])

    with patch(
        "app.services.mcp_client.MultiServerMCPClient",
        return_value=mock_client,
    ) as mock_ctor:
        t1 = await mcp_client.get_mcp_tools()
        t2 = await mcp_client.get_mcp_tools()

    assert t1 == [fake_tool]
    assert t2 == [fake_tool]
    mock_ctor.assert_called_once()                 # 构造一次
    mock_client.get_tools.assert_awaited_once()    # get_tools 一次


@pytest.mark.asyncio
async def test_get_mcp_tools_returns_empty_when_connection_fails():
    """连接失败时返回空列表，让上游降级，不抛异常。"""
    from app.services import mcp_client

    mcp_client._tools_cache = None
    mcp_client._client = None

    mock_client = MagicMock()
    mock_client.get_tools = AsyncMock(side_effect=ConnectionError("refused"))

    with patch(
        "app.services.mcp_client.MultiServerMCPClient",
        return_value=mock_client,
    ):
        result = await mcp_client.get_mcp_tools()

    assert result == []


@pytest.mark.asyncio
async def test_get_tool_by_name_finds_target():
    """get_tool 按名字找到具体工具。"""
    from app.services import mcp_client

    mcp_client._tools_cache = None
    mcp_client._client = None

    t1 = MagicMock(); t1.name = "extract_jd_text"
    t2 = MagicMock(); t2.name = "web_search"

    mock_client = MagicMock()
    mock_client.get_tools = AsyncMock(return_value=[t1, t2])

    with patch(
        "app.services.mcp_client.MultiServerMCPClient",
        return_value=mock_client,
    ):
        result = await mcp_client.get_tool("web_search")

    assert result is t2


@pytest.mark.asyncio
async def test_get_tool_returns_none_when_not_found():
    """工具不存在时返回 None，不抛异常。"""
    from app.services import mcp_client

    mcp_client._tools_cache = None
    mcp_client._client = None

    t1 = MagicMock(); t1.name = "extract_jd_text"
    mock_client = MagicMock()
    mock_client.get_tools = AsyncMock(return_value=[t1])

    with patch(
        "app.services.mcp_client.MultiServerMCPClient",
        return_value=mock_client,
    ):
        result = await mcp_client.get_tool("nonexistent")

    assert result is None
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend
uv run pytest tests/unit/test_mcp_client.py -v
```

预期：4 条全部 FAIL（`ImportError: No module named 'app.services.mcp_client'`）

- [ ] **Step 3: 写实现**

创建 `backend/app/services/mcp_client.py`：

```python
"""MCP client 单例：连接 job-intel MCP server，缓存工具列表，失败时优雅降级。

设计要点：
- 进程级单例，启动期一次建立连接，跨节点复用
- 失败不抛异常（连接失败返回空列表），让上游 Supervisor 走降级路径
- 缓存工具列表，避免每次工具查找都重新拉取
"""
from __future__ import annotations

from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("app.services.mcp_client")

_client: MultiServerMCPClient | None = None
_tools_cache: list[Any] | None = None


async def get_mcp_tools() -> list[Any]:
    """返回 LangChain BaseTool 列表（已封装 job-intel MCP server 的工具）。

    首次调用建立连接 + 拉取工具，后续调用走缓存。
    连接失败返回空列表（不抛异常），让 Supervisor 走 jd_analysis 兜底。
    """
    global _client, _tools_cache
    if _tools_cache is not None:
        return _tools_cache

    settings = get_settings()
    try:
        _client = MultiServerMCPClient({
            "job_intel": {
                "url": settings.mcp_job_intel_url,
                "transport": "streamable_http",
            }
        })
        _tools_cache = await _client.get_tools()
        log.info(
            "mcp_tools_loaded",
            url=settings.mcp_job_intel_url,
            count=len(_tools_cache),
            names=[t.name for t in _tools_cache],
        )
    except Exception as exc:
        log.warning(
            "mcp_connection_failed_fallback",
            url=settings.mcp_job_intel_url,
            error=str(exc),
        )
        _tools_cache = []
        _client = None

    return _tools_cache


async def get_tool(name: str) -> Any | None:
    """按名字找单个工具；找不到返回 None。"""
    tools = await get_mcp_tools()
    for t in tools:
        if t.name == name:
            return t
    return None


def reset_cache() -> None:
    """测试用：清空缓存。"""
    global _client, _tools_cache
    _client = None
    _tools_cache = None
```

- [ ] **Step 4: 跑测试确认通过**

```bash
uv run pytest tests/unit/test_mcp_client.py -v
```

预期：4 条全部 PASS

- [ ] **Step 5: commit**

```bash
git add backend/app/services/mcp_client.py backend/tests/unit/test_mcp_client.py
git commit -m "feat(mcp): mcp_client 单例 + 连接重试 + 失败降级"
```

---

### Task 11: 联通 smoke：multi → job-intel MCP

**Repository:** multi-agent-coach（手动验证，无代码改动）

- [ ] **Step 1: 启动 job-intel MCP server（另一个终端）**

```bash
cd /Users/xuebao/learn/AI项目/job-intel-agent/backend
uv run python -m app.mcp_server
```

确保监听 9001，无错。

- [ ] **Step 2: 在 multi 跑一个 ad-hoc Python smoke**

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach/backend
uv run python -c "
import asyncio
from app.services.mcp_client import get_mcp_tools

async def main():
    tools = await get_mcp_tools()
    print(f'Got {len(tools)} tools:')
    for t in tools:
        print(f'  - {t.name}: {t.description[:80]}')

asyncio.run(main())
"
```

预期输出：

```
Got 6 tools:
  - extract_jd_text: ...
  - web_search: ...
  - analyze_position: ...
  - generate_position_report: ...
  - scrape_jd_url: ...
  - extract_resume: ...
```

- [ ] **Step 3: 停掉 job-intel MCP（Ctrl+C）后再跑 smoke**

```bash
# 关掉 job-intel MCP
# 在 multi 终端再跑：
uv run python -c "
import asyncio
from app.services.mcp_client import get_mcp_tools, reset_cache

async def main():
    reset_cache()  # 清掉上次的缓存
    tools = await get_mcp_tools()
    print(f'Got {len(tools)} tools (degraded)')

asyncio.run(main())
"
```

预期：`Got 0 tools (degraded)`（无异常，优雅降级）

- [ ] **Step 4: 验证完成，无需 commit**

不修改任何文件。只是验证通道。

---

## Phase 3 — research_agent + State + Supervisor

### Task 12: 加 `JobIntel` TypedDict 到 PrepareState

**Repository:** multi-agent-coach

**Files:**

- Modify: `backend/app/agents/prepare/state.py`

- [ ] **Step 1: 看现有 PrepareState 结构**

```bash
cat backend/app/agents/prepare/state.py
```

确认 `JDContext` / `PreparedQuestion` / `PrepareState` 三个 TypedDict 的位置。

- [ ] **Step 2: 在 `PreparedQuestion` 之后插入 `JobIntel`**

打开 `backend/app/agents/prepare/state.py`，在 `PreparedQuestion` 定义之后追加：

```python
class JobIntel(TypedDict, total=False):
    """research_agent 写入：目标岗位的 6 模块情报（来自 job-intel MCP）。

    下游 Designer / Evaluator / Coach / Interviewer 各自读关心的字段。
    interview_qa / salary_range 保留为字段但下游不消费（避免 LLM 自循环和假数据）。
    """
    job_interpretation: dict
    resume_match: dict
    company_profile: dict
    interview_qa: list[dict]
    salary_range: dict
    prep_suggestions: list[dict]
    _trace: dict  # research_agent 过程产物：tools_used / iterations / elapsed_ms / final_thought
```

- [ ] **Step 3: 在 `PrepareState` 里加 `job_intel` 字段**

在 `PrepareState` 类的 "子 Agent 结果" 注释段内（与 `weak_areas`、`jd_context` 同层），追加：

```python
    job_intel: JobIntel | None    # research_agent 写入；MCP 不可用时为 None
```

- [ ] **Step 4: 验证 state 文件能 import 不报错**

```bash
uv run python -c "from app.agents.prepare.state import PrepareState, JobIntel; print('ok')"
```

预期：`ok`

- [ ] **Step 5: commit**

```bash
git add backend/app/agents/prepare/state.py
git commit -m "feat(prepare): PrepareState 加 JobIntel TypedDict 与 job_intel 字段"
```

---

### Task 13: InterviewState 加 `job_intel` 字段（跨阶段透传）

**Repository:** multi-agent-coach

**Files:**

- Modify: `backend/app/agents/interviewer/state.py`

- [ ] **Step 1: 看现有 InterviewState 字段**

```bash
grep -nE "class InterviewState|jd_context|prepared_questions" backend/app/agents/interviewer/state.py
```

- [ ] **Step 2: 加字段**

打开 `backend/app/agents/interviewer/state.py`，在 InterviewState 类里找到 `prepared_questions: list[dict[str, Any]]` 这一行，**之后**追加：

```python
    job_intel: dict | None         # 来自 PrepareState，跨阶段透传；MCP 不可用时为 None
```

类型用 `dict | None` 而不是 `JobIntel`，避免循环引用。

- [ ] **Step 3: 找 Prepare → Interview transition 处，加透传**

```bash
grep -rn "jd_context.*prepared_questions\|InterviewState" backend/app/services/ backend/app/api/ 2>/dev/null | grep -v __pycache__ | head -10
```

定位到把 PrepareState 转换为 InterviewState 的代码（通常在 `app/api/v1/interview.py` 或 `app/services/interview_*.py`）。

打开该文件，在构造 InterviewState 的字典字面量里加一行：

```python
        "job_intel": prepare_state.get("job_intel"),  # 把备课情报透传给整场面试
```

（具体变量名按当前文件调整。）

- [ ] **Step 4: 验证 import**

```bash
uv run python -c "from app.agents.interviewer.state import InterviewState; print('ok')"
```

预期：`ok`

- [ ] **Step 5: 跑现有 interviewer 测试确保没破**

```bash
uv run pytest tests/unit/test_interviewer*.py -v 2>&1 | tail -20
```

预期：现有测试全 PASS（job_intel 是新增可选字段，不影响旧用例）

- [ ] **Step 6: commit**

```bash
git add backend/app/agents/interviewer/state.py backend/app/api/v1/interview.py
git commit -m "feat(state): InterviewState 加 job_intel 字段，Prepare→Interview 透传"
```

---

### Task 14: 写 research_agent ReAct loop + prompt + 测试

**Repository:** multi-agent-coach

**Files:**

- Create: `backend/app/agents/prepare/research_prompts.py`
- Create: `backend/app/agents/prepare/research_agent.py`
- Create: `backend/tests/unit/test_research_agent.py`

- [ ] **Step 1: 写 research_agent system prompt**

创建 `backend/app/agents/prepare/research_prompts.py`：

```python
"""research_agent 系统提示词。"""

RESEARCH_AGENT_SYSTEM_PROMPT = """你是一位面试调研专员，正在帮一位候选人备课。
你的任务：用提供的工具，研究**目标岗位**（公司 + 职位），为候选人产出一份带针对性的备课情报。

## 你拥有的工具（来自 job-intel MCP）

- extract_jd_text(text)：把 JD 文本变结构化字段（公司、岗位、要求等）
- web_search(query)：联网搜公司背景 / 技术栈 / 团队文化
- analyze_position(...)：综合 JD + 搜索结果出 300-500 字分析
- generate_position_report(...)：最终生成 6 模块结构化报告
- scrape_jd_url(url)：从招聘网页抓 JD（用户给了 URL 时）
- extract_resume(text)：从简历原文提取结构化（候选人简历还未结构化时）

## 工作流程（你自己决策每一步）

1. 先看用户给了什么：JD 文本？URL？候选人简历摘要？
2. 用 extract_jd_text 把 JD 嚼结构化
3. 用 web_search 搜公司技术栈 / 团队 / 文化（搜 2-3 条不同方向的查询足够）
4. （可选）用 analyze_position 综合一下
5. **最后一定要**调 generate_position_report 产出最终 6 模块报告

## 决策原则

- 不要重复搜同一个 query
- 搜公司时 query 里带上"公司名 + 关键词"，比如 "字节 飞书 国际化团队"
- 信息够了就尽早调 generate_position_report 收尾，不要做不必要的额外搜索
- 最大调用次数 6，超过会被强制停

## 输出

最后一轮：调用 generate_position_report 拿到 6 模块报告，把它的 JSON 作为最终结果。
不需要写自然语言总结，工具返回值会自动保存。

## 候选人本次备课的上下文

{context}
"""
```

- [ ] **Step 2: 写失败测试**

创建 `backend/tests/unit/test_research_agent.py`：

```python
"""research_agent ReAct loop 单测（mock MCP 工具）。"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage


def _mock_tool(name: str, return_value):
    t = MagicMock()
    t.name = name
    t.ainvoke = AsyncMock(return_value=return_value)
    return t


@pytest.mark.asyncio
async def test_research_agent_writes_job_intel_on_success():
    """正常路径：LLM 决策调 extract_jd_text → web_search → generate_position_report，job_intel 被写入。"""
    from app.agents.prepare.research_agent import research_agent_node

    fake_report = {
        "job_interpretation": {"hard_requirements": ["Python"]},
        "resume_match": {"strengths": ["3 年经验"], "gaps": ["缺分布式"]},
        "company_profile": {"summary": "字节核心业务", "tags": ["快节奏"]},
        "interview_qa": [],
        "salary_range": {"median": 30000},
        "prep_suggestions": [{"title": "补分布式", "content": "看 DDIA"}],
    }

    mock_tools = [
        _mock_tool("extract_jd_text", {"title": "后端", "company": "字节", "requirements": ["Python"], "jd_summary": "...", "salary_range": None, "location": None, "work_type": None}),
        _mock_tool("web_search", [{"title": "blog", "url": "u", "content": "字节技术栈"}]),
        _mock_tool("generate_position_report", fake_report),
    ]

    # 第 1 轮 LLM 决策调 extract_jd_text
    msg1 = AIMessage(content="", tool_calls=[{"name": "extract_jd_text", "args": {"text": "JD..."}, "id": "c1"}])
    # 第 2 轮 LLM 决策调 web_search
    msg2 = AIMessage(content="", tool_calls=[{"name": "web_search", "args": {"query": "字节 后端"}, "id": "c2"}])
    # 第 3 轮 LLM 决策调 generate_position_report
    msg3 = AIMessage(content="", tool_calls=[{"name": "generate_position_report", "args": {"title": "后端", "company": "字节", "jd_summary": "...", "requirements": ["Python"], "search_results": {"general": []}, "directions": ["技术栈"]}, "id": "c3"}])
    # 第 4 轮 LLM 看到结果，不再调工具，结束
    msg4 = AIMessage(content="调研完成")

    mock_model = MagicMock()
    mock_model.bind_tools = MagicMock(return_value=mock_model)
    mock_model.ainvoke = AsyncMock(side_effect=[msg1, msg2, msg3, msg4])

    state = {
        "user_id": "u1",
        "user_direction": "AI Agent 工程师",
        "jd_raw": "字节后端 JD...",
        "user_background": "3 年 Python",
    }

    with (
        patch("app.agents.prepare.research_agent.get_mcp_tools", new_callable=AsyncMock, return_value=mock_tools),
        patch("app.agents.prepare.research_agent._chat_model", return_value=mock_model),
    ):
        result = await research_agent_node(state)

    assert result["job_intel"] is not None
    assert result["job_intel"]["resume_match"]["gaps"] == ["缺分布式"]
    assert "generate_position_report" in result["job_intel"]["_trace"]["tools_used"]
    assert "research_agent" in result.get("completed_tools", [])


@pytest.mark.asyncio
async def test_research_agent_returns_none_when_mcp_unavailable():
    """MCP 不可用（空工具列表）时，job_intel 为 None，让 Supervisor 走 jd_analysis 兜底。"""
    from app.agents.prepare.research_agent import research_agent_node

    state = {"user_id": "u1", "jd_raw": "JD..."}

    with patch(
        "app.agents.prepare.research_agent.get_mcp_tools",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await research_agent_node(state)

    assert result["job_intel"] is None
    assert "research_agent" in result["completed_tools"]


@pytest.mark.asyncio
async def test_research_agent_stops_at_max_iterations():
    """超过 max iterations 时强制兜底调 generate_position_report 收尾。"""
    from app.agents.prepare.research_agent import research_agent_node

    fake_report = {
        "job_interpretation": {}, "resume_match": {}, "company_profile": {},
        "interview_qa": [], "salary_range": {}, "prep_suggestions": [],
    }
    report_tool = _mock_tool("generate_position_report", fake_report)
    extract_tool = _mock_tool("extract_jd_text", {"title": "x", "company": "y", "requirements": [], "jd_summary": "", "salary_range": None, "location": None, "work_type": None})

    # LLM 死循环调 extract_jd_text，每轮都不调 generate_position_report
    loop_msg = AIMessage(content="", tool_calls=[{"name": "extract_jd_text", "args": {"text": "..."}, "id": "loop"}])

    mock_model = MagicMock()
    mock_model.bind_tools = MagicMock(return_value=mock_model)
    mock_model.ainvoke = AsyncMock(return_value=loop_msg)

    state = {"user_id": "u1", "jd_raw": "JD..."}

    with (
        patch("app.agents.prepare.research_agent.get_mcp_tools", new_callable=AsyncMock, return_value=[extract_tool, report_tool]),
        patch("app.agents.prepare.research_agent._chat_model", return_value=mock_model),
    ):
        result = await research_agent_node(state)

    # 即使 LLM 死循环，节点也应该兜底调 generate_position_report 出报告
    assert result["job_intel"] is not None
    assert result["job_intel"]["_trace"]["iterations"] >= 6


@pytest.mark.asyncio
async def test_research_agent_skips_when_no_jd():
    """没 jd_raw 也没 jd_url 时直接跳过，不启动 ReAct loop。"""
    from app.agents.prepare.research_agent import research_agent_node

    state = {"user_id": "u1"}  # 没 jd_raw

    with patch("app.agents.prepare.research_agent.get_mcp_tools", new_callable=AsyncMock) as mock_get:
        result = await research_agent_node(state)

    mock_get.assert_not_awaited()
    assert result["job_intel"] is None
    assert "research_agent" in result["completed_tools"]
```

- [ ] **Step 3: 跑测试确认失败**

```bash
uv run pytest tests/unit/test_research_agent.py -v
```

预期：4 条 FAIL

- [ ] **Step 4: 写实现**

创建 `backend/app/agents/prepare/research_agent.py`：

```python
"""Prepare 阶段 research_agent：ReAct sub-agent，通过 MCP 调 job-intel 工具，
为候选人产出一份目标岗位备课情报，写入 PrepareState["job_intel"]。

设计要点：
- ReAct loop 最多 6 轮 / 90s，超时或超轮次强制兜底 generate_position_report
- MCP 不可用或没 JD 时，job_intel 写 None，让 Supervisor 走 jd_analysis 兜底
- 记录 _trace 子字段（tools_used / iterations / elapsed_ms / final_thought）供前端展示
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.agents.prepare.research_prompts import RESEARCH_AGENT_SYSTEM_PROMPT
from app.agents.prepare.state import PrepareState
from app.core.logging import get_logger
from app.services.mcp_client import get_mcp_tools

log = get_logger("app.agents.prepare.research_agent")

MAX_ITERATIONS = 6
TOTAL_TIMEOUT_SECONDS = 90


def _chat_model() -> Any:
    """构造 LLM 实例（独立函数便于测试 mock）。"""
    from langchain_openai import ChatOpenAI

    from app.core.config import get_settings

    settings = get_settings()
    return ChatOpenAI(
        model=settings.openai_model_chat,
        api_key=settings.openai_api_key,
        timeout=30,
    )


def _build_context(state: PrepareState) -> str:
    """把候选人本次备课上下文转成 prompt 块。"""
    parts = []
    if state.get("user_direction"):
        parts.append(f"候选人目标方向：{state['user_direction']}")
    if state.get("user_background"):
        parts.append(f"候选人背景/简历摘要：{state['user_background'][:1500]}")
    if state.get("jd_raw"):
        parts.append(f"目标岗位 JD 原文：{state['jd_raw'][:2000]}")
    return "\n\n".join(parts) or "（候选人未提供详细上下文）"


def _extract_final_report(messages: list) -> dict | None:
    """从 ToolMessage 序列里找最后一次 generate_position_report 的结果。"""
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage) and msg.name == "generate_position_report":
            try:
                content = msg.content
                if isinstance(content, str):
                    return json.loads(content)
                if isinstance(content, dict):
                    return content
            except (json.JSONDecodeError, TypeError):
                continue
    return None


async def _force_finalize(tools_by_name: dict, partial_state: dict) -> dict | None:
    """兜底：超轮次/超时时，用已有数据强制调 generate_position_report 收尾。"""
    report_tool = tools_by_name.get("generate_position_report")
    if report_tool is None:
        return None
    args = {
        "title": partial_state.get("title", ""),
        "company": partial_state.get("company", ""),
        "jd_summary": partial_state.get("jd_summary", ""),
        "requirements": partial_state.get("requirements", []),
        "search_results": partial_state.get("search_results", {}),
        "directions": partial_state.get("directions", ["综合背景"]),
        "resume_content": partial_state.get("resume_content"),
    }
    try:
        result = await report_tool.ainvoke(args)
        if isinstance(result, str):
            return json.loads(result)
        return result
    except Exception as exc:
        log.warning("research_agent_force_finalize_failed", error=str(exc))
        return None


async def research_agent_node(state: PrepareState) -> PrepareState:
    """research_agent 节点：ReAct loop 调 MCP 工具，产出 job_intel 写 State。"""
    completed = state.get("completed_tools", [])

    # 没 JD 直接跳过
    if not state.get("jd_raw") and not state.get("jd_url"):
        log.info("research_agent_skip_no_jd")
        return {**state, "job_intel": None, "completed_tools": completed + ["research_agent"]}

    started = time.time()

    # 拉 MCP 工具
    tools = await get_mcp_tools()
    if not tools:
        log.warning("research_agent_no_mcp_tools_fallback")
        return {**state, "job_intel": None, "completed_tools": completed + ["research_agent"]}

    tools_by_name = {t.name: t for t in tools}

    # 初始化 ReAct 状态
    model = _chat_model().bind_tools(tools)
    messages: list = [
        SystemMessage(content=RESEARCH_AGENT_SYSTEM_PROMPT.format(context=_build_context(state))),
        HumanMessage(content="请开始调研。"),
    ]

    tools_used: list[str] = []
    final_thought = ""
    partial: dict[str, Any] = {}  # 累积 extract_jd_text / web_search 结果用于兜底

    try:
        for iteration in range(MAX_ITERATIONS):
            elapsed = time.time() - started
            if elapsed > TOTAL_TIMEOUT_SECONDS:
                log.warning("research_agent_total_timeout", elapsed=elapsed)
                break

            response = await asyncio.wait_for(
                model.ainvoke(messages),
                timeout=max(5, TOTAL_TIMEOUT_SECONDS - elapsed),
            )
            messages.append(response)

            if isinstance(response.content, str) and response.content.strip():
                final_thought = response.content.strip()[:300]

            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                log.info("research_agent_llm_decided_to_stop", iteration=iteration)
                break

            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("args", {}) or {}
                call_id = tc.get("id", name)
                tool = tools_by_name.get(name)
                if tool is None:
                    content = json.dumps({"error": f"unknown tool: {name}"})
                else:
                    try:
                        result = await asyncio.wait_for(tool.ainvoke(args), timeout=30)
                        content = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
                        tools_used.append(name)
                        # 累积关键中间产物，便于兜底
                        if name == "extract_jd_text" and isinstance(result, dict):
                            partial.update({
                                "title": result.get("title", ""),
                                "company": result.get("company", ""),
                                "jd_summary": result.get("jd_summary", ""),
                                "requirements": result.get("requirements", []),
                            })
                        elif name == "web_search":
                            partial.setdefault("search_results", {}).setdefault("general", []).extend(result if isinstance(result, list) else [])
                        elif name == "extract_resume" and isinstance(result, dict):
                            partial["resume_content"] = result.get("summary", "")
                    except Exception as exc:
                        log.warning("research_agent_tool_failed", tool=name, error=str(exc))
                        content = json.dumps({"error": str(exc)})

                messages.append(ToolMessage(content=content, tool_call_id=call_id, name=name))
    except asyncio.TimeoutError:
        log.warning("research_agent_iter_timeout")

    # 找最终报告：先看 messages 里有没有 generate_position_report 的结果，没有就强制兜底
    job_intel = _extract_final_report(messages)
    if job_intel is None:
        log.info("research_agent_no_final_report_force_finalize")
        job_intel = await _force_finalize(tools_by_name, partial)

    elapsed_ms = int((time.time() - started) * 1000)

    if job_intel is None:
        # 完全没拿到报告，让 Supervisor 走 jd_analysis 兜底
        log.warning("research_agent_failed_no_report", elapsed_ms=elapsed_ms, tools_used=tools_used)
        return {**state, "job_intel": None, "completed_tools": completed + ["research_agent"]}

    job_intel["_trace"] = {
        "tools_used": tools_used,
        "iterations": iteration + 1 if "iteration" in dir() else 0,
        "elapsed_ms": elapsed_ms,
        "final_thought": final_thought,
    }

    log.info(
        "research_agent_done",
        tools_used=tools_used,
        iterations=job_intel["_trace"]["iterations"],
        elapsed_ms=elapsed_ms,
        has_report=True,
    )
    return {**state, "job_intel": job_intel, "completed_tools": completed + ["research_agent"]}
```

- [ ] **Step 5: 跑测试**

```bash
uv run pytest tests/unit/test_research_agent.py -v
```

预期：4 条 PASS。如果有 fail，根据错误调试（特别注意 `_trace.iterations` 的字段是否能从循环外访问，必要时把 `iteration` 提到循环外初始化）。

- [ ] **Step 6: commit**

```bash
git add backend/app/agents/prepare/research_agent.py backend/app/agents/prepare/research_prompts.py backend/tests/unit/test_research_agent.py
git commit -m "feat(prepare): research_agent ReAct loop + 兜底 + 跳过逻辑（mock MCP 测试覆盖）"
```

---

### Task 15: Supervisor prompt 加 `research_agent` 决策规则

**Repository:** multi-agent-coach

**Files:**

- Modify: `backend/app/agents/prepare/prompts.py`

- [ ] **Step 1: 看现有 SUPERVISOR_COMBINED_PROMPT**

```bash
cat backend/app/agents/prepare/prompts.py
```

确认现有调用规则的编号 1-4 + END 条件。

- [ ] **Step 2: 改写 SUPERVISOR_COMBINED_PROMPT**

打开 `backend/app/agents/prepare/prompts.py`，找到现有规则段，**替换**为如下结构（在原有规则之间插入 research_agent，并把 jd_analysis 降级为兜底）：

```python
SUPERVISOR_COMBINED_PROMPT = """你是面试准备 Supervisor，负责调度各 Agent。

当前状态：
{state_summary}

已完成的 Agent：{completed_tools}

可选 next：
- memory_search：查候选人历史薄弱点 + 简历摘要兜底（内部 DB 查询）
- research_agent：ReAct 调研 Agent，通过 MCP 调 job-intel 工具产出 6 模块岗位情报
- jd_analysis：浅 JD 结构化（仅作 research_agent 失败时的兜底）
- question_gen：综合所有信息出 5 道定制题
- need_direction：用户没说方向，向用户追问
- END：结束

调用规则（按优先级）：
1. 若用户完全没有提供岗位方向信息 → next = "need_direction"
2. 若 memory_search 未完成 → next = "memory_search"
3. 若有 JD 且 research_agent 未完成 → next = "research_agent"
4. 若 research_agent 已完成但失败（job_intel 为空）且 jd_analysis 未完成 → next = "jd_analysis"
5. 若 research_agent 成功（job_intel 非空），跳过 jd_analysis，直接到第 6 步
6. 若 question_gen 未完成 → next = "question_gen"
7. 否则 → next = "END"

输出格式（最后一行必须是 DECISION 行）：

先用中文写 1-2 句你的判断。
DECISION: {{"next": "...", "direction": "...", "reasoning": "..."}}
"""
```

- [ ] **Step 3: 跑现有 Supervisor 相关测试**

```bash
uv run pytest tests/unit/test_prepare_nodes.py -k "supervisor" -v
```

预期：现有测试 PASS（如果有依赖旧 prompt 字面值的断言会 FAIL，按需调整测试以适配新规则）。

- [ ] **Step 4: commit**

```bash
git add backend/app/agents/prepare/prompts.py
git commit -m "feat(prepare): Supervisor prompt 加 research_agent 决策分支，jd_analysis 降级为兜底"
```

---

### Task 16: 把 research_agent 注册到 graph + 路由

**Repository:** multi-agent-coach

**Files:**

- Modify: `backend/app/agents/prepare/graph.py`

- [ ] **Step 1: 打开 graph.py，更新 `_NODE_MAP` 和标签**

修改 `backend/app/agents/prepare/graph.py`，找到 `_NODE_MAP / _NODE_LABELS / _NODE_TITLES` 这三个字典，每个都追加 `research_agent` 条目：

```python
_NODE_MAP = {
    "supervisor": nodes.supervisor_node,
    "memory_search": nodes.memory_search_node,
    "research_agent": _research_agent_lazy,   # ★ 新增
    "jd_analysis": nodes.jd_analysis_node,
    "question_gen": nodes.question_gen_node,
}

_NODE_LABELS = {
    "supervisor": "调度",
    "memory_search": "记忆检索",
    "research_agent": "岗位调研",     # ★
    "jd_analysis": "JD分析",
    "question_gen": "出题",
}

_NODE_TITLES = {
    "supervisor": "识别方向，启动准备",
    "memory_search": "读取历史表现",
    "research_agent": "通过 MCP 调研目标岗位",  # ★
    "jd_analysis": "构建岗位考点地图（兜底）",
    "question_gen": "定制专属题目",
}
```

- [ ] **Step 2: 加 `_research_agent_lazy` 包装**

在 `_NODE_MAP` 定义**之前**加一个延迟导入函数（避免 graph 模块导入期触发 MCP 连接）：

```python
async def _research_agent_lazy(state):
    """延迟导入 research_agent，避免模块加载期触发 MCP 连接。"""
    from app.agents.prepare.research_agent import research_agent_node
    return await research_agent_node(state)
```

- [ ] **Step 3: 改 `_build_graph` 注册节点 + 路由**

找到 `_build_graph()` 函数。它现在 add_node 3 个节点 + 1 个 supervisor，改为追加 research_agent：

```python
def _build_graph() -> Any:
    g = StateGraph(PrepareState)
    g.add_node("supervisor", nodes.supervisor_node)
    g.add_node("memory_search", nodes.memory_search_node)
    g.add_node("research_agent", _research_agent_lazy)   # ★
    g.add_node("jd_analysis", nodes.jd_analysis_node)
    g.add_node("question_gen", nodes.question_gen_node)

    g.set_entry_point("supervisor")

    g.add_conditional_edges(
        "supervisor",
        _supervisor_router,
        {
            "memory_search": "memory_search",
            "research_agent": "research_agent",  # ★
            "jd_analysis": "jd_analysis",
            "question_gen": "question_gen",
            "wait_direction": END,
            "END": END,
        },
    )

    g.add_edge("memory_search", "supervisor")
    g.add_edge("research_agent", "supervisor")           # ★
    g.add_edge("jd_analysis", "supervisor")
    g.add_edge("question_gen", "supervisor")

    return g.compile()
```

- [ ] **Step 4: 更新 `_format_..._trace` 加 research_agent 摘要**

在 `_node_completion_trace()` 函数里追加 research_agent 分支，让前端能看到调研结果（紧跟现有 `if ev_node == "jd_analysis"` 后）：

```python
def _format_research_agent_trace(state: dict[str, Any]) -> list[str]:
    job_intel = state.get("job_intel")
    if not job_intel:
        return ["岗位调研未启动或失败，已回退到 JD 浅分析。"]

    trace = job_intel.get("_trace", {})
    tools = trace.get("tools_used", [])
    iters = trace.get("iterations", 0)
    elapsed = trace.get("elapsed_ms", 0)

    lines = [f"调研完成，{iters} 轮、用了 {len(tools)} 次工具调用，耗时 {elapsed} 毫秒。"]
    company = (job_intel.get("company_profile") or {}).get("summary", "")
    if company:
        lines.append(f"公司画像：{company[:120]}")
    gaps = (job_intel.get("resume_match") or {}).get("gaps", [])
    if gaps:
        lines.append(f"针对此岗位的 Gap：{', '.join(gaps[:5])}")
    return lines


def _node_completion_trace(ev_node: str, state: dict[str, Any]) -> list[str]:
    if ev_node == "memory_search":
        return _format_memory_search_trace(state)
    if ev_node == "research_agent":         # ★
        return _format_research_agent_trace(state)
    if ev_node == "jd_analysis":
        return _format_jd_analysis_trace(state)
    return []
```

- [ ] **Step 5: 跑现有 prepare graph 测试**

```bash
uv run pytest tests/unit/test_prepare*.py -v 2>&1 | tail -30
```

预期：旧测试不应该被破坏。新节点没有专门的 graph 测试，下面集成测试覆盖。

- [ ] **Step 6: commit**

```bash
git add backend/app/agents/prepare/graph.py
git commit -m "feat(prepare): graph 注册 research_agent 节点 + 路由 + trace 摘要"
```

---

### Task 17: Prepare 节点 jd_analysis 路径不变（不改），question_gen 消费 job_intel

**Repository:** multi-agent-coach

**Files:**

- Modify: `backend/app/agents/prepare/nodes.py`
- Modify: `backend/app/agents/prepare/prompts.py`
- Modify: `backend/tests/unit/test_prepare_nodes.py`

`jd_analysis` 节点逻辑本身不变，它仍然是 supervisor 决策走它时的兜底；本任务给 `question_gen_node` 加 job_intel 消费。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/unit/test_prepare_nodes.py` 追加：

```python
@pytest.mark.asyncio
async def test_question_gen_uses_job_intel_when_available():
    """question_gen 应优先用 job_intel.job_interpretation 的 hard_requirements / focus 出题。"""
    from app.agents.prepare.nodes import question_gen_node

    state: PrepareState = {
        "user_id": "u1",
        "direction": "AI Agent 工程师",
        "user_direction": "AI Agent 工程师",
        "user_background": "3 年 Python",
        "weak_areas": [],
        "jd_context": None,
        "job_intel": {
            "job_interpretation": {
                "hard_requirements": ["分布式系统", "高并发"],
                "soft_requirements": ["快节奏适应"],
                "hidden_bonuses": ["LangGraph 经验"],
                "summary": "字节核心业务",
            },
            "resume_match": {"strengths": ["Python"], "gaps": ["缺分布式"]},
        },
    }

    mock_content = '[{"id":1,"question":"Q1","category":"technical","focus_area":"分布式","priority":1}]'
    captured: dict[str, str] = {}

    async def mock_astream(messages):
        captured["prompt"] = messages[0].content
        ch = MagicMock(); ch.content = mock_content
        yield ch

    with patch("app.agents.prepare.nodes._llm") as mock_llm:
        mock_llm.return_value.with_config.return_value.astream = mock_astream
        await question_gen_node(state)

    # 验证 job_intel 的硬要求和 gap 进了出题 prompt
    assert "分布式系统" in captured["prompt"]
    assert "缺分布式" in captured["prompt"]
```

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run pytest tests/unit/test_prepare_nodes.py::test_question_gen_uses_job_intel_when_available -v
```

预期：FAIL（断言"分布式系统" not in prompt）

- [ ] **Step 3: 改 QUESTION_GEN_SYSTEM_PROMPT 模板**

打开 `backend/app/agents/prepare/prompts.py`，找到 `QUESTION_GEN_SYSTEM_PROMPT`，在 `{jd_context_block}` 之后加 `{job_intel_block}`：

```python
QUESTION_GEN_SYSTEM_PROMPT = """你是专业面试出题官。根据以下信息生成 {count} 道高质量定制题。
...（保留原有正文）
练习方向：{direction}
目标岗位：{target_role}
{jd_context_block}
{job_intel_block}
{user_background_block}
{weak_areas_block}"""
```

- [ ] **Step 4: 改 question_gen_node 构造 job_intel_block**

打开 `backend/app/agents/prepare/nodes.py`，找到 `question_gen_node`，在 `jd_block` 构造之后追加：

```python
    # 优先用 research_agent 的 job_intel，没有则空字符串
    job_intel = state.get("job_intel") or {}
    job_intel_block = ""
    if job_intel:
        ji = job_intel.get("job_interpretation") or {}
        rm = job_intel.get("resume_match") or {}
        lines = []
        if ji.get("hard_requirements"):
            lines.append(f"岗位硬要求：{', '.join(ji['hard_requirements'])}")
        if ji.get("soft_requirements"):
            lines.append(f"岗位软偏好：{', '.join(ji['soft_requirements'])}")
        if rm.get("gaps"):
            lines.append(f"候选人对此岗位的 Gap（优先围绕这些出题）：{', '.join(rm['gaps'])}")
        if rm.get("strengths"):
            lines.append(f"候选人优势（可适当探测深度）：{', '.join(rm['strengths'])}")
        if lines:
            job_intel_block = "岗位调研情报：\n" + "\n".join(lines)
```

然后在 `prompt = QUESTION_GEN_SYSTEM_PROMPT.format(...)` 的参数里加 `job_intel_block=job_intel_block`：

```python
    prompt = QUESTION_GEN_SYSTEM_PROMPT.format(
        count=5,
        direction=direction,
        target_role=target_role,
        jd_context_block=jd_block,
        job_intel_block=job_intel_block,           # ★
        user_background_block=background_block,
        weak_areas_block=weak_block,
    )
```

- [ ] **Step 5: 跑测试确认通过**

```bash
uv run pytest tests/unit/test_prepare_nodes.py::test_question_gen_uses_job_intel_when_available -v
uv run pytest tests/unit/test_prepare_nodes.py -v 2>&1 | tail -10
```

预期：新测试 PASS，旧测试全 PASS。

- [ ] **Step 6: commit**

```bash
git add backend/app/agents/prepare/nodes.py backend/app/agents/prepare/prompts.py backend/tests/unit/test_prepare_nodes.py
git commit -m "feat(prepare): question_gen 消费 job_intel 的 hard_requirements 和 gaps 出更针对性题"
```

---

## Phase 4 — 下游 Agent 消费 job_intel

### Task 18: Designer prompt 消费 `job_interpretation` + `resume_match`

**Repository:** multi-agent-coach

**Files:**

- Modify: `backend/app/agents/designer/prompts.py`
- Modify: `backend/app/agents/designer/nodes.py`（或调用 prompt 的入口）

- [ ] **Step 1: 找 Designer 入口与 prompt 模板**

```bash
ls backend/app/agents/designer/
grep -n "SYSTEM_PROMPT\|def run_designer" backend/app/agents/designer/*.py
```

定位 designer 的 system prompt 模板和组装函数。

- [ ] **Step 2: 写 mini 失败测试**

在 `backend/tests/unit/` 下创建（或追加到现有 designer 测试）：

```python
# 文件：backend/tests/unit/test_designer_consumes_job_intel.py
"""Designer 应消费 job_intel 的 job_interpretation 和 resume_match 字段。"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_designer_prompt_contains_hard_requirements_and_gaps():
    """run_designer 组装出来的 prompt 应包含 job_intel 里的关键字段。"""
    from app.agents.designer import run_designer

    inputs = {
        "focus": "new_question",
        "target_role": "后端工程师",
        "target_company": "字节",
        "user_background": "3 年 Python",
        "candidate_profile": {},
        "jd_context": None,
        "previous_questions": [],
        "prepared_questions": [],
        "current_question_index": 0,
        "evaluator_report": None,
        "messages": [],
        "job_intel": {
            "job_interpretation": {
                "hard_requirements": ["分布式系统", "高并发"],
                "soft_requirements": [],
                "hidden_bonuses": [],
                "summary": "",
            },
            "resume_match": {"strengths": ["Python"], "gaps": ["缺分布式"]},
        },
    }

    captured: dict[str, str] = {}

    class FakeResp:
        content = '{"question_text": "Q", "question_category": "technical", "focus_area": "x", "source": "llm"}'

    async def fake_ainvoke(messages):
        captured["system"] = messages[0].content
        return FakeResp()

    with patch("app.agents.designer.nodes._chat_model") as mock_model:
        mock_model.return_value.ainvoke = fake_ainvoke
        await run_designer(inputs)

    assert "分布式系统" in captured["system"]
    assert "缺分布式" in captured["system"]
```

- [ ] **Step 3: 跑测试**

```bash
uv run pytest tests/unit/test_designer_consumes_job_intel.py -v
```

预期：FAIL（字段没进 prompt）

- [ ] **Step 4: 改 designer 接受 + 注入 job_intel**

打开 `backend/app/agents/designer/nodes.py`（或 `__init__.py`，看 `run_designer` 实际在哪），在组装 prompt 的位置加 job_intel 块：

```python
# 在 run_designer 组装 prompt 字段时：
job_intel = inputs.get("job_intel") or {}
ji = job_intel.get("job_interpretation") or {}
rm = job_intel.get("resume_match") or {}

job_intel_block = ""
if ji or rm:
    sub = []
    if ji.get("hard_requirements"):
        sub.append(f"岗位硬要求（出题重点考察）：{', '.join(ji['hard_requirements'])}")
    if ji.get("soft_requirements"):
        sub.append(f"岗位软偏好：{', '.join(ji['soft_requirements'])}")
    if rm.get("strengths"):
        sub.append(f"候选人对此岗位的强项（可适度探深）：{', '.join(rm['strengths'])}")
    if rm.get("gaps"):
        sub.append(f"候选人对此岗位的 Gap（优先围绕这些出题）：{', '.join(rm['gaps'])}")
    if sub:
        job_intel_block = "目标岗位情报：\n" + "\n".join(sub) + "\n"
```

把 `job_intel_block` 注入 prompt（看 designer 现有 SYSTEM_PROMPT 是否能加新占位符，没有就拼到 prompt 字符串末尾）。

- [ ] **Step 5: 跑测试**

```bash
uv run pytest tests/unit/test_designer_consumes_job_intel.py -v
```

预期：PASS

- [ ] **Step 6: commit**

```bash
git add backend/app/agents/designer/ backend/tests/unit/test_designer_consumes_job_intel.py
git commit -m "feat(designer): 出题 prompt 消费 job_intel 的 hard_requirements 与 resume_match.gaps"
```

---

### Task 19: Evaluator prompt 消费 `hard_requirements`

**Repository:** multi-agent-coach

**Files:**

- Modify: `backend/app/agents/evaluator/prompts.py` 或 `nodes.py`
- Create: `backend/tests/unit/test_evaluator_consumes_job_intel.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_evaluator_consumes_job_intel.py
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


@pytest.mark.asyncio
async def test_evaluator_prompt_contains_hard_requirements_as_dimension():
    """evaluator 的 prompt 应把 job_intel.hard_requirements 当评分维度引用。"""
    from app.agents.evaluator import run_evaluator

    inputs = {
        "session_id": "s1",
        "user_id": "u1",
        "target_role": "后端工程师",
        "latest_answer": "我用 Redis 做了缓存",
        "conversation_context": "",
        "existing_profile": {},
        "question_index": 0,
        "followup_index": 0,
        "db": None,
        "job_intel": {
            "job_interpretation": {
                "hard_requirements": ["分布式系统", "高并发"],
            },
        },
    }

    captured = {}

    class FakeResp:
        content = '{"scoring": {"summary_score": 7}, "report_text": "ok", "updated_profile": {}}'

    async def fake_ainvoke(messages):
        captured["system"] = messages[0].content
        return FakeResp()

    with patch("app.agents.evaluator.nodes._chat_model") as mock_model:
        mock_model.return_value.with_structured_output.return_value.ainvoke = fake_ainvoke
        mock_model.return_value.ainvoke = fake_ainvoke
        await run_evaluator(inputs)

    assert "分布式系统" in captured["system"]
```

- [ ] **Step 2: 跑测试**

```bash
uv run pytest tests/unit/test_evaluator_consumes_job_intel.py -v
```

预期：FAIL

- [ ] **Step 3: 改 evaluator 接受 + 注入**

在 evaluator 的 prompt 组装处追加：

```python
job_intel = inputs.get("job_intel") or {}
hard_reqs = (job_intel.get("job_interpretation") or {}).get("hard_requirements") or []

job_intel_block = ""
if hard_reqs:
    job_intel_block = (
        f"\n本岗位的硬性要求（请把这些作为评分维度，特别关注候选人回答是否触及）：\n"
        f"- " + "\n- ".join(hard_reqs) + "\n"
    )
```

把 `job_intel_block` 拼到 evaluator system prompt 末尾。

- [ ] **Step 4: 跑测试**

```bash
uv run pytest tests/unit/test_evaluator_consumes_job_intel.py -v
```

预期：PASS

- [ ] **Step 5: commit**

```bash
git add backend/app/agents/evaluator/ backend/tests/unit/test_evaluator_consumes_job_intel.py
git commit -m "feat(evaluator): 评分 prompt 把 job_intel.hard_requirements 作为评分维度"
```

---

### Task 20: Interviewer chief_prompts 注入 `company_profile` persona

**Repository:** multi-agent-coach

**Files:**

- Modify: `backend/app/agents/interviewer/chief_prompts.py`
- Modify: `backend/app/agents/interviewer/chief.py`（\_chief_context 函数）
- Create: `backend/tests/unit/test_chief_consumes_company_profile.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_chief_consumes_company_profile.py
import pytest


def test_chief_context_includes_company_profile():
    """_chief_context 应在 state 有 job_intel.company_profile 时把它拼进上下文。"""
    from app.agents.interviewer.chief import _chief_context

    state = {
        "question_count": 1,
        "total_questions": 5,
        "followup_count": 0,
        "max_followups": 2,
        "target_role": "后端工程师",
        "messages": [],
        "job_intel": {
            "company_profile": {
                "summary": "字节国际化团队，节奏快，技术栈以 Go 为主",
                "tags": ["扁平管理", "快节奏"],
            },
        },
    }

    ctx = _chief_context(state)
    assert "字节国际化团队" in ctx
    assert "扁平管理" in ctx
```

- [ ] **Step 2: 跑测试**

```bash
uv run pytest tests/unit/test_chief_consumes_company_profile.py -v
```

预期：FAIL

- [ ] **Step 3: 改 `_chief_context`**

打开 `backend/app/agents/interviewer/chief.py`，找到 `_chief_context()` 函数，在 `target_role` 之后追加：

```python
    job_intel = state.get("job_intel") or {}
    cp = job_intel.get("company_profile") or {}
    if cp.get("summary"):
        tags = cp.get("tags") or []
        tags_str = f"（关键词：{', '.join(tags)}）" if tags else ""
        parts.append(f"面试官 persona 提示：你正在以 {state.get('target_company') or '本公司'} 的风格主持面试。公司画像：{cp['summary']}{tags_str}")
```

- [ ] **Step 4: 跑测试**

```bash
uv run pytest tests/unit/test_chief_consumes_company_profile.py -v
```

预期：PASS

- [ ] **Step 5: commit**

```bash
git add backend/app/agents/interviewer/chief.py backend/tests/unit/test_chief_consumes_company_profile.py
git commit -m "feat(chief): 面试官上下文注入 job_intel.company_profile 当 persona 提示"
```

---

### Task 21: Coach prompt 消费 `gaps` + `prep_suggestions`

**Repository:** multi-agent-coach

**Files:**

- Modify: `backend/app/agents/coach/prompts.py` 或 `nodes.py`
- Create: `backend/tests/unit/test_coach_consumes_job_intel.py`

- [ ] **Step 1: 找 Coach 入口**

```bash
ls backend/app/agents/coach/
grep -n "SYSTEM_PROMPT\|def run_coach\|def coach_node" backend/app/agents/coach/*.py
```

- [ ] **Step 2: 写失败测试**

```python
# backend/tests/unit/test_coach_consumes_job_intel.py
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


@pytest.mark.asyncio
async def test_coach_prompt_includes_gaps_and_prep_suggestions():
    """Coach 反馈 prompt 应引用 job_intel.resume_match.gaps 和 prep_suggestions。"""
    # 按当前 coach 实际入口签名构造 inputs，此处给一个通用骨架：
    from app.agents.coach.nodes import _build_feedback_prompt   # 假设有这个工厂函数

    state = {
        "user_background": "3 年 Python",
        "evaluator_report": {"summary": "整体 7 分"},
        "target_role": "后端工程师",
        "job_intel": {
            "resume_match": {"strengths": ["Python"], "gaps": ["缺分布式", "未做过大流量"]},
            "prep_suggestions": [
                {"title": "3 天补分布式", "content": "看 DDIA 1-4 章"},
                {"title": "1 周写高并发 demo", "content": "用 Go 写 rate limiter"},
            ],
        },
    }

    prompt = _build_feedback_prompt(state)

    assert "缺分布式" in prompt
    assert "未做过大流量" in prompt
    assert "3 天补分布式" in prompt
```

- [ ] **Step 3: 跑测试**

```bash
uv run pytest tests/unit/test_coach_consumes_job_intel.py -v
```

预期：FAIL（函数不存在或没消费 job_intel）

- [ ] **Step 4: 在 coach 模块加 `_build_feedback_prompt` 工厂 + 注入 job_intel 块**

如果当前 coach 已有反馈 prompt 拼装函数，扩展它；否则新建：

```python
def _build_feedback_prompt(state: dict) -> str:
    """构造 coach 反馈 system prompt，注入 job_intel 的 gap 和准备建议。"""
    job_intel = state.get("job_intel") or {}
    rm = job_intel.get("resume_match") or {}
    suggestions = job_intel.get("prep_suggestions") or []

    intel_block = ""
    if rm.get("gaps") or suggestions:
        lines = []
        if rm.get("gaps"):
            lines.append("候选人对此岗位的 Gap：" + ", ".join(rm["gaps"]))
        if suggestions:
            lines.append("可参考的备战建议：")
            for s in suggestions[:5]:
                lines.append(f"- {s.get('title', '')}：{s.get('content', '')}")
        intel_block = "\n\n岗位调研情报（请基于这些给针对性建议）：\n" + "\n".join(lines)

    # 与现有 coach prompt 拼接（按当前实现调整）
    base = COACH_FEEDBACK_SYSTEM_PROMPT.format(
        target_role=state.get("target_role", ""),
        user_background=state.get("user_background", ""),
        evaluator_summary=str(state.get("evaluator_report") or "")[:1500],
    )
    return base + intel_block
```

在 `coach_node` 调用处改为用该函数生成 prompt。

- [ ] **Step 5: 跑测试**

```bash
uv run pytest tests/unit/test_coach_consumes_job_intel.py -v
```

预期：PASS

- [ ] **Step 6: commit**

```bash
git add backend/app/agents/coach/ backend/tests/unit/test_coach_consumes_job_intel.py
git commit -m "feat(coach): 反馈 prompt 消费 job_intel.gaps 与 prep_suggestions"
```

---

## Phase 5 — 集成与降级验证

### Task 22: Prepare 端到端集成测试（mock MCP 完整路径）

**Repository:** multi-agent-coach

**Files:**

- Create: `backend/tests/integration/test_prepare_with_mcp.py`

- [ ] **Step 1: 写集成测试**

创建 `backend/tests/integration/test_prepare_with_mcp.py`：

```python
"""Prepare 端到端集成：从 supervisor 启动 → memory_search + research_agent 并行 → question_gen 收尾。

不连真实 MCP，全程 mock。验证状态机正确串联。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, ToolMessage


@pytest.mark.asyncio
async def test_prepare_full_flow_with_mcp_success():
    """完整路径：research_agent 成功 → 跳过 jd_analysis → question_gen 拿到 job_intel。"""
    from app.agents.prepare.graph import get_prepare_graph

    fake_report = {
        "job_interpretation": {
            "hard_requirements": ["分布式系统", "高并发"],
            "soft_requirements": [], "hidden_bonuses": [], "summary": "",
        },
        "resume_match": {"strengths": ["Python"], "gaps": ["缺分布式"]},
        "company_profile": {"summary": "字节核心业务", "tags": ["快节奏"]},
        "interview_qa": [],
        "salary_range": {},
        "prep_suggestions": [{"title": "3 天补分布式", "content": "DDIA"}],
    }

    # Mock supervisor LLM：先 → research_agent，再 → memory_search，再 → question_gen，再 → END
    sup_responses = iter([
        AIMessage(content='DECISION: {"next": "research_agent", "direction": "AI Agent 工程师", "reasoning": "有 JD"}'),
        AIMessage(content='DECISION: {"next": "memory_search", "direction": "AI Agent 工程师", "reasoning": ""}'),
        AIMessage(content='DECISION: {"next": "question_gen", "direction": "AI Agent 工程师", "reasoning": ""}'),
        AIMessage(content='DECISION: {"next": "END", "direction": "AI Agent 工程师", "reasoning": ""}'),
    ])

    # research_agent 内部 mock：1 轮 generate_position_report
    report_msg = AIMessage(content="", tool_calls=[{"name": "generate_position_report", "args": {"title": "x", "company": "y", "jd_summary": "", "requirements": [], "search_results": {}, "directions": ["x"]}, "id": "c1"}])
    stop_msg = AIMessage(content="完成")

    report_tool = MagicMock(); report_tool.name = "generate_position_report"; report_tool.ainvoke = AsyncMock(return_value=fake_report)

    # question_gen mock 输出 1 道题
    qg_chunk = MagicMock(); qg_chunk.content = '[{"id":1,"question":"Q1","category":"technical","focus_area":"分布式","priority":1}]'

    async def qg_astream(messages):
        yield qg_chunk

    with (
        patch("app.agents.prepare.nodes._llm") as mock_llm,
        patch("app.agents.prepare.research_agent.get_mcp_tools", new_callable=AsyncMock, return_value=[report_tool]),
        patch("app.agents.prepare.research_agent._chat_model") as mock_research_model,
        patch("app.agents.prepare.nodes._get_recent_sessions", new_callable=AsyncMock, return_value=[]),
        patch("app.agents.prepare.nodes._get_resume_summary", new_callable=AsyncMock, return_value=None),
    ):
        # supervisor LLM
        sup_model = mock_llm.return_value.with_config.return_value
        sup_model.astream = AsyncMock(side_effect=lambda m: _async_gen([next(sup_responses)]))
        # research_agent LLM
        rmodel = MagicMock()
        rmodel.bind_tools = MagicMock(return_value=rmodel)
        rmodel.ainvoke = AsyncMock(side_effect=[report_msg, stop_msg])
        mock_research_model.return_value = rmodel
        # question_gen LLM
        mock_llm.return_value.with_config.return_value.astream = qg_astream

        graph = get_prepare_graph()
        init_state = {
            "session_id": "s1",
            "user_id": "u1",
            "user_direction": "AI Agent 工程师",
            "jd_raw": "字节后端 JD 全文...",
        }
        final = await graph.ainvoke(init_state)

    assert final.get("job_intel") is not None
    assert final["job_intel"]["resume_match"]["gaps"] == ["缺分布式"]
    assert len(final.get("prepared_questions", [])) == 1
    assert "research_agent" in final.get("completed_tools", [])
    assert "memory_search" in final.get("completed_tools", [])


async def _async_gen(items):
    for x in items:
        yield x


@pytest.mark.asyncio
async def test_prepare_falls_back_to_jd_analysis_when_mcp_down():
    """MCP 不可用时（工具列表为空），Supervisor 路径走 jd_analysis 兜底，仍能产出题目。"""
    from app.agents.prepare.graph import get_prepare_graph

    sup_responses = iter([
        AIMessage(content='DECISION: {"next": "research_agent", "direction": "AI Agent 工程师", "reasoning": ""}'),
        AIMessage(content='DECISION: {"next": "memory_search", "direction": "AI Agent 工程师", "reasoning": ""}'),
        AIMessage(content='DECISION: {"next": "jd_analysis", "direction": "AI Agent 工程师", "reasoning": ""}'),
        AIMessage(content='DECISION: {"next": "question_gen", "direction": "AI Agent 工程师", "reasoning": ""}'),
        AIMessage(content='DECISION: {"next": "END", "direction": "AI Agent 工程师", "reasoning": ""}'),
    ])

    # jd_analysis 用 with_structured_output 调用
    class JDOut:
        company = "字节"; role = "后端"; key_skills = ["Python"]; focus_areas = ["分布式"]; difficulty = "medium"

    qg_chunk = MagicMock(); qg_chunk.content = '[{"id":1,"question":"Q1","category":"technical","focus_area":"x","priority":1}]'

    async def qg_astream(messages):
        yield qg_chunk

    with (
        patch("app.agents.prepare.nodes._llm") as mock_llm,
        patch("app.agents.prepare.research_agent.get_mcp_tools", new_callable=AsyncMock, return_value=[]),
        patch("app.agents.prepare.nodes._get_recent_sessions", new_callable=AsyncMock, return_value=[]),
        patch("app.agents.prepare.nodes._get_resume_summary", new_callable=AsyncMock, return_value=None),
    ):
        sup_model = mock_llm.return_value.with_config.return_value
        sup_model.astream = AsyncMock(side_effect=lambda m: _async_gen([next(sup_responses)]))
        mock_llm.return_value.with_structured_output.return_value.ainvoke = AsyncMock(return_value=JDOut())
        mock_llm.return_value.with_config.return_value.astream = qg_astream

        graph = get_prepare_graph()
        init_state = {
            "session_id": "s2",
            "user_id": "u2",
            "user_direction": "AI Agent 工程师",
            "jd_raw": "字节后端 JD...",
        }
        final = await graph.ainvoke(init_state)

    assert final.get("job_intel") is None
    assert final.get("jd_context") is not None  # 兜底走了 jd_analysis
    assert len(final.get("prepared_questions", [])) == 1
```

- [ ] **Step 2: 跑测试**

```bash
uv run pytest tests/integration/test_prepare_with_mcp.py -v 2>&1 | tail -40
```

预期：2 条 PASS。如果 mock 顺序不对会报 StopIteration，调整 sup_responses 列表顺序匹配 supervisor 实际决策步数。

- [ ] **Step 3: commit**

```bash
git add backend/tests/integration/test_prepare_with_mcp.py
git commit -m "test(integration): Prepare 端到端 + MCP 成功/降级两条路径"
```

---

### Task 23: 全量回归 + 类型检查 + lint

**Repository:** multi-agent-coach

- [ ] **Step 1: 跑全部单元测试**

```bash
cd backend
uv run pytest tests/unit/ -v 2>&1 | tail -30
```

预期：全部 PASS，无 import 报错。

- [ ] **Step 2: 跑集成测试**

```bash
uv run pytest tests/integration/test_prepare_with_mcp.py -v 2>&1 | tail -20
```

预期：2 条 PASS。

- [ ] **Step 3: 跑 ruff**

```bash
uv run ruff check app/agents/prepare/ app/services/mcp_client.py app/agents/interviewer/state.py app/agents/interviewer/chief.py app/agents/designer/ app/agents/evaluator/ app/agents/coach/
```

预期：无错或仅有可接受 warning。如有需要修复。

- [ ] **Step 4: 跑 mypy**

```bash
uv run mypy app/agents/prepare/research_agent.py app/agents/prepare/research_prompts.py app/services/mcp_client.py
```

预期：无致命类型错误（可能有 `Any` 警告，可忽略）。

- [ ] **Step 5: commit 修复（如有）**

```bash
git add -p   # 选择性 add 只跟修复有关的改动
git commit -m "chore: ruff/mypy 修复 research_agent 与 mcp_client 相关告警"
```

如无需要修复，跳过 commit。

---

### Task 24: 端到端联调（启 job-intel MCP + 跑 multi 备课）

**Repository:** 两个仓库均涉及（手动验证）

- [ ] **Step 1: 启 job-intel MCP server（终端 A）**

```bash
cd /Users/xuebao/learn/AI项目/job-intel-agent/backend
uv run python -m app.mcp_server
```

- [ ] **Step 2: 启 multi dev 全栈（终端 B）**

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach
./dev.sh
```

- [ ] **Step 3: 浏览器打开 multi 前端，启动一次备课**

操作：

- 登录
- 进入"开始模拟面试"
- 填写：方向 = "AI Agent 工程师"，目标公司 = "字节"，目标岗位 = "后端工程师"
- 粘一段真实 JD 文本
- 点"开始备课"

观察前端：

- trace panel 应该看到 `research_agent` 节点出现
- 节点完成后应有"调研完成"消息
- 题目卡片应能正常出现

- [ ] **Step 4: 看 multi 后端日志**

终端 B 输出应包含：

```
mcp_tools_loaded ... count=6
research_agent_done ... tools_used=[...] iterations=N
```

- [ ] **Step 5: 看 job-intel MCP 日志（终端 A）**

应能看到 multi 过来的工具调用请求。

- [ ] **Step 6: 关闭 job-intel MCP，再发起一次备课，验证降级**

终端 A Ctrl+C。然后在浏览器再启动一次备课。

预期：

- multi 后端日志出现 `mcp_connection_failed_fallback`
- Supervisor 走 `jd_analysis` 路径
- 题目仍能正常出现，用户感知不到差异

- [ ] **Step 7: 联调完成**

不需要 commit 任何代码（本任务只是手动验证）。如果发现 bug，回到对应 Task 修复。

---

### Task 25: 推送 + PR

**Repository:** multi-agent-coach

- [ ] **Step 1: 检查改动总览**

```bash
git log --oneline main..HEAD
```

预期：看到 Phase 2-5 的所有 commit。

- [ ] **Step 2: 推送 multi 分支**

```bash
git push -u origin feature/research-agent-mcp
```

- [ ] **Step 3: 推送 job-intel 分支（如未推）**

```bash
cd /Users/xuebao/learn/AI项目/job-intel-agent
git status
git log --oneline origin/main..HEAD
git push -u origin feature/mcp-server   # 如未推
```

- [ ] **Step 4: 在 multi 仓库开 PR**

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach
gh pr create --title "feat: research_agent + job-intel MCP 接入" --body "$(cat <<'EOF'
## Summary

- 新增 Prepare 阶段 research_agent 节点（ReAct sub-agent）
- 通过 MCP 协议接入 job-intel-agent 的 6 个工具（streamable HTTP）
- research_agent 与 memory_search 并行；jd_analysis 退化为降级兜底
- 下游 Designer / Evaluator / Coach / Interviewer 消费 job_intel 字段
- 砍掉 interview_qa（避免 LLM 自循环）和 salary_range（避免假数据）

依赖 job-intel-agent 同步开 PR：`feature/mcp-server`

## Spec

`docs/superpowers/specs/2026-06-03-research-agent-mcp-design.md`

## Plan

`docs/superpowers/plans/2026-06-03-research-agent-mcp.md`

## Test plan

- [ ] 单元测试全 PASS（`uv run pytest tests/unit/`）
- [ ] 集成测试 PASS（`uv run pytest tests/integration/test_prepare_with_mcp.py`）
- [ ] 联调通：浏览器启动备课，trace 看到 research_agent 节点 + 工具调用
- [ ] 联调降级：关掉 job-intel MCP，备课仍能完成（走 jd_analysis 兜底）

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: 在 job-intel 仓库也开 PR**

```bash
cd /Users/xuebao/learn/AI项目/job-intel-agent
gh pr create --title "feat: 新增 MCP server 暴露 6 个能力" --body "$(cat <<'EOF'
## Summary

- 新增独立 FastMCP server（streamable HTTP, IPv6, port 9001）
- 暴露 4 必选 + 2 可选工具：extract_jd_text / web_search / analyze_position / generate_position_report / scrape_jd_url / extract_resume
- 复用现有 service / graph 节点函数，无状态、不写 DB
- dev.sh 同步启动 MCP server

## 消费方

multi-agent-coach 的 Prepare 阶段 research_agent，相关 PR 见 multi 仓库 `feature/research-agent-mcp`。

## 契约文档

`docs/specs/2026-06-03-mcp-server-contract.md`

## Test plan

- [ ] 单元测试 PASS（`cd backend && uv run pytest tests/unit/test_mcp_server.py`）
- [ ] 手动 smoke：`uv run python -m app.mcp_server` 启动并 curl 验证
- [ ] dev.sh 启动后 multi 端能拉到 6 个工具

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

至此实施完成。

---

## 不在本期范围（follow-up plans）

| Follow-up                                   | 范围                                                                                                             |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| 前端 trace panel 渲染 research_agent 子节点 | multi 前端：把 research_agent 内部的 tool_thinking / tool_call_start / tool_call_done SSE 事件渲染成 collapse 树 |
| MCP 鉴权层                                  | job-intel MCP server 加 Bearer token middleware，支持跨 Railway Project 部署                                     |
| 备课笔记 HIL                                | 用户审核/修改 research_agent 产出的 job_intel 后再开始面试                                                       |
| 面试结果回流 job-intel                      | Evaluator 标记情报里哪些点被实战验证，回写到 job-intel 数据库                                                    |

---

## Self-Review 检查结果

- **Spec 覆盖**：spec 第 4 章 → Tasks 2-8；第 5 章 → Tasks 9-21；第 6 章下游消费 → Tasks 18-21；第 7 章通信细节 → Tasks 9-11；第 8 章降级 → Task 22 第二条；第 9 章 trace → Task 16 trace 摘要（前端渲染留 follow-up）；第 10 章验收 → Tasks 22-24
- **Placeholder 扫描**：无 TBD / TODO；每个 step 含具体代码或具体命令
- **类型一致性**：`JobIntel` TypedDict 在 Task 12 定义，跨阶段透传用 `dict | None`（Task 13 注释说明原因）；`research_agent_node` 签名跨 Tasks 14-22 保持一致；`get_mcp_tools` / `get_tool` 签名在 Tasks 10-14 一致
