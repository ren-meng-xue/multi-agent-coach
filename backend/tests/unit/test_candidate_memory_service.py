"""验证 CandidateMemory 服务的 upsert 逻辑。"""
from datetime import datetime

import pytest

from app.models.core import InterviewSession, User
from app.services.candidate_memory import upsert_candidate_memory


@pytest.fixture
async def test_user(db):
    """创建测试用户。"""
    user_id = f"user_test_{datetime.now().timestamp()}"
    user = User(id=user_id, email=f"test_{user_id}@example.com")
    db.add(user)
    await db.commit()
    return user

@pytest.fixture
async def test_session(db, test_user):
    """创建测试会话。"""
    session = InterviewSession(user_id=test_user.id, status="completed")
    db.add(session)
    await db.commit()
    return session

@pytest.mark.asyncio
async def test_upsert_creates_row_when_absent(db, test_user, test_session):
    """当记录不存在时，创建新记录。"""
    mem = await upsert_candidate_memory(
        db, test_user.id,
        latest_level="junior",
        latent_signals=["python", "fastapi"],
        weakness_tags=["quantification"],
        session_id=test_session.id
    )
    
    assert mem.user_id == test_user.id
    assert mem.latest_level == "junior"
    assert mem.cumulative_signals == ["python", "fastapi"]
    assert len(mem.weakness_tags) == 1
    assert mem.weakness_tags[0]["tag"] == "quantification"
    assert mem.weakness_tags[0]["count"] == 1
    assert mem.total_sessions == 1
    assert mem.last_session_id == test_session.id

@pytest.mark.asyncio
async def test_upsert_dedup_signals_preserve_order(db, test_user, test_session):
    """测试信号合并：去重并保持顺序。"""
    # 第一次 upsert
    await upsert_candidate_memory(
        db, test_user.id,
        latest_level="junior",
        latent_signals=["a", "b"],
        weakness_tags=[],
        session_id=test_session.id
    )
    
    # 第二次 upsert
    mem = await upsert_candidate_memory(
        db, test_user.id,
        latest_level="mid",
        latent_signals=["b", "c"],
        weakness_tags=[],
        session_id=test_session.id
    )
    
    # 期望结果：["a", "b", "c"]，且最新的信号在后面（或按原有顺序）
    # Spec 要求：跨 session 去重保序。
    assert mem.cumulative_signals == ["a", "b", "c"]
    assert mem.latest_level == "mid"
    assert mem.total_sessions == 1

@pytest.mark.asyncio
async def test_weakness_tag_count_increments(db, test_user, test_session):
    """测试短板标签计数累加。"""
    await upsert_candidate_memory(
        db, test_user.id,
        latest_level="junior",
        latent_signals=[],
        weakness_tags=["tag1", "tag2"],
        session_id=test_session.id
    )
    
    mem = await upsert_candidate_memory(
        db, test_user.id,
        latest_level="junior",
        latent_signals=[],
        weakness_tags=["tag1", "tag3"],
        session_id=test_session.id
    )
    
    tags = {t["tag"]: t for t in mem.weakness_tags}
    assert tags["tag1"]["count"] == 2
    assert tags["tag2"]["count"] == 1
    assert tags["tag3"]["count"] == 1
    # 验证时间更新
    assert "last_seen_at" in tags["tag1"]

@pytest.mark.asyncio
async def test_signals_capped_at_50_fifo(db, test_user, test_session):
    """测试信号上限 50 条，FIFO。"""
    # 构造 40 个信号
    signals_1 = [f"s{i}" for i in range(40)]
    await upsert_candidate_memory(
        db, test_user.id,
        latest_level="junior",
        latent_signals=signals_1,
        weakness_tags=[],
        session_id=test_session.id
    )
    
    # 再加 20 个新信号
    signals_2 = [f"s{i}" for i in range(30, 60)]
    mem = await upsert_candidate_memory(
        db, test_user.id,
        latest_level="junior",
        latent_signals=signals_2,
        weakness_tags=[],
        session_id=test_session.id
    )
    
    # 总共 60 个唯一信号，应保留后 50 个
    assert len(mem.cumulative_signals) == 50
    assert mem.cumulative_signals[0] == "s10"
    assert mem.cumulative_signals[-1] == "s59"
