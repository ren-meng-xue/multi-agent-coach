"""QA Bank 接口的请求/响应 schema。"""
from pydantic import BaseModel


class QABankSummary(BaseModel):
    technical: int
    hr: int
    project: int
    total: int


class QABankUploadResult(BaseModel):
    imported: dict[str, int]
    skipped: int
