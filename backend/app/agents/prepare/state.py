# backend/app/agents/prepare/state.py
"""LangGraph state for the prepare pipeline."""
from typing import Annotated, Any, Literal, TypedDict


def merge_completed_tools(left: list[str] | None, right: list[str] | None) -> list[str]:
    """合并并行节点写入的 completed_tools，保持顺序并去重。"""
    merged: list[str] = []
    for item in (left or []) + (right or []):
        if item not in merged:
            merged.append(item)
    return merged


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


class JobIntel(TypedDict, total=False):
    """research_agent 写入：目标岗位的 6 模块情报（来自 job-intel MCP）。

    下游 Designer / Evaluator / Coach / Interviewer 各自读关心的字段。
    interview_qa / salary_range 保留为字段但下游不消费（避免 LLM 自循环和假数据）。
    """
    job_interpretation: dict
    resume_match: dict
    company_profile: dict
    interview_qa: list[dict]
    salary_range: dict
    prep_suggestions: list[dict]
    _trace: dict  # research_agent 过程产物：tools_used / iterations / elapsed_ms / final_thought


class PrepareState(TypedDict, total=False):
    # 输入
    session_id: str
    user_id: str
    user_direction: str | None   # 当前会话用户说的方向（非记忆）
    user_background: str | None
    jd_raw: str | None           # 已提取的 JD 纯文本
    jd_url: str | None           # JD 链接；research_agent 可用 MCP 提取

    # SUPERVISOR 决策输出
    direction: str               # 识别出的方向，如"分布式系统"
    next_action: str             # supervisor 当前决策
    need_direction: bool         # True = 需要向用户追问方向
    iteration_count: int         # supervisor 调用次数，防死循环
    completed_tools: Annotated[list[str], merge_completed_tools]   # 已完成的 tool 名列表

    # 子 Agent 结果
    weak_areas: list[str]        # 来自历史面试表现
    jd_context: JDContext | None
    job_intel: JobIntel | None    # research_agent 写入；MCP 不可用时为 None
    prepared_questions: list[PreparedQuestion]
    # 第五步「教练 Agent + 共享记忆层」预留：长期记忆/爱好记忆注入槽。本次不实现填充。
    long_memory: list[dict[str, Any]]

    # 最终输出
    summary: str                 # LLM 生成的一句话摘要（非固定文案）
