"""验证 CandidateMemory 和 CoachPlan 模型。"""
from app.db.base import Base
from app.models import register_models

# 触发模型导入
register_models()

def test_new_tables_registered():
    """确保新增的表被 SQLAlchemy 发现。"""
    table_names = set(Base.metadata.tables.keys())
    assert "candidate_memory" in table_names
    assert "coach_plans" in table_names

def test_candidate_memory_fields():
    """验证 CandidateMemory 模型的字段。"""
    from app.models.core import CandidateMemory
    
    cols = {c.name for c in CandidateMemory.__table__.columns}
    expected = {
        "user_id",
        "latest_level",
        "cumulative_signals",
        "weakness_tags",
        "last_session_id",
        "total_sessions",
        "updated_at",
    }
    assert expected.issubset(cols)

def test_coach_plan_fields():
    """验证 CoachPlan 模型的字段。"""
    from app.models.core import CoachPlan
    
    cols = {c.name for c in CoachPlan.__table__.columns}
    expected = {
        "id",
        "user_id",
        "session_id",
        "plan_json",
        "consumed",
        "created_at",
    }
    assert expected.issubset(cols)
