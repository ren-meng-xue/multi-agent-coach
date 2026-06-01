"""把 eval input_json 接通到真实 Agent 节点。

每个 target_type 对应一个 adapter，负责：
1. 把 eval benchmark 的 input_json（纯 dict）转换成 Agent 节点期待的 state 形状
2. 调用 Agent 节点函数（用 ainvoke 单节点方式，不跑整图）
3. 把节点返回的 partial state 重新组织成 judge 容易消费的 dict

不接 master_node / load_memory / persist 等无可评 LLM 输出的节点。
"""
from collections.abc import Awaitable, Callable
from typing import Any, cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.agents.coach.nodes import plan_node as _coach_plan_node
from app.agents.coach.nodes import review_node as _coach_review_node
from app.agents.coach.state import CoachState
from app.agents.interviewer.nodes import evaluator_node, followup_node
from app.agents.interviewer.state import InterviewState
from app.agents.prepare.nodes import question_gen_node
from app.agents.prepare.state import PrepareState
from app.eval.dimensions import TargetType

SystemCall = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def _messages_from_input(raw: list[dict[str, Any]] | None) -> list[BaseMessage]:
    """把 eval benchmark 用的 [{"role": ".ai|user", "content": "..."}] 序列
    转成 LangChain 的 BaseMessage 列表。

    role 大小写不敏感；".ai" / "assistant" 视为 AI，其余按用户处理。
    """
    msgs: list[BaseMessage] = []
    for m in raw or []:
        role = str(m.get("role") or "").lower()
        content = str(m.get("content", ""))
        if role in (".ai", "assistant"):
            msgs.append(AIMessage(content=content))
        else:
            msgs.append(HumanMessage(content=content))
    return msgs


async def _call_question(input_json: dict[str, Any]) -> dict[str, Any]:
    """评估 prepare.question_gen_node 出题质量。

    input_json 关心字段：
        direction (str)
        user_direction (str | None)
        weak_areas (list[str])
        star_stories (list[dict], 每项含 title)
        jd_context (dict | None, 含 focus_areas / key_skills)
    """
    state = cast(PrepareState, {**input_json})
    out = await question_gen_node(state)
    return {
        "prepared_questions": out.get("prepared_questions", []),
        "summary": out.get("summary", ""),
    }


async def _call_scoring(input_json: dict[str, Any]) -> dict[str, Any]:
    """评估 interviewer.evaluator_node 评分一致性。

    input_json 关心字段：
        messages (list[{"role", "content"}])  最近对话
        target_role (str)
        candidate_profile (dict)  历史画像，可空
        turn_evaluations (list[dict])  已有评估，可空
        question_count / followup_count / current_question_index (int)
    """
    state = cast(InterviewState, {
        **input_json,
        "messages": _messages_from_input(input_json.get("messages")),
    })
    out = await evaluator_node(state)
    new_evals = out.get("turn_evaluations") or []
    latest = dict(new_evals[-1]) if new_evals else {}
    return {
        "evaluation": latest,
        "candidate_profile": dict(out.get("candidate_profile") or {}),
    }


async def _call_followup(input_json: dict[str, Any]) -> dict[str, Any]:
    """评估 interviewer.followup_node 追问质量。

    input_json 关心字段：
        followup_focus (str)
        turn_evaluations (list[dict])  至少含最新一条的 latent_signals / missing_dimensions
        messages (list[{"role", "content"}])
        target_role / target_company / user_background (str)
        followup_count (int)
    """
    state = cast(InterviewState, {
        **input_json,
        "messages": _messages_from_input(input_json.get("messages")),
    })
    out = await followup_node(state)
    return {"followup_text": out.get("assistant_message", "")}


async def _call_review(input_json: dict[str, Any]) -> dict[str, Any]:
    """评估 coach.review_node 复盘质量。

    input_json 关心字段：
        candidate_memory (dict)  含 latest_level / cumulative_signals / weakness_tags / total_sessions
        last_session_report (dict)  最近一场面试报告
    """
    state = cast(CoachState, {**input_json})
    out = await _coach_review_node(state)
    return {"review_text": out.get("review_text", "")}


async def _call_plan(input_json: dict[str, Any]) -> dict[str, Any]:
    """评估 coach.plan_node 训练计划质量。

    input_json 关心字段：
        review_text (str)  上一步复盘文本（独立评 plan 时必须自带）
        candidate_memory (dict)
    """
    state = cast(CoachState, {**input_json})
    out = await _coach_plan_node(state)
    return {"plan": out.get("plan_json") or {}}


SYSTEM_CALLS: dict[TargetType, SystemCall] = {
    TargetType.QUESTION: _call_question,
    TargetType.SCORING: _call_scoring,
    TargetType.FOLLOWUP: _call_followup,
    TargetType.REVIEW: _call_review,
    TargetType.PLAN: _call_plan,
}


async def dispatch_system_call(
    target_type: TargetType, input_json: dict[str, Any]
) -> dict[str, Any]:
    """根据 target_type 路由到对应 Agent 节点 adapter。

    未注册的 target_type 抛 ValueError —— 不允许静默兜底返回空 dict，
    否则 eval 跑完 judge 仍会给出"看起来正常"的分数，掩盖配置错误。
    """
    call = SYSTEM_CALLS.get(target_type)
    if call is None:
        raise ValueError(
            f"No system_call adapter for target_type={target_type!r}. "
            f"Registered: {sorted(t.value for t in SYSTEM_CALLS)}"
        )
    return await call(input_json)
