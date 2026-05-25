from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """用户基本配置。"""
    id: str
    email: str
    target_role: str | None = None
    work_years: str | None = None

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    """更新用户配置的请求。"""
    target_role: str | None = None
    work_years: str | None = None


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
