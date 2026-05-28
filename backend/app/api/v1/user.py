from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.db.session import get_db
from app.models.core import UserStory as UserStoryModel
from app.schemas.response import Response
from app.schemas.user import (
    UserProfile,
    UserProfileUpdate,
    UserStory,
    UserStoryCreate,
    UserStoryList,
    UserStoryUpdate,
)
from app.services.interview_turn import ensure_user_exists
from app.services.user_stage import derive_user_stage

router = APIRouter(prefix="/user")


@router.get("/stage", response_model=Response[dict])
async def get_user_stage(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """获取用户当前所处的模拟面试阶段。"""
    stage = await derive_user_stage(db, user_id=user_id)
    return Response.ok(data={"stage": stage})


@router.get("/profile", response_model=Response[UserProfile])
async def get_profile(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的个人配置。"""
    user = await ensure_user_exists(db, user_id=user_id)
    return Response.ok(data=UserProfile.model_validate(user))


@router.patch("/profile", response_model=Response[UserProfile])
async def update_profile(
    req: UserProfileUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """更新当前用户的个人配置。"""
    user = await ensure_user_exists(db, user_id=user_id)
    
    if req.target_role is not None:
        user.target_role = req.target_role
    if req.work_years is not None:
        user.work_years = req.work_years
        
    await db.commit()
    await db.refresh(user)
    return Response.ok(data=UserProfile.model_validate(user))


@router.get("/stories", response_model=Response[UserStoryList])
async def list_stories(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户的所有故事。"""
    result = await db.execute(
        select(UserStoryModel)
        .where(UserStoryModel.user_id == user_id)
        .order_by(UserStoryModel.created_at.desc())
    )
    stories = result.scalars().all()
    return Response.ok(data=UserStoryList(stories=[UserStory.model_validate(s) for s in stories]))


@router.post("/stories", response_model=Response[UserStory])
async def create_story(
    req: UserStoryCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """为当前用户创建一个新故事。"""
    await ensure_user_exists(db, user_id=user_id)
    
    story = UserStoryModel(
        user_id=user_id,
        title=req.title,
        role=req.role,
        tags=req.tags,
        content_json=req.content_json,
    )
    db.add(story)
    await db.commit()
    await db.refresh(story)
    return Response.ok(data=UserStory.model_validate(story))


@router.patch("/stories/{story_id}", response_model=Response[UserStory])
async def update_story(
    story_id: UUID,
    req: UserStoryUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """更新指定故事的内容。"""
    result = await db.execute(
        select(UserStoryModel).where(
            UserStoryModel.id == story_id,
            UserStoryModel.user_id == user_id
        )
    )
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=404, detail="故事不存在")
        
    if req.title is not None:
        story.title = req.title
    if req.role is not None:
        story.role = req.role
    if req.tags is not None:
        story.tags = req.tags
    if req.content_json is not None:
        story.content_json = req.content_json
        
    await db.commit()
    await db.refresh(story)
    return Response.ok(data=UserStory.model_validate(story))


@router.delete("/stories/{story_id}", response_model=Response)
async def delete_story(
    story_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """删除指定故事。"""
    result = await db.execute(
        select(UserStoryModel).where(
            UserStoryModel.id == story_id,
            UserStoryModel.user_id == user_id
        )
    )
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=404, detail="故事不存在")
        
    await db.delete(story)
    await db.commit()
    return Response.ok()
