from pydantic import BaseModel, ConfigDict
from typing import Optional


class EventDetailBase(BaseModel):
    event_id: int
    file: str
    explain: str


class EventDetailCreate(EventDetailBase):
    pass


class EventDetailUpdate(BaseModel):
    file: Optional[str] = None
    explain: Optional[str] = None


class EventDetailInDB(EventDetailBase):

    model_config = ConfigDict(from_attributes=True)


class EventDetailResponse(EventDetailInDB):
    pass
