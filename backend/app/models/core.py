"""M2 阶段 7 张核心业务表：用户、RAG 题库、用户画像、面试场次、对话记录、STAR 故事、弱点标签。"""
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    UUID,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class User(Base):
    """用户表：Clerk user_id 为主键（VARCHAR，如 user_2abcDEF...）。"""

    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RagChunk(Base):
    """RAG 题库文档块：爬取的文档分片 + OpenAI embedding 向量。"""

    __tablename__ = "rag_chunks"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    source: Mapped[str] = mapped_column(String(100))
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UserProfile(Base):
    """用户长期画像（L2 记忆）：技术强弱项、STAR 完成度、面试历史摘要。"""

    __tablename__ = "user_profile"
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), primary_key=True)
    goals: Mapped[str | None] = mapped_column(Text, nullable=True)
    experience_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tech_strengths: Mapped[dict] = mapped_column(JSONB, default=dict)
    tech_weaknesses: Mapped[dict] = mapped_column(JSONB, default=dict)
    soft_strengths: Mapped[dict] = mapped_column(JSONB, default=dict)
    star_completeness_score: Mapped[float] = mapped_column(Float, default=0.0)
    total_interviews: Mapped[int] = mapped_column(Integer, default=0)
    history: Mapped[list] = mapped_column(JSONB, default=list)
    profile_embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InterviewSession(Base):
    """面试场次：一次多 Agent 面试的完整记录。"""

    __tablename__ = "interview_session"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    phase_completed: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class InterviewMessage(Base):
    """对话消息：面试中每一轮问答，可附带 Reflexion 评分。"""

    __tablename__ = "interview_message"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_session.id")
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    retrieved_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reflexion_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class StarStory(Base):
    """STAR 故事库（L3 记忆）：用户项目经历的 S/T/A/R 结构化抽取。"""

    __tablename__ = "star_stories"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"))
    project_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    situation: Mapped[str | None] = mapped_column(Text, nullable=True)
    task: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantified_results: Mapped[str | None] = mapped_column(Text, nullable=True)
    tech_stack: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_message.id"), nullable=True
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WeaknessTag(Base):
    """弱点标签（L4 记忆）：用户反复出错的技能维度及严重程度。"""

    __tablename__ = "weakness_tags"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"))
    tag: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(50))
    severity: Mapped[float] = mapped_column(Float)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    last_occurred_session: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    related_message_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
