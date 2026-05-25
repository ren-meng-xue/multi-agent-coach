"""interview 对话接口的请求体模型与校验。"""
from typing import Literal, Self

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

    @field_validator("message")
    @classmethod
    def _message_not_blank(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("message 不能为空")
        if len(text) > MAX_CONTENT_LEN:
            raise ValueError(f"message 长度不能超过 {MAX_CONTENT_LEN}")
        return text
