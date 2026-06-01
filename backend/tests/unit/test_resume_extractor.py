import pytest

from app.services.resume_extractor import (
    extract_target_role_from_resume,
    extract_target_role_locally,
)


def test_extract_target_role_locally_from_explicit_resume_field():
    resume_text = """
    任孟雪
    求职意向：高级前端工程师
    项目经历：负责 React 与性能优化。
    """

    assert extract_target_role_locally(resume_text) == "高级前端工程师"


def test_extract_target_role_locally_from_filename():
    assert extract_target_role_locally("", "任孟雪WEB前端工程师.pdf") == "WEB前端工程师"


@pytest.mark.asyncio
async def test_extract_target_role_from_resume_uses_local_match_before_llm():
    resume_text = "目标岗位：后端开发工程师\n熟悉 Python、PostgreSQL 与 Redis。"

    assert await extract_target_role_from_resume(resume_text) == "后端开发工程师"
