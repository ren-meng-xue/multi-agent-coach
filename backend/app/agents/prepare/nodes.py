# backend/app/agents/prepare/nodes.py
"""Node functions for the prepare pipeline."""
from __future__ import annotations

from typing import Any

from app.agents.prepare.state import PrepareState
from app.core.logging import get_logger

log = get_logger("app.agents.prepare.nodes")


# ─────────────────────────────────────────────
# 内部 DB 查询助手
# ─────────────────────────────────────────────

async def _get_recent_sessions(user_id: str, limit: int = 5) -> list[Any]:
    """读取用户最近 N 场面试 session（含 report_json 字段）。"""
    from sqlalchemy import desc, select

    from app.db.session import async_session_factory
    from app.models.core import InterviewSession

    async with async_session_factory() as db:
        result = await db.execute(
            select(InterviewSession)
            .where(InterviewSession.user_id == user_id)
            .order_by(desc(InterviewSession.started_at))
            .limit(limit)
        )
        return list(result.scalars().all())


async def _get_user_stories(user_id: str) -> list[Any]:
    """读取用户故事库。"""
    from sqlalchemy import select

    from app.db.session import async_session_factory
    from app.models.core import UserStory

    async with async_session_factory() as db:
        result = await db.execute(
            select(UserStory).where(UserStory.user_id == user_id)
        )
        return list(result.scalars().all())


def _extract_weak_areas(sessions: list[Any]) -> list[str]:
    """从历史 session report 提取薄弱点描述。"""
    weak = []
    for s in sessions:
        # 避免 MagicMock 默认生成属性的坑，只接受真正的 dict 属性
        report_json = getattr(s, "report_json", None)
        if isinstance(report_json, dict):
            report = report_json
        else:
            report_val = getattr(s, "report", None)
            report = report_val if isinstance(report_val, dict) else {}

        if report.get("technical_depth", 5) <= 2:
            weak.append("技术深度不足")
        if report.get("quantified_results", 5) <= 2:
            weak.append("量化结果欠缺")
        if report.get("failure_tradeoffs", 5) <= 2:
            weak.append("失败/降级处理薄弱")
        if report.get("structure", 5) <= 2:
            weak.append("表达结构不清晰")
        for item in report.get("improvements", []):
            if item not in weak:
                weak.append(item)
    return list(dict.fromkeys(weak))  # 去重保序


# ─────────────────────────────────────────────
# memory_search_node
# ─────────────────────────────────────────────

async def memory_search_node(state: PrepareState) -> PrepareState:
    """查询历史面试表现和故事库，填充 weak_areas + star_stories。"""
    user_id = state.get("user_id", "")
    if not user_id:
        return {**state, "weak_areas": [], "star_stories": []}

    sessions = await _get_recent_sessions(user_id)
    stories = await _get_user_stories(user_id)

    weak_areas = _extract_weak_areas(sessions)
    star_stories = [
        {
            "title": s.title,
            "role": s.role or "",
            "tags": s.tags or [],
            "content_json": s.content_json or {},
        }
        for s in stories
    ]

    log.info(
        "memory_search_done",
        user_id=user_id,
        weak_count=len(weak_areas),
        story_count=len(star_stories),
    )
    return {**state, "weak_areas": weak_areas, "star_stories": star_stories}
