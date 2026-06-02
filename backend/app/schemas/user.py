from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """用户基本配置。"""
    id: str
    email: str
    target_role: str | None = None
    resume_filename: str | None = None
    resume_text: str | None = None
    evaluation: str | None = None
    total_sessions: int = 0

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    """更新用户配置的请求。"""
    target_role: str | None = None


class RadarData(BaseModel):
    """能力雷达数据。"""
    technical_depth: float = 0.0
    quantified_results: float = 0.0
    failure_tradeoffs: float = 0.0
    structure: float = 0.0


class GrowthPoint(BaseModel):
    """成长轨迹数据点。"""
    session_index: int
    score: float


class WeaknessTag(BaseModel):
    """薄弱项标签。"""
    tag: str
    severity: str  # severe, warn, info


class DashboardData(BaseModel):
    """Dashboard 看板聚合数据。"""
    session_count: int = 0
    total_duration_hours: float = 0.0
    average_score: float = 0.0
    weaknesses_improved_count: int = 0
    radar: RadarData = Field(default_factory=RadarData)
    growth_trajectory: list[GrowthPoint] = Field(default_factory=list)
    weaknesses: list[WeaknessTag] = Field(default_factory=list)
