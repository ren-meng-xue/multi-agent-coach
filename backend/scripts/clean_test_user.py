import asyncio
import os
import sys

# 确保能找到 app 模块
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import get_settings

settings = get_settings()

async def clean():
    print(f"Connecting to database to clean dev user data...")
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        # 按外键依赖顺序删除
        await conn.execute(text("DELETE FROM interview_messages WHERE session_id IN (SELECT id FROM interview_sessions WHERE user_id = 'dev-auth-bypass-token')"))
        await conn.execute(text("DELETE FROM interview_sessions WHERE user_id = 'dev-auth-bypass-token'"))
        await conn.execute(text("DELETE FROM candidate_memory WHERE user_id = 'dev-auth-bypass-token'"))
        await conn.execute(text("DELETE FROM coach_plans WHERE user_id = 'dev-auth-bypass-token'"))
        await conn.execute(text("DELETE FROM user_qa_bank WHERE user_id = 'dev-auth-bypass-token'"))
        await conn.execute(text("DELETE FROM users WHERE id = 'dev-auth-bypass-token'"))
        print("Successfully cleaned all data for 'dev-auth-bypass-token'")

if __name__ == "__main__":
    asyncio.run(clean())
