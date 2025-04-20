from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from ..db import models as db_models
from ..db import cruds
from ..db import schemas as db_schemas
from ..utils import encode_image, make_pdf, send_email
from ..chatbot import ChatBot

async def create_event_service(
    db: AsyncSession, event_data: db_schemas.EventCreateRequest
) -> db_models.EventModel:
    """이벤트 생성 서비스 로직"""
    return await cruds.create_event(db=db, type=event_data.type, value=event_data.value)

async def get_event_service(db: AsyncSession, event_id: int) -> db_models.EventModel:
    """특정 이벤트 조회 서비스 로직"""
    event = await cruds.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event with ID {event_id} not found")
    return event

async def get_events_service(
    db: AsyncSession, skip: int = 0, limit: int = 30
) -> List[db_models.EventModel]:
    """이벤트 목록 조회 서비스 로직"""
    return await cruds.get_events(db=db, skip=skip, limit=limit)

async def solve_event_service(
    db: AsyncSession, event_id: int, image: UploadFile, explain: str
) -> str:
    """이벤트 해결 정보 제출 및 AI 분석 서비스 로직"""
    event = await get_event_service(db, event_id) # 내부 서비스 함수 재사용 및 404 처리

    try:
        bytes_data = await image.read()
        if not bytes_data:
             raise HTTPException(status_code=400, detail="Image file is empty.")
        encoded_image = encode_image(bytes_data)
    except Exception as e:
        # 이미지 처리 오류 핸들링 강화
        raise HTTPException(status_code=400, detail=f"Failed to process image: {e}")
    finally:
        await image.close() # 파일 핸들 닫기

    # EventDetail 생성 또는 업데이트
    event_detail = await cruds.get_event_detail(db, event_id)
    if event_detail:
        await cruds.update_event_detail(db, event_id, encoded_image, explain)
    else:
        await cruds.create_event_detail(db, event_id, encoded_image, explain)

    # Chatbot 호출
    try:
        chatbot = ChatBot() # ChatBot 인스턴스화 (싱글톤 패턴 가정)
        answer = chatbot.solve_event(event, encoded_image, explain)
    except Exception as e:
        # Chatbot 호출 오류 핸들링
        raise HTTPException(status_code=500, detail=f"Failed to get analysis from AI: {e}")

    # Solution 생성 또는 업데이트
    solution = await cruds.get_solution(db, event_id)
    if solution:
        await cruds.update_solution(db, event_id, answer)
    else:
        await cruds.create_solution(db, event_id, answer)

    return answer

async def mark_event_complete_service(
    db: AsyncSession, event_id: int, complete: bool
) -> db_models.SolutionModel:
    """이벤트 완료 처리 서비스 로직"""
    solution = await cruds.update_solution_complete(db=db, event_id=event_id, complete=complete)
    if not solution:
        raise HTTPException(status_code=404, detail=f"Solution for event ID {event_id} not found. Cannot mark as complete.")
    return solution

async def generate_and_send_report_service(
    db: AsyncSession, event_id: int, email: str
) -> str:
    """보고서 생성 및 이메일 전송 서비스 로직"""
    event = await get_event_service(db, event_id) # 404 처리 포함

    event_detail = await cruds.get_event_detail(db, event_id)
    if not event_detail:
        raise HTTPException(status_code=404, detail=f"Event detail for event ID {event_id} not found")

    solution = await cruds.get_solution(db, event_id)
    if not solution:
        raise HTTPException(status_code=404, detail=f"Solution for event ID {event_id} not found")
    if not solution.answer:
         raise HTTPException(status_code=400, detail=f"Solution answer for event ID {event_id} is empty. Cannot generate report.")

    # Chatbot 호출하여 보고서 내용 생성
    try:
        chatbot = ChatBot()
        report_content = chatbot.make_report_content(
            event, event_detail.file, event_detail.explain, solution.answer
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report content from AI: {e}")

    # PDF 생성 및 이메일 전송
    try:
        pdf_data = make_pdf(report_content)
        send_email(email, pdf_data)
    except Exception as e:
        # PDF 또는 이메일 전송 실패 처리
        raise HTTPException(status_code=500, detail=f"Failed to generate or send report PDF: {e}")

    return report_content # 또는 성공 메시지 반환