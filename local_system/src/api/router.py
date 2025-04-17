# from src.chatbot.chatbot_service import ChatBot
from fastapi import APIRouter, UploadFile, Depends, HTTPException, Form, File
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.database import get_db
from ..db.cruds import create_event, get_event, get_events
from ..db.cruds import create_event_detail, get_event_detail, update_event_detail
from ..db.cruds import (
    create_solution,
    get_solution,
    update_solution,
    update_solution_complete,
)
from typing import Optional
from ..utils import encode_image, make_pdf, send_email
import base64
import os

router = APIRouter()

@router.post("/create_event")
async def create_event_router(
    type: str,
    value: str,
    db: AsyncSession = Depends(get_db)
):
    event = await create_event(db, type, value)
    return event

@router.get("/event/{event_id}")
async def get_event_router(event_id: int, db: AsyncSession = Depends(get_db)):
    event = await get_event(db, event_id)
    return {"event": event}

@router.get("/events")
async def get_events_router(
    skip: Optional[int] = 0,
    limit: Optional[int] = 30,
    db: AsyncSession = Depends(get_db),
):
    events = await get_events(db, skip, limit)
    return {"events": events}

@router.post("/solve_event")
async def solve_event_router(
    event_id: int = Form(...),
    image: Optional[UploadFile] = File(None),
    explain: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    from src.chatbot.chatbot_service import chatbot

    event = await get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event with ID {event_id} not found")

    # 이미지 처리
    if image is not None:
        if image.content_type not in ["image/png", "image/jpeg", "image/gif", "image/webp"]:
            raise HTTPException(status_code=400, detail=f"지원하지 않는 이미지 형식입니다: {image.content_type}")

        bytes_data = await image.read()
        base64_image = base64.b64encode(bytes_data).decode("utf-8")
        encoded_image = f"data:{image.content_type};base64,{base64_image}"
    else:
        encoded_image = None

    # DB 저장 또는 업데이트
    event_detail = await get_event_detail(db, event_id)
    if event_detail:
        event_detail = await update_event_detail(db, event_id, encoded_image or "", explain)
    else:
        event_detail = await create_event_detail(db, event_id, encoded_image or "", explain)

    # GPT 응답
    answer = chatbot.solve_event(event, encoded_image, explain)
    if answer.startswith("[ERROR]"):
        raise HTTPException(status_code=500, detail=answer)

    # 솔루션 저장
    solution = await get_solution(db, event_id)
    if solution:
        solution = await update_solution(db, event_id, answer)
    else:
        solution = await create_solution(db, event_id, answer)

    return {
        "event_id": event_id,
        "answer": answer
    }

@router.post("/event_complete/{event_id}")
async def event_complete_router(
    event_id: int, complete: bool = True, db: AsyncSession = Depends(get_db)
):
    solution = await update_solution_complete(db, event_id, complete)
    if not solution:
        raise HTTPException(
            status_code=404, detail=f"Solution with ID {event_id} not found"
        )
    return {"event_id": event_id, "complete": complete}

@router.get("/download_report/{event_id}")
async def get_event_report_router(event_id: int, email: str, db: AsyncSession = Depends(get_db)):
    from src.chatbot.chatbot_service import chatbot

    event = await get_event(db, event_id)
    if not event:
        raise HTTPException(
            status_code=404, detail=f"Event with ID {event_id} not found"
        )

    event_detail = await get_event_detail(db, event_id)
    if not event_detail:
        raise HTTPException(
            status_code=404, detail=f"Event detail for event ID {event_id} not found"
        )

    solution = await get_solution(db, event_id)
    if not solution:
        raise HTTPException(
            status_code=404, detail=f"Solution for event ID {event_id} not found"
        )

    answer = chatbot.make_report_content(
        event, event_detail.file, event_detail.explain, solution.answer
    )

    send_email(email, make_pdf(answer))

    return {"answer": answer}
