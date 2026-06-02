"""用户看板统计服务。"""
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import InterviewSession, CandidateMemory
from app.schemas.user import DashboardData, RadarData, GrowthPoint, WeaknessTag


async def get_user_dashboard_data(db: AsyncSession, user_id: str) -> DashboardData:
    """聚合用户面试表现的看板数据。"""
    # 1. 获取长期记忆基础信息
    mem_result = await db.execute(select(CandidateMemory).where(CandidateMemory.user_id == user_id))
    mem = mem_result.scalar_one_or_none()
    
    # 直接通过 InterviewSession 表统计面试次数，而不是依赖可能延迟生成的 CandidateMemory
    # 仅统计已完成且有评分的场次
    count_stmt = (
        select(func.count(InterviewSession.id))
        .where(
            InterviewSession.user_id == user_id,
            InterviewSession.status == "completed",
            InterviewSession.score.is_not(None)
        )
    )
    count_res = await db.execute(count_stmt)
    total_sessions = count_res.scalar() or 0
    
    # 2. 获取所有已完成会话用于计算时长和平均分
    all_sessions_result = await db.execute(
        select(InterviewSession)
        .where(
            InterviewSession.user_id == user_id,
            InterviewSession.status == "completed",
            InterviewSession.score.is_not(None)
        )
        .order_by(InterviewSession.completed_at.asc())
    )
    all_sessions = all_sessions_result.scalars().all()
    
    total_duration_hours = 0.0
    scores_sum = 0.0
    valid_count = len(all_sessions)
    
    for s in all_sessions:
        if s.completed_at and s.started_at:
            delta = s.completed_at - s.started_at
            total_duration_hours += delta.total_seconds() / 3600
        scores_sum += float(s.score or 0.0)

    avg_score = round(scores_sum / valid_count, 1) if valid_count > 0 else 0.0
    
    # 3. 成长轨迹 (取最后 10 场)
    growth_trajectory = []
    # session_index 使用其在所有已完成 session 中的序号
    for i, s in enumerate(all_sessions[-10:]):
        growth_trajectory.append(GrowthPoint(
            session_index=max(0, valid_count - 10) + i + 1,
            score=float(s.score or 0.0)
        ))
        
    # 4. 雷达图 (取最近 5 场平均值)
    radar = RadarData()
    recent_5 = all_sessions[-5:]
    if recent_5:
        r_depth, r_results, r_tradeoffs, r_struct = 0.0, 0.0, 0.0, 0.0
        count = 0
        for s in recent_5:
            if s.report_json and isinstance(s.report_json, dict):
                r_depth += float(s.report_json.get("technical_depth", 0))
                r_results += float(s.report_json.get("quantified_results", 0))
                r_tradeoffs += float(s.report_json.get("failure_tradeoffs", 0))
                r_struct += float(s.report_json.get("structure", 0))
                count += 1
        if count > 0:
            radar.technical_depth = round(r_depth / count, 1)
            radar.quantified_results = round(r_results / count, 1)
            radar.failure_tradeoffs = round(r_tradeoffs / count, 1)
            radar.structure = round(r_struct / count, 1)

    # 5. 薄弱项与改进数
    weaknesses = []
    improved_count = 0
    if mem and mem.weakness_tags:
        # 按出现次数降序
        sorted_tags = sorted(mem.weakness_tags, key=lambda x: x.get("count", 0), reverse=True)
        for t in sorted_tags[:7]:  # 最多取 7 个展示
            count = t.get("count", 0)
            # 简单判定：出现 3 次以上为 severe，2 次为 warn，1 次为 info
            severity = "severe" if count >= 3 else ("warn" if count >= 2 else "info")
            weaknesses.append(WeaknessTag(tag=t["tag"], severity=severity))
        
        # 简单逻辑：如果某些 tag 出现过但最近 3 场没出现，算作“可能已改善” (示例逻辑，暂取 count > 5 的数量 / 2 作为 Mock)
        improved_count = sum(1 for t in mem.weakness_tags if t.get("count", 0) > 2)

    return DashboardData(
        session_count=total_sessions,
        total_duration_hours=round(total_duration_hours, 1),
        average_score=avg_score,
        weaknesses_improved_count=improved_count,
        radar=radar,
        growth_trajectory=growth_trajectory,
        weaknesses=weaknesses
    )
