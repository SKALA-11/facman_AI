from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

orm_config = ConfigDict(from_attributes=True)

class SolutionBase(BaseModel):
    """솔루션(AI 분석 결과)의 기본 필드를 정의하는 스키마."""
    event_id: int = Field(..., description="관련 이벤트의 고유 ID", example=1)
    answer: str = Field(..., description="AI가 생성한 분석 및 해결 방안 텍스트", example="1. 원인 분석: ...")
    complete: bool = Field(False, description="이벤트 해결 완료 여부", example=False)

class SolutionCreate(SolutionBase):
    """새로운 솔루션 생성을 위한 스키마."""
    answer: str = Field(..., min_length=1, description="AI가 생성한 분석 및 해결 방안 텍스트 (최소 1자 이상)", example="1. 원인 분석: ...")

class SolutionUpdate(BaseModel):
    """솔루션 업데이트를 위한 스키마. 모든 필드는 선택적입니다."""
    answer: Optional[str] = Field(None, min_length=1, description="업데이트할 AI 분석 및 해결 방안 텍스트 (최소 1자 이상)")
    complete: Optional[bool] = Field(None, description="업데이트할 이벤트 해결 완료 여부")

class SolutionInDB(SolutionBase):
    """데이터베이스에서 읽어온 솔루션 정보를 나타내는 스키마."""
    model_config = orm_config

class SolutionResponse(SolutionInDB):
    """API 응답으로 사용될 솔루션 정보 스키마."""
    pass

class EventCompleteRequest(BaseModel):
     """이벤트 완료 상태 변경 요청을 위한 스키마 (라우터에서 사용)."""
     complete: bool = Field(True, description="변경할 완료 상태 (기본값: True)")

class EventCompleteResponse(BaseModel):
    """이벤트 완료 상태 변경 API의 응답 스키마."""
    event_id: int = Field(..., description="완료 상태가 변경된 이벤트의 ID")
    complete: bool = Field(..., description="변경된 완료 상태")