import base64
from chatbot import chatbot
from fastapi import APIRouter, UploadFile, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db.cruds import create_event, get_event, get_events
from db.cruds import create_event_detail, get_event_detail, update_event_detail
from db.cruds import (
    create_solution,
    get_solution,
    update_solution,
    update_solution_complete,
)
from typing import Optional
from io import BytesIO
from PIL import Image

router = APIRouter()


@router.post("/create_event")
async def create_event_router(
    type: str, value: str, db: AsyncSession = Depends(get_db)
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
    event_id: int, file: UploadFile, explain: str, db: AsyncSession = Depends(get_db)
):
    event = await get_event(db, event_id)
    if not event:
        raise HTTPException(
            status_code=404, detail=f"Event with ID {event_id} not found"
        )

    bytes_data = await file.read()

    img = Image.open(BytesIO(bytes_data))
    img = img.convert("RGB")

    max_size = (800, 800)
    img.thumbnail(max_size, Image.LANCZOS)

    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=70)
    compressed_bytes = buffer.getvalue()

    file_encoded = base64.b64encode(compressed_bytes).decode("utf-8")

    event_detail = await get_event_detail(db, event_id)

    if event_detail:
        event_detail = await update_event_detail(db, event_id, file_encoded, explain)
    else:
        event_detail = await create_event_detail(db, event_id, file_encoded, explain)

    await file.seek(0)
    answer = chatbot.solve_event(event, file_encoded, explain)

    solution = await get_solution(db, event_id)
    if solution:
        solution = await update_solution(db, event_id, answer)
    else:
        solution = await create_solution(db, event_id, answer)

    return {"event_id": event_id, "answer": answer}


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
async def get_event_report_router(event_id: int, db: AsyncSession = Depends(get_db)):
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

    return {"answer": answer}
