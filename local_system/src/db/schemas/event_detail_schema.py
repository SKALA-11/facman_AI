from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

orm_config = ConfigDict(from_attributes=True)

class EventDetailBase(BaseModel):
    """이벤트 상세 정보의 기본 필드를 정의하는 스키마."""
    event_id: int = Field(..., description="관련 이벤트의 고유 ID", example=1)
    file: str = Field(..., description="Base64로 인코딩된 이미지 데이터 문자열")
    explain: str = Field(..., description="이벤트에 대한 사용자 설명", 
                         example="일부 생산라인에 화재가 발생하여 공장 전체에 정전이 발생했습니다.")

class EventDetailCreate(EventDetailBase):
    """새로운 이벤트 상세 정보 생성을 위한 스키마."""
    # 생성 시점의 유효성 검사
    explain: str = Field(..., min_length=1, 
                         description="이벤트에 대한 사용자 설명 (최소 1자 이상)", 
                         example="센서 주변에서 연기 발생 및 온도 급상승 감지됨.")

class EventDetailUpdate(BaseModel):
    """이벤트 상세 정보 업데이트를 위한 스키마."""
    file: Optional[str] = Field(None, description="업데이트할 Base64 인코딩 이미지 데이터 문자열")
    explain: Optional[str] = Field(None, min_length=1, description="업데이트할 이벤트 설명 (최소 1자 이상)")

class EventDetailInDB(EventDetailBase):
    """데이터베이스에서 읽어온 이벤트 상세 정보를 나타내는 스키마."""
    model_config = orm_config

class EventDetailResponse(EventDetailInDB):
    """API 응답으로 사용될 이벤트 상세 정보 스키마."""
    # API 응답에서 특정 필드를 제외하거나 형식을 변경해야 할 경우에 추가로 수정
    pass

