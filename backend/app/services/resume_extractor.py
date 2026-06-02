import logging
import re

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.core.config import get_settings


class TargetRoleExtraction(BaseModel):
    target_role: str = Field(description="The target job role inferred from the resume, e.g., 'Senior Java Engineer', 'Product Manager'. Empty string if unable to determine.")


ROLE_KEYWORDS = (
    "前端",
    "后端",
    "全栈",
    "客户端",
    "移动端",
    "安卓",
    "Android",
    "iOS",
    "Java",
    "Python",
    "Golang",
    "Go",
    "C++",
    "算法",
    "数据",
    "测试",
    "运维",
    "SRE",
    "DevOps",
    "AI",
    "机器学习",
    "深度学习",
    "产品",
    "项目",
    "运营",
    "设计",
    "UI",
    "UX",
)
ROLE_SUFFIXES = (
    "开发工程师",
    "工程师",
    "开发",
    "架构师",
    "经理",
    "专家",
    "实习生",
)
ROLE_PREFIX = r"(?:高级|资深|中级|初级|专家级|Senior|Junior|Web|WEB|web|AI|Java|Python)?"
ROLE_KEYWORD_PATTERN = "|".join(re.escape(keyword) for keyword in ROLE_KEYWORDS)
ROLE_SUFFIX_PATTERN = "|".join(re.escape(suffix) for suffix in ROLE_SUFFIXES)
ROLE_PATTERN = re.compile(
    rf"({ROLE_PREFIX}\s*(?:{ROLE_KEYWORD_PATTERN})[\w+#. /\-·（）()]*?(?:{ROLE_SUFFIX_PATTERN}))",
    re.IGNORECASE,
)
EXPLICIT_ROLE_PATTERN = re.compile(
    r"(?:求职意向|目标岗位|应聘岗位|求职岗位|期望职位|期望岗位|Objective|Target Role)"
    r"\s*[:：]\s*(?P<role>[^\n\r,，;；|]{2,40})",
    re.IGNORECASE,
)


def _clean_role(role: str) -> str:
    role = re.sub(r"\.(pdf|txt|md)$", "", role, flags=re.IGNORECASE)
    role = re.sub(r"[_\-]+", " ", role)
    role = re.sub(r"\s+", " ", role).strip(" \t:：,，;；|/\\()（）[]【】")
    return role[:40]


def extract_target_role_locally(resume_text: str, filename: str | None = None) -> str:
    """Best-effort local role extraction for obvious resume labels and filenames."""
    candidates: list[str] = []
    if resume_text:
        candidates.append(resume_text[:4000])
    if filename:
        candidates.append(filename)

    for source in candidates:
        explicit = EXPLICIT_ROLE_PATTERN.search(source)
        if explicit:
            role = _clean_role(explicit.group("role"))
            if role:
                return role

    for source in candidates:
        normalized = _clean_role(source)
        match = ROLE_PATTERN.search(normalized)
        if match:
            role = _clean_role(match.group(1))
            if role:
                return role

    return ""


async def extract_target_role_from_resume(resume_text: str, filename: str | None = None) -> str:
    """Extract the most likely target job role from a resume text."""
    if not resume_text or len(resume_text) < 10:
        return extract_target_role_locally(resume_text, filename)

    local_role = extract_target_role_locally(resume_text, filename)
    if local_role:
        return local_role

    settings = get_settings()

    model = ChatOpenAI(
        model=settings.openai_model_chat_fast,
        api_key=settings.openai_api_key,
        temperature=0.1,
        timeout=settings.llm_timeout_seconds,
    )
    
    # We use structured output to get a clean JSON response
    model_with_structure = model.with_structured_output(TargetRoleExtraction)
    
    prompt = f"""
    You are a professional HR analyst. Analyze the following resume text and identify the candidate's "Target Job Role".
    
    Rules:
    1. If the resume explicitly mentions a target role or objective, use that.
    2. If not, infer the role from their most recent experience or primary technical stack (e.g., if they are a Java dev, the role is "Backend Engineer").
    3. Be concise (max 4 words). Examples: "Senior Frontend Engineer", "Product Manager", "AI Researcher".
    4. Return "General Candidate" only if absolutely no professional context is found.
    
    Resume content:
    {resume_text[:4000]}
    """
    
    try:
        result = await model_with_structure.ainvoke([HumanMessage(content=prompt)])
        return result.target_role
    except Exception as e:
        log = logging.getLogger("app.services.resume_extractor")
        log.warning(f"Failed to extract role from resume: {e}")
        return ""


async def summarize_resume(resume_text: str) -> str:
    """将简历浓缩为 200 字以内的结构化中文摘要，供 Coach Agent 使用。"""
    settings = get_settings()
    model = ChatOpenAI(
        model=settings.openai_model_chat_fast,
        api_key=settings.openai_api_key,
        temperature=0.1,
        timeout=settings.llm_timeout_seconds,
    )
    prompt = f"""请将以下简历浓缩为一段 200 字以内的中文结构化摘要，供面试教练参考。
摘要需包含：工作年限、核心技能栈、代表性项目经历（1-2 条）、求职意向岗位。
只输出摘要正文，不要加标题或前缀。

简历内容：
{resume_text[:6000]}"""
    result = await model.ainvoke([HumanMessage(content=prompt)])
    return result.content.strip()
