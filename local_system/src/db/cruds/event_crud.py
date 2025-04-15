from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime

from ..models import EventModel
from ..schemas import EventCreate, EventInDB


async def create_event(db: AsyncSession, type: str, value: str, sensor_data: str) -> EventInDB:
    db_event = EventModel(type=type, value=value, sensor_data=sensor_data, time=datetime.now())
    db.add(db_event)
    await db.commit()
    await db.refresh(db_event)
    return db_event


async def get_event(db: AsyncSession, event_id: int) -> Optional[EventModel]:
    result = await db.execute(select(EventModel).filter(EventModel.id == event_id))
    return result.scalar_one_or_none()


async def get_events(
    db: AsyncSession, skip: int = 0, limit: int = 30
) -> List[EventModel]:
    stmt = select(EventModel).order_by(EventModel.time.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    events = list(result.scalars().all())
    return events
