"""导入所有模型以便 Alembic 和 SQLAlchemy 发现。"""


def register_models() -> None:
    """确保所有 ORM 模型被导入，Alembic autogenerate 才能检测到。"""
    from app.models import (
        core,  # noqa: F401
        qa_bank,  # noqa: F401
    )
    from app.models import eval as _eval_models  # noqa: F401
