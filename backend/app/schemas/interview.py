"""interview 对话接口的请求体模型与校验。"""
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

# 单条消息内容上限，防止单条超长拖垮上下文与调用成本
MAX_CONTENT_LEN = 4000
# 历史消息条数上限：无状态多轮下前端带全量历史，需兜底防止上下文无限增长
MAX_MESSAGES = 50


class ChatMessage(BaseModel):
    """一条对话消息：role 仅限 user / assistant。"""

    role: Literal["user", "assistant"]
    content: str

    @field_validator("content")
    @classmethod
    def _content_not_blank(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("content 不能为空")
        if len(text) > MAX_CONTENT_LEN:
            raise ValueError(f"content 长度不能超过 {MAX_CONTENT_LEN}")
        return text


class ChatRequest(BaseModel):
    """面试对话请求：前端带全量历史，最后一条必须是 user 才有可回复的输入。"""

    messages: list[ChatMessage]

    @model_validator(mode="after")
    def _validate_messages(self) -> Self:
        if not self.messages:
            raise ValueError("messages 不能为空")
        if len(self.messages) > MAX_MESSAGES:
            raise ValueError(f"messages 条数不能超过 {MAX_MESSAGES}")
        if self.messages[-1].role != "user":
            raise ValueError("最后一条消息必须是 user")
        return self


class TurnRequest(BaseModel):
    """统一面试入口请求：前端只提交本轮用户输入，历史由后端按 user_id 管理。"""

    message: str
    prepared_questions: list[dict[str, Any]] | None = None
    jd_context: dict[str, Any] | None = None

    @field_validator("message")
    @classmethod
    def _message_not_blank(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("message 不能为空")
        if len(text) > MAX_CONTENT_LEN:
            raise ValueError(f"message 长度不能超过 {MAX_CONTENT_LEN}")
        return text


class UserContextResponse(BaseModel):
    """GET /interview/context 的响应：用于 Coach 页面判断新老用户。"""

    is_returning: bool
    target_role: str | None
    work_years: str | None = None
    target_company: str | None
    user_background: str | None
    session_count: int


class ResetRequest(BaseModel):
    """POST /interview/reset 的可选请求体：携带 Coach 收集的上下文。"""

    target_role: str | None = None
    user_background: str | None = None


class CoachOpeningMessageResponse(BaseModel):
    """GET /api/coach/opening-message 的展示文案响应。"""

    greeting: str
    weakness_summary: str | None
    evidence: str | None
    focus_today: str
    cta_type: Literal["new", "returning"]
    # 第五步「教练 Agent + 共享记忆层」预留：默认空，本次不实现填充逻辑
    long_memory_hints: list[str] = []
    hobby_hints: list[str] = []


class InterviewHistoryItem(BaseModel):
    """单场面试历史记录项。"""

    id: UUID
    date: str
    topic: str
    target_role: str
    score: float
    pass_fail: Literal["pass", "fail", "partial"]
    key_issues: list[str]
    report: dict[str, Any] | None


class InterviewHistoryResponse(BaseModel):
    """GET /api/v1/interview/history 的响应。"""

    sessions: list[InterviewHistoryItem]


class ActiveMessageItem(BaseModel):
    role: str
    content: str


class ActiveSessionResponse(BaseModel):
    """GET /api/v1/interview/active 的响应。"""

    session_id: str | None = None
    target_role: str | None = None
    target_company: str | None = None
    user_background: str | None = None
    stage: str | None = None
    question_count: int = 0
    total_questions: int = 5
    followup_count: int = 0
    messages: list[ActiveMessageItem] = []
    report: dict[str, Any] | None = None
