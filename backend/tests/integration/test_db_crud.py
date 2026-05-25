"""数据层 CRUD 冒烟测试：验证 User 模型的基本增删查操作。"""
import pytest
from sqlalchemy import select

from app.models.core import InterviewMessage, InterviewSession, User


@pytest.mark.asyncio
async def test_create_and_select_user(db):
    """创建用户后能通过 email 查询到。"""
    u = User(id="user_test01abc", email="test+d1@example.com")
    db.add(u)
    await db.flush()
    assert u.id == "user_test01abc"

    result = await db.execute(select(User).where(User.email == "test+d1@example.com"))
    fetched = result.scalar_one()
    assert fetched.id == "user_test01abc"


@pytest.mark.asyncio
async def test_create_interview_session_and_message(db):
    """创建 Session 与消息后能按 session_id 查询恢复上下文。"""
    user = User(id="user_interview01", email="test+interview@example.com")
    session = InterviewSession(
        user_id=user.id,
        target_role="AI Agent 工程师",
        target_company="字节跳动",
        user_background="做过一个多 Agent 面试教练项目",
    )
    db.add_all([user, session])
    await db.flush()

    message = InterviewMessage(
        session_id=session.id,
        role="assistant",
        content="请介绍你做过的 LangGraph 项目。",
        question_number=1,
    )
    db.add(message)
    await db.flush()

    result = await db.execute(
        select(InterviewMessage).where(InterviewMessage.session_id == session.id)
    )
    fetched = result.scalar_one()
    assert fetched.content == "请介绍你做过的 LangGraph 项目。"
    assert fetched.is_followup is False
