"""验证当前 ORM 表在 SQLAlchemy metadata 中正确注册。"""
from app.db.base import Base
from app.models import register_models

# 触发模型导入，否则 Base.metadata 中没有表
register_models()


def test_users_table_registered():
    """确保当前保留的 users 表被 SQLAlchemy 发现。"""
    table_names = set(Base.metadata.tables.keys())
    assert table_names == {"users"}


def test_users_table_columns():
    """确保 users 表只保留当前登录链路需要的基础字段。"""
    from app.models.core import User

    cols = {c.name for c in User.__table__.columns}
    assert cols == {"id", "email", "created_at"}
