"""QA Bank 服务：Markdown 解析 + 数据库 CRUD。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

SECTION_MAP = {
    "技术题": "technical",
    "HR题": "hr",
    "项目讲解": "project",
    "项目经验": "project",
}


@dataclass
class ParsedQAItem:
    category: str
    question: str
    model_answer: str
    tags: list[str] | None = field(default=None)


def parse_qa_markdown(content: str) -> tuple[list[ParsedQAItem], int]:
    """解析题库 Markdown，返回 (有效条目列表, 跳过数量)。

    字段匹配必须严格，缺少问题或参考答案的条目计入 skipped。
    """
    items: list[ParsedQAItem] = []
    skipped = 0
    current_category: str | None = None
    current_item: dict | None = None

    def _flush_item() -> None:
        nonlocal skipped, current_item
        if current_item is None:
            return
        if current_item.get("question") and current_item.get("model_answer"):
            items.append(
                ParsedQAItem(
                    category=current_item["category"],
                    question=current_item["question"],
                    model_answer=current_item["model_answer"],
                    tags=current_item.get("tags"),
                )
            )
        else:
            skipped += 1
        current_item = None

    for line in content.splitlines():
        stripped = line.strip()

        sec_match = re.match(r"^## (.+)$", stripped)
        if sec_match:
            _flush_item()
            current_category = SECTION_MAP.get(sec_match.group(1).strip())
            continue

        if current_category is None:
            continue

        if re.match(r"^### .+$", stripped):
            _flush_item()
            current_item = {"category": current_category}
            continue

        if current_item is None:
            continue

        q_match = re.match(r"^\*\*问题：\*\* (.+)$", stripped)
        if q_match:
            current_item["question"] = q_match.group(1).strip()
            continue

        a_match = re.match(r"^\*\*参考答案：\*\* (.+)$", stripped)
        if a_match:
            current_item["model_answer"] = a_match.group(1).strip()
            continue

        t_match = re.match(r"^\*\*标签：\*\* (.+)$", stripped)
        if t_match:
            raw = t_match.group(1).strip()
            current_item["tags"] = [t.strip() for t in raw.split(",") if t.strip()]
            continue

    _flush_item()
    return items, skipped


async def upsert_qa_bank(
    db: AsyncSession,
    *,
    user_id: str,
    items: list[ParsedQAItem],
) -> dict[str, int]:
    """按 category 覆盖写入题库条目，只更新 items 中出现过的 category。

    返回各 category 的导入数量。
    """
    from app.models.qa_bank import UserQABank

    categories_present = {item.category for item in items}
    for category in categories_present:
        await db.execute(
            delete(UserQABank).where(
                UserQABank.user_id == user_id,
                UserQABank.category == category,
            )
        )

    counts: dict[str, int] = {}
    for item in items:
        db.add(
            UserQABank(
                user_id=user_id,
                category=item.category,
                question=item.question,
                model_answer=item.model_answer,
                tags=item.tags,
            )
        )
        counts[item.category] = counts.get(item.category, 0) + 1

    await db.flush()
    return counts


async def get_qa_bank_summary(db: AsyncSession, *, user_id: str) -> dict[str, int]:
    """返回 {technical, hr, project} 各 category 的条目数。"""
    from app.models.qa_bank import UserQABank

    result = await db.execute(
        select(UserQABank.category, func.count().label("cnt"))
        .where(UserQABank.user_id == user_id)
        .group_by(UserQABank.category)
    )
    summary: dict[str, int] = {"technical": 0, "hr": 0, "project": 0}
    for row in result:
        summary[row.category] = row.cnt
    return summary


async def get_qa_bank_items(
    db: AsyncSession, *, user_id: str
) -> list:
    """返回用户所有题库条目（UserQABank 实例列表），按 category 和创建时间排序。"""
    from app.models.qa_bank import UserQABank

    result = await db.execute(
        select(UserQABank)
        .where(UserQABank.user_id == user_id)
        .order_by(UserQABank.category, UserQABank.created_at)
    )
    return list(result.scalars().all())
