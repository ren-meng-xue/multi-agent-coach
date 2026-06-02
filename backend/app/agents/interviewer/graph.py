import logging
from collections.abc import AsyncIterator
from typing import Any

from app.agents.interviewer.state import InterviewState

logger = logging.getLogger(__name__)

# 前端显示的节点名称映射
_PUBLIC_TRACE_NODES = {
    "question_gen": "准备题目",
    "chief_think": "思考",
    "chief_respond": "回复",
    "master": "调度",
    "evaluator": "评估",
    "followup": "面试官 · 追问",
    "ask_question": "面试官 · 出题",
    "closing": "收尾",
}

# 不发 node_* 事件的内部节点（用户无需可见）
# designer/evaluator 子图内部节点也在此隐藏——其结果通过 chief_think node_done 向上传递
_HIDDEN_NODES = {
    "load_context",
    "report",
    "chief_execute",
    # designer 子图内部节点
    "design",
    "validate",
    "respond_to_chief",
    # evaluator 子图内部节点
    "analyze_answer",
    "update_profile",
    # designer_dual 子图内部节点
    "design_dual",
}


def _stream_chunk_text(chunk: Any) -> str:
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return str(content)


def _latest_evaluation_payload(node_dict: dict[str, Any]) -> dict[str, Any]:
    evals = node_dict.get("turn_evaluations") or []
    if evals:
        last_eval = evals[-1]
        return {
            "summary_score": last_eval.get("summary_score", 0),
            "candidate_level": last_eval.get("candidate_level", "junior"),
            "latent_signals": last_eval.get("latent_signals", []),
            "missing_dimensions": last_eval.get("missing_dimensions", []),
        }
    return {}


async def stream_graph_events(
    graph: Any,
    initial_state: InterviewState,
    config: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    """
    包装 LangGraph 的 astream_events，将其转换为前端 SSE 友好的事件流。
    """
    final_state = None

    async for event in graph.astream_events(initial_state, config, version="v2"):
        ev_name = event.get("event")
        ev_node = event.get("metadata", {}).get("langgraph_node")

        # 1. 节点开始
        if ev_name == "on_chain_start" and ev_node:
            if ev_node in _HIDDEN_NODES:
                continue
            yield {
                "event": "node_start",
                "data": {
                    "node": ev_node,
                    "label": _PUBLIC_TRACE_NODES.get(ev_node, ev_node),
                },
            }

        # 2. 节点过程 (Token 流)
        # 我们只关心特定节点的 LLM 输出
        if ev_name == "on_chat_model_stream" and ev_node:
            if ev_node in _HIDDEN_NODES:
                continue

            chunk = event.get("data", {}).get("chunk")
            if chunk:
                text = _stream_chunk_text(chunk)
                if text:
                    yield {
                        "event": "node_token",
                        "data": {
                            "node": ev_node,
                            "text": text,
                        },
                    }

        # 3. 节点结束 (携带 Payload)
        if ev_name == "on_chain_end" and ev_node:
            if ev_node in _HIDDEN_NODES:
                continue

            # 提取节点产生的状态增量
            node_state = event.get("data", {}).get("output")
            payload = {
                "node": ev_node,
                "label": _PUBLIC_TRACE_NODES.get(ev_node, ev_node),
                "elapsed_ms": 0,  # 暂不计算精确耗时
            }

            node_dict = {}
            if hasattr(node_state, "model_dump"):
                node_dict = node_state.model_dump()
            elif hasattr(node_state, "dict"):
                node_dict = node_state.dict()

            if ev_node == "master" and isinstance(node_dict, dict):
                payload["chain"] = node_dict.get("chain", [])
                payload["followup_focus"] = node_dict.get("followup_focus", "")
            if ev_node == "chief_think" and isinstance(node_dict, dict):
                msgs = node_dict.get("chief_messages") or []
                last = msgs[-1] if msgs else None
                tool_calls = [tc["name"] for tc in (getattr(last, "tool_calls", None) or [])]
                payload["chief_tool_calls"] = tool_calls
                payload["chief_thoughts"] = node_dict.get("chief_thoughts", [])
                # 补上 designer 出题结果，供前端展示
                designer = node_dict.get("designer_output") or {}
                if designer.get("question_text"):
                    payload["designed_question"] = designer.get("question_text", "")
            if isinstance(node_dict, dict):
                payload.update(_latest_evaluation_payload(node_dict))
            # 对于 ask_question/followup/closing 节点，将 assistant_message 附在 node_done
            # 里，供前端在没有 LLM token 流时（如有备题路径）填充 trace 面板内容
            if ev_node in ("ask_question", "followup", "closing", "chief_respond") and isinstance(node_dict, dict):
                am = node_dict.get("assistant_message", "")
                if am:
                    payload["assistant_message"] = am
            yield {"event": "node_done", "data": payload}

        # 全图结束
        if ev_name == "on_chain_end" and event.get("name") == "LangGraph":
            final_state = event.get("data", {}).get("output")

    if final_state is None:
        raise RuntimeError("interviewer graph did not produce final state")
    yield {"event": "final", "data": final_state}
