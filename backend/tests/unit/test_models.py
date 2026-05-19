"""验证 7 张业务表在 SQLAlchemy metadata 中正确注册，向量和 JSONB 字段类型正确。"""
from app.db.base import Base
from app.models import register_models

# 触发模型导入，否则 Base.metadata 中没有表
register_models()


def test_seven_tables_registered():
    """确保 7 张表都被 SQLAlchemy 发现。"""
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "users",
        "rag_chunks",
        "user_profile",
        "interview_session",
        "interview_message",
        "star_stories",
        "weakness_tags",
    }
    assert expected.issubset(table_names), f"missing: {expected - table_names}"


def test_rag_chunks_has_vector_column():
    """RAG 文档块必须有 embedding 向量列和 metadata JSONB 列。"""
    from app.models.core import RagChunk

    cols = {c.name for c in RagChunk.__table__.columns}
    assert "embedding" in cols
    assert "metadata" in cols


def test_user_profile_has_history_jsonb():
    """用户画像必须有 history JSONB 列和 profile_embedding 向量列。"""
    from app.models.core import UserProfile

    cols = {c.name: c.type.__class__.__name__ for c in UserProfile.__table__.columns}
    assert "history" in cols
    assert "profile_embedding" in cols
