from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List

from db.models import SolutionModel
from db.schemas import SolutionCreate, SolutionInDB


async def create_solution(db: AsyncSession, event_id: int, answer: str) -> SolutionInDB:
    db_solution = SolutionModel(event_id=event_id, answer=answer, complete=False)
    db.add(db_solution)
    await db.commit()
    await db.refresh(db_solution)
    return db_solution


async def get_solution(db: AsyncSession, event_id: int) -> Optional[SolutionModel]:
    result = await db.execute(
        select(SolutionModel).filter(SolutionModel.event_id == event_id)
    )
    return result.scalar_one_or_none()


async def update_solution(
    db: AsyncSession, event_id: int, answer: str
) -> Optional[SolutionModel]:
    solution = await get_solution(db, event_id)
    if solution:
        solution.answer = answer
        await db.commit()
        await db.refresh(solution)
    return solution


async def update_solution_complete(
    db: AsyncSession, event_id: int, complete: bool
) -> Optional[SolutionModel]:
    solution = await get_solution(db, event_id)
    if solution:
        solution.complete = complete
        await db.commit()
        await db.refresh(solution)
    return solution
