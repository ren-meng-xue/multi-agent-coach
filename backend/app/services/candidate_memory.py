"""候选人长期记忆服务。"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import CandidateMemory


async def upsert_candidate_memory(
    db: AsyncSession,
    user_id: str,
    *,
    latest_level: str | None,
    latent_signals: list[str],
    weakness_tags: list[str],
    session_id: UUID | None,
) -> CandidateMemory:
    """
    更新或创建候选人的长期记忆。
    
    逻辑：
    1. 合并 cumulative_signals：去重、保序、上限 50 条 (FIFO)。
    2. 合并 weakness_tags：增加 count，更新 last_seen_at。
    3. 更新 latest_level, last_session_id, total_sessions。
    """
    # 1. 获取现有记忆
    stmt = select(CandidateMemory).where(CandidateMemory.user_id == user_id)
    result = await db.execute(stmt)
    mem = result.scalar_one_or_none()
    
    now = datetime.now()
    
    if not mem:
        # 创建新记录
        # 处理初始 signals
        unique_signals = []
        for s in latent_signals:
            if s not in unique_signals:
                unique_signals.append(s)
        
        # 处理初始 weakness_tags
        initial_tags = []
        for tag in weakness_tags:
            initial_tags.append({
                "tag": tag,
                "count": 1,
                "last_seen_at": now.isoformat()
            })
            
        mem = CandidateMemory(
            user_id=user_id,
            latest_level=latest_level,
            cumulative_signals=unique_signals[:50],
            weakness_tags=initial_tags,
            last_session_id=session_id,
            total_sessions=1,
        )
        db.add(mem)
    else:
        # 更新现有记录
        # a. 更新基本信息
        if latest_level:
            mem.latest_level = latest_level
        
        # 只有当 session_id 发生变化时才增加总场次计数
        if session_id and mem.last_session_id != session_id:
            mem.total_sessions += 1
            mem.last_session_id = session_id
        
        # b. 合并信号 (去重保序)
        new_signals = list(mem.cumulative_signals)
        for s in latent_signals:
            if s not in new_signals:
                new_signals.append(s)
        
        # FIFO 上限 50
        if len(new_signals) > 50:
            new_signals = new_signals[-50:]
        mem.cumulative_signals = new_signals
        
        # c. 合并弱点标签
        existing_tags = {t["tag"]: t for t in mem.weakness_tags}
        for tag_name in weakness_tags:
            if tag_name in existing_tags:
                existing_tags[tag_name]["count"] += 1
                existing_tags[tag_name]["last_seen_at"] = now.isoformat()
            else:
                existing_tags[tag_name] = {
                    "tag": tag_name,
                    "count": 1,
                    "last_seen_at": now.isoformat()
                }
        mem.weakness_tags = list(existing_tags.values())
        
    await db.commit()
    await db.refresh(mem)
    return mem
