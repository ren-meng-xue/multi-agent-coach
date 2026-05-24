"""统一 API 响应模型，所有接口返回数据走此结构。"""
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Response(BaseModel, Generic[T]):
    """统一响应：{ code, msg, data }，code 对齐 HTTP 状态码。"""

    code: int = Field(default=200, description="业务状态码，与 HTTP 状态码一致")
    msg: str = Field(default="success", description="响应消息")
    data: T | dict = Field(default_factory=dict, description="响应数据")

    @classmethod
    def ok(cls, data: T | None = None, msg: str = "success") -> "Response[T]":
        """成功响应，code 固定为 200。"""
        return cls(code=200, msg=msg, data=data if data is not None else {})

    @classmethod
    def fail(cls, code: int, msg: str, data: T | None = None) -> "Response[T]":
        """失败响应，code 自定义。"""
        return cls(code=code, msg=msg, data=data if data is not None else {})
