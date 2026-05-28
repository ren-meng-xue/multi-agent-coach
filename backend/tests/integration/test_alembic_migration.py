"""验证 Alembic 迁移后的数据库结构。"""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_candidate_memory_table_exists(db: AsyncSession):
    """验证 candidate_memory 表在数据库中存在。"""
    # 检查表是否存在
    result = await db.execute(text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'candidate_memory')"
    ))
    assert result.scalar() is True

@pytest.mark.asyncio
async def test_coach_plans_table_exists(db: AsyncSession):
    """验证 coach_plans 表在数据库中存在。"""
    result = await db.execute(text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'coach_plans')"
    ))
    assert result.scalar() is True

@pytest.mark.asyncio
async def test_coach_plans_index_exists(db: AsyncSession):
    """验证 idx_coach_plans_user_unconsumed 索引存在。"""
    result = await db.execute(text(
        "SELECT EXISTS (SELECT FROM pg_indexes WHERE indexname = 'idx_coach_plans_user_unconsumed')"
    ))
    assert result.scalar() is True
