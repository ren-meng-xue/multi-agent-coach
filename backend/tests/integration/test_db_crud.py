"""数据层 CRUD 冒烟测试：验证 User 模型的基本增删查操作。"""
import pytest
from sqlalchemy import select

from app.models.core import User


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
