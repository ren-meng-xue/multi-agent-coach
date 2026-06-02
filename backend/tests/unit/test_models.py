"""验证当前 ORM 表在 SQLAlchemy metadata 中正确注册。"""
from app.db.base import Base
from app.models import register_models

# 触发模型导入，否则 Base.metadata 中没有表
register_models()


def test_users_table_registered():
    """确保核心业务表被 SQLAlchemy 发现。"""
    table_names = set(Base.metadata.tables.keys())
    assert table_names == {
        # 业务表
        "users",
        "interview_sessions",
        "interview_messages",
        "candidate_memory",
        "coach_plans",
        "user_qa_bank",
        # 评估系统表（phase4-parallel-eval）
        "eval_suites",
        "eval_cases",
        "eval_runs",
        "eval_results",
        "eval_comparisons",
    }


def test_users_table_columns():
    """确保 users 表只保留当前登录链路需要的基础字段。"""
    from app.models.core import User

    cols = {c.name for c in User.__table__.columns}
    assert cols == {"id", "email", "target_role", "work_years", "resume_text", "resume_filename", "resume_summary", "created_at"}


def test_interview_sessions_table_columns():
    """确保面试 Session 表包含状态机和用户上下文字段。"""
    from app.models.core import InterviewSession

    cols = {c.name for c in InterviewSession.__table__.columns}
    assert cols == {
        "id",
        "user_id",
        "status",
        "stage",
        "target_role",
        "target_company",
        "user_background",
        "total_questions",
        "question_count",
        "followup_count",
        "started_at",
        "completed_at",
        "score",
        "pass_fail",
        "key_issues",
        "report_json",
        "use_qa_bank",
    }


def test_interview_messages_table_columns():
    """确保面试消息表包含恢复上下文所需字段。"""
    from app.models.core import InterviewMessage

    cols = {c.name for c in InterviewMessage.__table__.columns}
    assert cols == {
        "id",
        "session_id",
        "role",
        "content",
        "question_number",
        "is_followup",
        "turn_trace_json",
        "created_at",
    }
