"""用户题库相关接口：模板下载、题库上传、摘要查询。"""
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.core.exceptions import BadRequestException
from app.db.session import get_db
from app.schemas.qa_bank import QABankSummary, QABankUploadResult
from app.schemas.response import Response
from app.services.interview_turn import ensure_user_exists
from app.services.qa_bank import get_qa_bank_summary, parse_qa_markdown, upsert_qa_bank

_TEMPLATE = """\
## 技术题

### 题目 1
**问题：** 解释 RAG 的原理
**参考答案：** RAG 是检索增强生成，核心思路是...
**标签：** AI, RAG, 检索增强

---

### 题目 2
**问题：** 请在这里填写你的技术题
**参考答案：** 请填写参考答案
**标签：** 标签1, 标签2

---

## HR题

### 题目 1
**问题：** 介绍一下你自己
**参考答案：** 我有 X 年经验，专注于...
**标签：** 自我介绍

---

## 项目经验

### 题目 1
**问题：** 介绍你最近一个项目
**参考答案：** 这个项目的核心是...
**标签：** 项目经验

---
"""

router = APIRouter(prefix="/user/qa-bank")


@router.get("/template")
async def download_template(category: str | None = None) -> FastAPIResponse:
    """下载空白 Markdown 题库模板文件。可指定 category 下载单个分类。"""
    content = _TEMPLATE
    filename = "面试题库模板.md"

    if category:
        # 简单的正则或字符串分割来提取特定分类
        # 这里使用简单分割方式
        sections = _TEMPLATE.split("## ")
        cat_map = {
            "technical": "技术题",
            "hr": "HR题",
            "project": "项目经验",
        }
        target_title = cat_map.get(category)
        if target_title:
            for sec in sections:
                if sec.startswith(target_title):
                    content = "## " + sec.strip() + "\n"
                    filename = f"面试题库模板_{target_title}.md"
                    break

    return FastAPIResponse(
        content=content.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/upload", response_model=Response[QABankUploadResult])
async def upload_qa_bank(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Response[QABankUploadResult]:
    """上传填好的 Markdown 题库，解析后覆盖入库。"""
    filename = file.filename or ""
    if not filename.lower().endswith(".md"):
        raise BadRequestException("请上传 .md 格式的文件")

    raw = await file.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BadRequestException("文件编码不正确，请使用 UTF-8 编码保存后重新上传") from exc

    if not content.strip():
        raise BadRequestException("文件内容为空")

    try:
        items, skipped = parse_qa_markdown(content)
    except Exception as exc:
        raise BadRequestException("Markdown 格式错误，无法解析，请使用下载的模板填写") from exc

    await ensure_user_exists(db, user_id=user_id)
    imported = await upsert_qa_bank(db, user_id=user_id, items=items)
    await db.commit()

    return Response.ok(
        data=QABankUploadResult(imported=imported, skipped=skipped),
        msg="上传成功",
    )


@router.get("/summary", response_model=Response[QABankSummary])
async def get_summary(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Response[QABankSummary]:
    """返回各 category 题目数量。"""
    counts = await get_qa_bank_summary(db, user_id=user_id)
    return Response.ok(
        data=QABankSummary(
            technical=counts["technical"],
            hr=counts["hr"],
            project=counts["project"],
            total=sum(counts.values()),
        )
    )
