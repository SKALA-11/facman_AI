from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class EventBase(BaseModel):
    type: str
    value: str


class EventCreate(EventBase):
    pass


class EventUpdate(EventBase):
    type: Optional[str] = None
    value: Optional[str] = None


class EventInDB(EventBase):
    id: int
    time: datetime

    model_config = ConfigDict(from_attributes=True)


class EventResponse(EventInDB):
    pass
