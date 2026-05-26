# backend/app/agents/prepare/state.py
"""LangGraph state for the prepare pipeline."""
from typing import Any, Literal, TypedDict


class JDContext(TypedDict):
    company: str
    role: str
    key_skills: list[str]
    focus_areas: list[str]
    difficulty: str  # "easy" | "medium" | "hard" | "faang"


class PreparedQuestion(TypedDict):
    id: int
    question: str
    category: Literal["technical", "behavioral", "system_design"]
    focus_area: str
    priority: int  # 1=最高优先级，薄弱点相关题排前


class PrepareState(TypedDict, total=False):
    # 输入
    session_id: str
    user_id: str
    user_direction: str | None   # 当前会话用户说的方向（非记忆）
    user_background: str | None
    jd_raw: str | None           # 已提取的 JD 纯文本

    # MASTER 决策输出
    direction: str               # 识别出的方向，如"分布式系统"
    chain: list[str]             # 调用链，如 ["memory_search", "jd_analysis", "question_gen"]
    need_direction: bool         # True = 需要向用户追问方向

    # 子 Agent 结果
    weak_areas: list[str]        # 来自历史面试表现
    star_stories: list[dict[str, Any]]  # 来自 UserStory 表
    jd_context: JDContext | None
    prepared_questions: list[PreparedQuestion]
    # 第五步「教练 Agent + 共享记忆层」预留：长期记忆/爱好记忆注入槽。本次不实现填充。
    long_memory: list[dict[str, Any]]

    # 最终输出
    summary: str                 # LLM 生成的一句话摘要（非固定文案）
