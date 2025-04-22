#-----------------------------------------------------------------------------------------#
# [ 파일 개요 ]
# 이 파일은 FastAPI의 APIRouter를 사용하여 '/ai/local' 경로 아래에 로컬 AI 이벤트 관련 API 엔드포인트들을 정의합니다.
# 각 엔드포인트는 특정 HTTP 메소드(POST, GET)와 경로에 매핑되며, 관련된 서비스 함수(event_service)를 호출하여 비즈니스 로직을 처리합니다.
# 데이터베이스 세션 관리는 `Depends(get_db)`를 통해 이루어집니다.

# [ 주요 기능 (API 엔드포인트) ]
# 1. POST /create_event: 새로운 이벤트를 생성합니다. (event_service.create_event_service 호출)
# 2. GET /event/{event_id}: 특정 ID의 이벤트 상세 정보를 조회합니다. (event_service.get_event_service 호출)
# 3. GET /events: 이벤트 목록을 페이지네이션하여 조회합니다. (event_service.get_events_service 호출)
# 4. POST /solve_event: 이벤트 해결 정보(이미지, 설명)를 받아 처리하고 AI 분석 결과를 반환합니다. (event_service.solve_event_service 호출)
# 5. POST /event_complete/{event_id}: 이벤트 해결 상태를 완료/미완료로 변경합니다. (event_service.mark_event_complete_service 호출)
# 6. GET /download_report/{event_id}: 이벤트 보고서를 생성하여 지정된 이메일로 전송합니다. (event_service.generate_and_send_report_service 호출)
#-----------------------------------------------------------------------------------------#


from fastapi import APIRouter, UploadFile, Depends, HTTPException, Form, File, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from ..db import schemas as db_schemas
from ..db import models as db_models
from ..db.database import get_db
from ..services import event_service

router = APIRouter(
    prefix="/ai/local",
    tags=["Local AI Events"]
)


@router.post(
    "/create_event",
    response_model=db_schemas.EventResponse,
    summary="Create a new event"
)
async def create_event_router(
    payload: db_schemas.EventCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    새로운 이벤트를 생성합니다.

    - **type**: 이벤트 유형 (문자열)
    - **value**: 이벤트 내용 (문자열)
    """
    event = await event_service.create_event_service(db=db, event_data=payload)
    return event


@router.get(
    "/event/{event_id}",
    response_model=db_schemas.EventResponse,
    summary="Get a specific event by ID"
)
async def get_event_router(event_id: int, db: AsyncSession = Depends(get_db)):
    """지정된 ID의 이벤트 상세 정보를 조회합니다."""
    event = await event_service.get_event_service(db=db, event_id=event_id)
    return event


@router.get(
    "/events",
    response_model=db_schemas.EventsResponse,
    summary="Get a list of events"
)
async def get_events_router(
    skip: Optional[int] = 0,
    limit: Optional[int] = 30,
    db: AsyncSession = Depends(get_db),
):
    """
    이벤트 목록을 조회합니다 (페이지네이션 지원).

    - **skip**: 건너뛸 항목 수
    - **limit**: 가져올 최대 항목 수
    """
    events = await event_service.get_events_service(db=db, skip=skip, limit=limit)
    return {"events": events}


@router.post(
    "/solve_event",
    response_model=db_schemas.SolveEventResponse,
    summary="Submit solution info and get AI analysis"
)
async def solve_event_router(
    event_id: int = Form(...),
    image: UploadFile = File(...),
    explain: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """
    이벤트 해결 정보(이미지, 설명)를 제출하고 AI 분석 결과를 받습니다.
    (multipart/form-data 형식으로 요청)
    """
    answer = await event_service.solve_event_service(
        db=db, event_id=event_id, image=image, explain=explain
    )
    return {"event_id": event_id, "answer": answer}


@router.post(
    "/event_complete/{event_id}",
    response_model=db_schemas.EventCompleteResponse,
    summary="Mark an event solution as complete"
)
async def event_complete_router(
    event_id: int,
    payload: db_schemas.EventCompleteRequest = Body(db_schemas.EventCompleteRequest()),
    db: AsyncSession = Depends(get_db)
):
    """
    특정 이벤트의 해결 상태를 완료 또는 미완료로 변경합니다.
    기본값은 완료(True)입니다.
    """
    solution = await event_service.mark_event_complete_service(
        db=db, event_id=event_id, complete=payload.complete
    )
    return {"event_id": solution.event_id, "complete": solution.complete}


@router.get(
    "/download_report/{event_id}",
    response_model=db_schemas.ReportResponse, # 단순 메시지 또는 report_content 반환 스키마
    summary="Generate and email a report for an event"
)
async def get_event_report_router(
    event_id: int,
    email: str, 
    db: AsyncSession = Depends(get_db)
):
    """
    특정 이벤트에 대한 PDF 보고서를 생성하여 지정된 이메일로 전송합니다.
    (보고서 내용은 응답으로도 반환될 수 있음 - 스키마 정의에 따름)

    - **event_id**: 보고서를 생성할 이벤트 ID
    - **email**: 보고서를 받을 이메일 주소
    """
    report_content = await event_service.generate_and_send_report_service(
        db=db, event_id=event_id, email=email
    )
    return {"answer": report_content}
