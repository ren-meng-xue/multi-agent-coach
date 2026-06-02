"""教练 Agent 子图的节点函数。"""
import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from app.agents.coach.prompts import COACH_PLAN_SYSTEM_PROMPT, COACH_REVIEW_SYSTEM_PROMPT
from app.agents.coach.state import CoachState
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.core import CandidateMemory, CoachPlan, InterviewSession, User

log = get_logger("app.agents.coach.nodes")

# ─────────────────────────────────────────────
# 辅助函数与模型
# ─────────────────────────────────────────────

def _chat_model(streaming: bool = False) -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.openai_model_chat,
        api_key=settings.openai_api_key,
        timeout=settings.llm_timeout_seconds,
        streaming=streaming,
    )

class CoachPlanSchema(BaseModel):
    """结构化训练计划的 Pydantic 模型。"""
    summary: str = Field(description="一句话总结本次面试最核心的结论")
    strengths: list[str] = Field(description="2-3 条具体的、有引证的亮点")
    weaknesses: list[str] = Field(description="2-3 条具体的、亟需改进的短板")
    next_focus_areas: list[str] = Field(description="下次面试要重点练习的方向")
    recommended_role: str | None = Field(description="推荐下一场练习什么岗位")
    recommended_question_types: list[str] = Field(description="推荐题型")

# ─────────────────────────────────────────────
# LLM 封装
# ─────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
async def _generate_review_text(state: CoachState) -> str:
    """生成复盘叙事文本。"""
    model = _chat_model(streaming=True).with_config(tags=["coach_review_stream"])
    
    memory_ctx = f"【候选人长期记忆】\n{json.dumps(state['candidate_memory'], ensure_ascii=False)}"
    session_ctx = (
        f"【最近一场面试表现】\n"
        f"岗位：{state['target_role'] or '未指定'}\n"
        f"报告内容：{json.dumps(state['last_session_report'], ensure_ascii=False)}"
    )
    resume_ctx = (
        f"\n\n【候选人简历摘要】\n{state['resume_summary']}"
        if state.get("resume_summary") else ""
    )

    # 模拟 astream 以便 SSE 捕获 tokens
    full_text = []
    messages = [
        SystemMessage(content=COACH_REVIEW_SYSTEM_PROMPT),
        HumanMessage(content=f"{memory_ctx}\n\n{session_ctx}{resume_ctx}"),
    ]
    async for chunk in model.astream(messages):
        content = chunk.content
        if isinstance(content, str):
            full_text.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, str):
                    full_text.append(part)
                elif isinstance(part, dict) and "text" in part:
                    full_text.append(str(part["text"]))
    return "".join(full_text)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
async def _generate_structured_plan(state: CoachState) -> CoachPlanSchema:
    """生成结构化训练计划。"""
    model = _chat_model().with_structured_output(CoachPlanSchema)
    
    review_ctx = f"【复盘总结】\n{state['review_text']}"
    memory_ctx = f"【候选人长期画像】\n{json.dumps(state['candidate_memory'], ensure_ascii=False)}"
    role_ctx = f"【本次练习岗位】\n{state['target_role'] or '未指定'}"
    resume_ctx = (
        f"\n\n【候选人简历摘要】\n{state['resume_summary']}"
        if state.get("resume_summary") else ""
    )

    messages = [
        SystemMessage(content=COACH_PLAN_SYSTEM_PROMPT),
        HumanMessage(content=f"{role_ctx}\n\n{review_ctx}\n\n{memory_ctx}{resume_ctx}"),
    ]
    
    result = await model.ainvoke(messages)
    if isinstance(result, CoachPlanSchema):
        return result
    raise ValueError("LLM failed to produce CoachPlanSchema")

# ─────────────────────────────────────────────
# 节点函数
# ─────────────────────────────────────────────

async def load_memory_node(state: CoachState) -> dict[str, Any]:
    """节点 1: 从 DB 加载长期记忆和最近面试报告。"""
    db = state["db"]
    user_id = state["user_id"]
    session_id = state["session_id"]
    
    # 1. 统计面试总场次 (仅统计已完成且有评分的)
    count_stmt = (
        select(func.count(InterviewSession.id))
        .where(
            InterviewSession.user_id == user_id,
            InterviewSession.status == "completed",
            InterviewSession.score.is_not(None)
        )
    )
    count_res = await db.execute(count_stmt)
    total_sessions = count_res.scalar() or 0

    # 2. 加载长期记忆
    stmt_mem = select(CandidateMemory).where(CandidateMemory.user_id == user_id)
    res_mem = await db.execute(stmt_mem)
    mem_row = res_mem.scalar_one_or_none()
    
    candidate_memory = {}
    if mem_row:
        candidate_memory = {
            "latest_level": mem_row.latest_level,
            "cumulative_signals": mem_row.cumulative_signals,
            "weakness_tags": mem_row.weakness_tags,
            "total_sessions": total_sessions,
        }
    else:
        candidate_memory = {
            "latest_level": None,
            "cumulative_signals": [],
            "weakness_tags": [],
            "total_sessions": total_sessions,
        }
    
    # 2. 加载最近面试报告与岗位
    stmt_session = select(InterviewSession).where(InterviewSession.id == session_id)
    res_session = await db.execute(stmt_session)
    session_row = res_session.scalar_one_or_none()
    
    last_session_report = session_row.report_json if session_row else {}
    target_role = session_row.target_role if session_row else None

    stmt_user = select(User.resume_summary).where(User.id == user_id)
    res_user = await db.execute(stmt_user)
    resume_summary = res_user.scalar_one_or_none()

    return {
        "candidate_memory": candidate_memory,
        "last_session_report": last_session_report,
        "target_role": target_role,
        "resume_summary": resume_summary,
    }

async def review_node(state: CoachState) -> dict[str, Any]:
    """节点 2: LLM 生成复盘叙事。"""
    try:
        review_text = await _generate_review_text(state)
        return {"review_text": review_text}
    except Exception as exc:
        log.error("coach_review_node_failed", error=str(exc))
        return {"review_text": "教练复盘生成失败，请稍后重试。"}

async def plan_node(state: CoachState) -> dict[str, Any]:
    """节点 3: LLM 生成结构化计划。"""
    try:
        plan = await _generate_structured_plan(state)
        return {"plan_json": plan.model_dump()}
    except Exception as exc:
        log.error("coach_plan_node_failed", error=str(exc))
        # 兜底计划
        fallback = {
            "summary": "面试已完成，但详细计划生成失败。",
            "strengths": [],
            "weaknesses": [],
            "next_focus_areas": ["建议继续复习基础知识"],
            "recommended_role": None,
            "recommended_question_types": []
        }
        return {"plan_json": fallback}

async def persist_node(state: CoachState) -> dict[str, Any]:
    """节点 4: 持久化计划到 DB。"""
    db = state["db"]
    user_id = state["user_id"]
    session_id = state["session_id"]
    plan_json = state["plan_json"]

    if not plan_json:
        return {"plan_id": None}

    try:
        # 幂等检查：如果 session_id 已有 plan，则更新它
        stmt = select(CoachPlan).where(CoachPlan.session_id == session_id)
        result = await db.execute(stmt)
        existing_plan = result.scalar_one_or_none()

        if existing_plan:
            existing_plan.plan_json = plan_json
            existing_plan.consumed = False  # 重置消费状态，允许按新计划练习
            db.add(existing_plan)
            await db.commit()
            await db.refresh(existing_plan)
            log.info("coach_plan_updated", plan_id=existing_plan.id, user_id=user_id)
            return {"plan_id": existing_plan.id}

        new_plan = CoachPlan(
            user_id=user_id,
            session_id=session_id,
            plan_json=plan_json,
            consumed=False,
        )
        db.add(new_plan)
        await db.commit()
        await db.refresh(new_plan)

        log.info("coach_plan_persisted", plan_id=new_plan.id, user_id=user_id)
        return {"plan_id": new_plan.id}
    except Exception as exc:
        log.error("coach_persist_node_failed", error=str(exc))
        await db.rollback()
        return {"plan_id": None}
