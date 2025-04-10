from pydantic import BaseModel, ConfigDict
from typing import Optional


class SolutionBase(BaseModel):
    event_id: int
    answer: str
    complete: bool = False


class SolutionCreate(SolutionBase):
    pass


class SolutionUpdate(BaseModel):
    answer: Optional[str] = None
    complete: Optional[bool] = None


class SolutionInDB(SolutionBase):

    model_config = ConfigDict(from_attributes=True)


class SolutionResponse(SolutionInDB):
    pass
