from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional, List

orm_config = ConfigDict(from_attributes=True)

class EventBase(BaseModel):
    """이벤트의 기본 필드를 정의하는 스키마."""
    type: str = Field(..., description="이벤트 유형", example="SensorAnomaly")
    value: str = Field(..., description="이벤트 상세 내용 또는 관련 값")

class EventCreate(EventBase):
    """새로운 이벤트 생성을 위한 스키마."""
    type: str = Field(..., min_length=1, description="이벤트 유형 (최소 1자 이상)", example="SensorAnomaly")
    value: str = Field(..., min_length=1, description="이벤트 상세 내용 (최소 1자 이상)")

class EventUpdate(BaseModel):
    """이벤트 업데이트를 위한 스키마. 모든 필드는 선택적입니다."""
    type: Optional[str] = Field(None, min_length=1, description="업데이트할 이벤트 유형 (최소 1자 이상)")
    value: Optional[str] = Field(None, min_length=1, description="업데이트할 이벤트 상세 내용 (최소 1자 이상)")

class EventInDB(EventBase):
    """데이터베이스에서 읽어온 이벤트 정보를 나타내는 스키마 (ID, 시간 포함)."""
    id: int = Field(..., description="이벤트 고유 ID", example=101)
    time: datetime = Field(..., description="이벤트 발생 시간")
    
    model_config = orm_config # ORM 모델 인스턴스로부터 필드 값을 읽어올 수 있도록 설정

class EventResponse(EventInDB):
    """API 응답으로 사용될 이벤트 정보 스키마."""
    pass

class EventsResponse(BaseModel):
    """이벤트 목록 API 응답을 위한 스키마."""
    events: List[EventResponse] = Field(..., description="이벤트 객체의 리스트")

class SolveEventResponse(BaseModel):
    """이벤트 해결 정보 제출 API의 응답 스키마."""
    event_id: int = Field(..., description="처리된 이벤트의 ID")
    answer: str = Field(..., description="AI가 생성한 분석 및 해결 방안")

class ReportResponse(BaseModel):
    """이벤트 보고서 생성 및 이메일 전송 API의 응답 스키마."""
    answer: str = Field(..., description="AI가 생성한 보고서 내용")