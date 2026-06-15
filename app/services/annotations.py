from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meta import Annotation


async def create_annotation(
    session: AsyncSession,
    entity_type: str,
    entity_id: int,
    text: str,
    author_id: int | None,
) -> Annotation:
    a = Annotation(
        entity_type=entity_type, entity_id=entity_id, text=text, author_id=author_id
    )
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return a


async def list_annotations(
    session: AsyncSession, entity_type: str, entity_id: int
) -> list[Annotation]:
    stmt = (
        select(Annotation)
        .where(Annotation.entity_type == entity_type, Annotation.entity_id == entity_id)
        .order_by(Annotation.id)
    )
    return list((await session.execute(stmt)).scalars().all())
