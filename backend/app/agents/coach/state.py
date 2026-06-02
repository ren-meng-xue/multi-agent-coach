"""教练 Agent 的状态定义。"""
from typing import Any, TypedDict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


class CoachState(TypedDict):
    # 输入字段
    user_id: str
    session_id: UUID
    db: AsyncSession  # 用于持久化
    
    # 派生/中间字段
    candidate_memory: dict[str, Any] | None
    last_session_report: dict[str, Any] | None
    target_role: str | None
    
    # 输出字段
    review_text: str
    plan_json: dict[str, Any] | None
    plan_id: UUID | None
