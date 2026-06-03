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
from typing import Any, cast

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from app.agents.prepare.research_prompts import RESEARCH_AGENT_SYSTEM_PROMPT
from app.agents.prepare.state import PrepareState
from app.core.logging import get_logger
from app.services.mcp_client import get_mcp_tools

from contextlib import suppress

try:
    from langgraph.config import get_stream_writer  # type: ignore
except ImportError:  # 老版本 LangGraph 兼容
    def get_stream_writer():  # type: ignore
        return None

log = get_logger("app.agents.prepare.research_agent")

MAX_ITERATIONS = 6
TOTAL_TIMEOUT_SECONDS = 90


def _summarize_args(args: dict) -> str:
    """工具入参摘要：截短长字符串、隐藏 list/dict 内容，前端可直接展示。"""
    parts: list[str] = []
    for k, v in (args or {}).items():
        if isinstance(v, str):
            v_short = v[:60] + ("..." if len(v) > 60 else "")
            parts.append(f'{k}="{v_short}"')
        elif isinstance(v, list):
            parts.append(f"{k}=<list len={len(v)}>")
        elif isinstance(v, dict):
            parts.append(f"{k}=<dict len={len(v)}>")
        else:
            parts.append(f"{k}={v}")
    return ", ".join(parts)


def _summarize_result(result) -> str:
    """工具出参摘要：dict 列 key、list 给计数、string 截短。"""
    if isinstance(result, dict):
        keys = list(result.keys())[:6]
        body = ", ".join(keys)
        suffix = "..." if len(result) > 6 else ""
        return "{" + body + "}" + suffix
    if isinstance(result, list):
        return f"[{len(result)} 条结果]"
    if isinstance(result, str):
        if len(result) > 120:
            return result[:120] + "..."
        return result
    s = str(result)
    return s[:120] + ("..." if len(s) > 120 else "")


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
    user_direction = state.get("user_direction")
    if user_direction:
        parts.append(f"候选人目标方向：{user_direction}")
    user_background = state.get("user_background")
    if user_background:
        parts.append(f"候选人背景/简历摘要：{user_background[:1500]}")
    jd_raw = state.get("jd_raw")
    if jd_raw:
        parts.append(f"目标岗位 JD 原文：{jd_raw[:2000]}")
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


def _remaining_budget_seconds(started: float) -> float:
    """返回 research_agent 本轮总预算剩余秒数。"""
    return max(0.0, TOTAL_TIMEOUT_SECONDS - (time.time() - started))


async def _force_finalize(
    tools_by_name: dict,
    partial_state: dict,
    timeout_seconds: float,
) -> dict | None:
    """兜底：超轮次/超时时，用已有数据强制调 generate_position_report 收尾。"""
    if timeout_seconds <= 0:
        log.warning("research_agent_force_finalize_budget_exhausted")
        return None

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
        result = await asyncio.wait_for(report_tool.ainvoke(args), timeout=timeout_seconds)
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

    try:
        writer = get_stream_writer()
    except Exception:
        writer = None

    def _emit(payload: dict) -> None:
        """安全 emit：writer 为 None 或抛错时静默跳过，绝不阻断业务。"""
        if writer is None:
            return
        try:
            writer(payload)
        except Exception as exc:
            log.warning("research_agent_emit_failed", error=str(exc))

    # 拉 MCP 工具
    try:
        tools = await get_mcp_tools()
    except Exception as exc:
        elapsed_ms = int((time.time() - started) * 1000)
        log.warning("research_agent_get_mcp_tools_failed", error=str(exc), elapsed_ms=elapsed_ms)
        return {**state, "job_intel": None, "completed_tools": completed + ["research_agent"]}

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
    iteration = 0

    try:
        for iteration in range(MAX_ITERATIONS):
            remaining = _remaining_budget_seconds(started)
            if remaining <= 0:
                log.warning("research_agent_total_timeout", elapsed_ms=int((time.time() - started) * 1000))
                break

            think_step_id = f"think-{iteration}"
            _emit({"kind": "tool_thinking_start", "iteration": iteration, "step_id": think_step_id})

            # 流式调用 LLM，每个 chunk emit token 事件并累积成完整 response
            chunks = []
            async for chunk in model.astream(messages):
                chunks.append(chunk)
                token = chunk.content if isinstance(chunk.content, str) else ""
                if token:
                    _emit({
                        "kind": "tool_thinking_token",
                        "iteration": iteration,
                        "step_id": think_step_id,
                        "text": token,
                    })

            if chunks:
                response = chunks[0]
                for c in chunks[1:]:
                    response = response + c
            else:
                response = await asyncio.wait_for(model.ainvoke(messages), timeout=remaining)

            messages.append(response)
            _emit({"kind": "tool_thinking_done", "iteration": iteration, "step_id": think_step_id})

            if isinstance(response.content, str) and response.content.strip():
                final_thought = response.content.strip()[:300]

            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                log.info("research_agent_llm_decided_to_stop", iteration=iteration)
                break

            for tc in tool_calls:
                remaining = _remaining_budget_seconds(started)
                if remaining <= 0:
                    log.warning(
                        "research_agent_budget_exhausted_before_tool",
                        tool=tc.get("name", ""),
                        elapsed_ms=int((time.time() - started) * 1000),
                    )
                    break

                name = tc.get("name", "")
                args = tc.get("args", {}) or {}
                call_id = tc.get("id", name)
                step_id = f"tool-{iteration}-{call_id}"

                _emit({
                    "kind": "tool_call_start",
                    "iteration": iteration,
                    "step_id": step_id,
                    "tool_name": name,
                    "tool_args_summary": _summarize_args(args),
                })

                t0 = time.time()
                tool = tools_by_name.get(name)
                if tool is None:
                    content = json.dumps({"error": f"unknown tool: {name}"})
                    _emit({
                        "kind": "tool_call_done",
                        "iteration": iteration,
                        "step_id": step_id,
                        "tool_error": f"unknown tool: {name}",
                        "tool_elapsed_ms": 0,
                    })
                else:
                    try:
                        result = await asyncio.wait_for(tool.ainvoke(args), timeout=min(30, remaining))
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

                        _emit({
                            "kind": "tool_call_done",
                            "iteration": iteration,
                            "step_id": step_id,
                            "tool_result_summary": _summarize_result(result),
                            "tool_elapsed_ms": int((time.time() - t0) * 1000),
                        })
                    except Exception as exc:
                        log.warning("research_agent_tool_failed", tool=name, error=str(exc))
                        content = json.dumps({"error": str(exc)})
                        _emit({
                            "kind": "tool_call_done",
                            "iteration": iteration,
                            "step_id": step_id,
                            "tool_error": str(exc),
                            "tool_elapsed_ms": int((time.time() - t0) * 1000),
                        })

                messages.append(ToolMessage(content=content, tool_call_id=call_id, name=name))
    except asyncio.TimeoutError:
        log.warning("research_agent_iter_timeout")
    except Exception as exc:
        log.warning(
            "research_agent_loop_failed",
            error=str(exc),
            elapsed_ms=int((time.time() - started) * 1000),
        )

    # 找最终报告：先看 messages 里有没有 generate_position_report 的结果，没有就强制兜底
    job_intel = _extract_final_report(messages)
    if job_intel is None:
        remaining = _remaining_budget_seconds(started)
        log.info("research_agent_no_final_report_force_finalize", remaining_seconds=remaining)
        job_intel = await _force_finalize(tools_by_name, partial, timeout_seconds=remaining)

    elapsed_ms = int((time.time() - started) * 1000)

    if job_intel is None:
        # 完全没拿到报告，让 Supervisor 走 jd_analysis 兜底
        log.warning("research_agent_failed_no_report", elapsed_ms=elapsed_ms, tools_used=tools_used)
        return {**state, "job_intel": None, "completed_tools": completed + ["research_agent"]}

    job_intel["_trace"] = {
        "tools_used": tools_used,
        "iterations": iteration + 1,
        "elapsed_ms": elapsed_ms,
        "final_thought": final_thought,
    }

    log.info(
        "research_agent_done",
        tools_used=tools_used,
        iterations=iteration + 1,
        elapsed_ms=elapsed_ms,
        has_report=True,
    )
    from app.agents.prepare.state import JobIntel
    return {**state, "job_intel": cast(JobIntel, job_intel), "completed_tools": completed + ["research_agent"]}
