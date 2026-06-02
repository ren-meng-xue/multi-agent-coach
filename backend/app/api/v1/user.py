import io
from uuid import UUID

import PyPDF2
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.core.exceptions import BadRequestException
from app.db.session import get_db
from app.models.core import (
    CandidateMemory,
    CoachPlan,
    InterviewSession,
)
from app.schemas.response import Response
from app.schemas.user import (
    DashboardData,
    UserProfile,
    UserProfileUpdate,
)
from app.services.coach_opening import invalidate_coach_opening_cache
from app.services.interview_turn import ensure_user_exists
from app.services.resume_extractor import (
    extract_target_role_from_resume,
    extract_target_role_locally,
)
from app.services.user_stage import derive_user_stage
from app.services.user_stats import get_user_dashboard_data

router = APIRouter(prefix="/user")


@router.post("/resume", response_model=Response[UserProfile])
async def upload_resume(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """上传并解析简历。"""
    user = await ensure_user_exists(db, user_id=user_id)

    filename = file.filename or "resume.pdf"
    content = await file.read()

    text_content = ""
    if filename.lower().endswith(".pdf"):
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
            for page in pdf_reader.pages:
                text_content += page.extract_text() + "\n"
        except Exception as e:
            raise BadRequestException(f"PDF 解析失败: {str(e)}") from e
    elif filename.lower().endswith((".txt", ".md")):
        try:
            text_content = content.decode("utf-8")
        except UnicodeDecodeError as e:
            raise BadRequestException("文件编码不正确，请使用 UTF-8") from e
    else:
        raise BadRequestException("仅支持 PDF, TXT 或 MD 格式")

    if not text_content.strip():
        raise BadRequestException("简历内容为空或解析失败")

    user.resume_text = text_content
    user.resume_filename = filename

    # [Sync] 自动提取并同步目标岗位
    try:
        extracted_role = await extract_target_role_from_resume(text_content, filename=filename)
        if extracted_role:
            user.target_role = extracted_role
    except Exception:
        # 提取失败不阻塞简历上传
        pass

    await db.commit()
    await db.refresh(user)

    # 简历更新，让 Coach 开场词缓存失效
    await invalidate_coach_opening_cache(user_id)

    return Response.ok(data=UserProfile.model_validate(user))

@router.post("/resume/extract-role", response_model=Response[UserProfile])
async def extract_resume_role(
    save: bool = True,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """从简历中自动提取目标岗位。"""
    user = await ensure_user_exists(db, user_id=user_id)
    if not user.resume_text:
        raise BadRequestException("请先上传简历，解析后才能提取岗位。")

    target_role = await extract_target_role_from_resume(
        user.resume_text,
        filename=user.resume_filename,
    )
    
    if save and target_role:
        user.target_role = target_role
        await db.commit()
        await db.refresh(user)
    
    return Response.ok(data=UserProfile.model_validate(user))


@router.delete("/resume", response_model=Response[UserProfile])
async def delete_resume(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """删除简历。"""
    user = await ensure_user_exists(db, user_id=user_id)
    user.resume_text = None
    user.resume_filename = None
    await db.commit()
    await db.refresh(user)
    
    # 简历删除，让 Coach 开场词缓存失效
    await invalidate_coach_opening_cache(user_id)
    
    return Response.ok(data=UserProfile.model_validate(user))


@router.get("/dashboard", response_model=Response[DashboardData])
async def get_dashboard(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """获取用户的 Dashboard 看板数据。"""
    data = await get_user_dashboard_data(db, user_id=user_id)
    return Response.ok(data=data)


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
    """获取当前用户的个人配置。优先使用持久化配置，回退至最近 session 的记忆。"""
    user = await ensure_user_exists(db, user_id=user_id)
    profile = UserProfile.model_validate(user)
    
    # 注入面试总场次 (实时从 InterviewSession 表统计已完成且有评分的场次)
    count_stmt = (
        select(func.count(InterviewSession.id))
        .where(
            InterviewSession.user_id == user_id,
            InterviewSession.status == "completed",
            InterviewSession.score.is_not(None)
        )
    )
    count_res = await db.execute(count_stmt)
    profile.total_sessions = count_res.scalar() or 0

    resume_text = user.resume_text if isinstance(user.resume_text, str) else ""
    resume_filename = user.resume_filename if isinstance(user.resume_filename, str) else None
    if not profile.target_role and resume_text:
        target_role = extract_target_role_locally(resume_text, resume_filename)
        if target_role:
            profile.target_role = target_role

    # 如果持久化配置为空，尝试从最近 session 捞取（即“记忆”逻辑）
    if not profile.target_role:
        latest_result = await db.execute(
            select(InterviewSession.target_role)
            .where(
                InterviewSession.user_id == user_id,
                InterviewSession.target_role.is_not(None),
                InterviewSession.target_role != "",
            )
            .order_by(InterviewSession.started_at.desc())
            .limit(1)
        )
        profile.target_role = latest_result.scalar_one_or_none()

    # 注入评价
    mem_result = await db.execute(select(CandidateMemory).where(CandidateMemory.user_id == user_id))
    mem = mem_result.scalar_one_or_none()
    
    if mem:
        # 获取最近一次教练计划中的 summary 作为评价
        plan_result = await db.execute(
            select(CoachPlan)
            .where(CoachPlan.user_id == user_id)
            .order_by(CoachPlan.created_at.desc())
            .limit(1)
        )
        latest_plan = plan_result.scalar_one_or_none()
        if latest_plan and isinstance(latest_plan.plan_json, dict) and "summary" in latest_plan.plan_json:
            profile.evaluation = latest_plan.plan_json["summary"]
        else:
            profile.evaluation = "已开启面试旅程，完成首场面试后将生成 AI 评价。"
    else:
        profile.evaluation = "欢迎开启 Coach 模拟面试！设置目标岗位后，点击开始面试，AI 将为你生成首份评价。"
        
    return Response.ok(data=profile)


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
        
    await db.commit()
    await db.refresh(user)
    return Response.ok(data=UserProfile.model_validate(user))
