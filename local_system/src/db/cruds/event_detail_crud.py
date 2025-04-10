from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List

from db.models import EventDetailModel
from db.schemas import EventDetailCreate, EventDetailInDB


async def create_event_detail(
    db: AsyncSession, event_id: int, file: str, explain: str
) -> EventDetailInDB:
    db_event_detail = EventDetailModel(event_id=event_id, file=file, explain=explain)
    db.add(db_event_detail)
    await db.commit()
    await db.refresh(db_event_detail)
    return db_event_detail


async def get_event_detail(
    db: AsyncSession, event_id: int
) -> Optional[EventDetailModel]:
    result = await db.execute(
        select(EventDetailModel).filter(EventDetailModel.event_id == event_id)
    )
    return result.scalar_one_or_none()


async def update_event_detail(
    db: AsyncSession, event_id: int, file: str, explain: str
) -> Optional[EventDetailModel]:
    event_detail = await get_event_detail(db, event_id)
    if event_detail:
        event_detail.file = file
        event_detail.explain = explain
        await db.commit()
        await db.refresh(event_detail)
    return event_detail
