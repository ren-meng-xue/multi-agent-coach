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


class UserStoryBase(BaseModel):
    """故事库基础字段。"""
    title: str
    role: str | None = None
    tags: list[str] | None = None
    content_json: dict = Field(default_factory=dict)


class UserStoryCreate(UserStoryBase):
    """创建故事的请求。"""
    pass


class UserStoryUpdate(BaseModel):
    """更新故事的请求。"""
    title: str | None = None
    role: str | None = None
    tags: list[str] | None = None
    content_json: dict | None = None


class UserStory(UserStoryBase):
    """故事库完整模型。"""
    id: UUID
    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserStoryList(BaseModel):
    """故事列表响应。"""
    stories: list[UserStory]


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
