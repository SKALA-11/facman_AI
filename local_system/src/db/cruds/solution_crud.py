import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from ..models import SolutionModel

logger = logging.getLogger(__name__)

async def create_solution(db: AsyncSession, event_id: int, answer: str) -> SolutionModel:
    """
    새로운 솔루션 레코드를 데이터베이스에 생성합니다.
    Args:
        db: SQLAlchemy AsyncSession 인스턴스.
        event_id: 연결될 이벤트의 ID.
        answer: AI가 생성한 솔루션 텍스트.
    Returns:
        생성된 SolutionModel 객체.
    Raises:
        SQLAlchemyError: 데이터베이스 작업 중 오류 발생 시.
    """
    try:
        db_solution = SolutionModel(event_id=event_id, answer=answer, complete=False)
        db.add(db_solution)
        await db.commit()
        await db.refresh(db_solution)
        return db_solution
    except Exception as e:
        logger.exception(f"Failed to create solution for event ID {event_id}. Error: {e}")
        await db.rollback()
        raise

async def get_solution(db: AsyncSession, event_id: int) -> Optional[SolutionModel]:
    """
    주어진 이벤트 ID에 해당하는 솔루션을 데이터베이스에서 조회합니다.
    Args:
        db: SQLAlchemy AsyncSession 인스턴스.
        event_id: 조회할 솔루션의 이벤트 ID.
    Returns:
        조회된 SolutionModel 객체 또는 찾지 못한 경우 None.
    """
    try:
        stmt = select(SolutionModel).filter(SolutionModel.event_id == event_id)
        result = await db.execute(stmt)
        solution = result.scalar_one_or_none()
        if solution:
            logger.debug(f"Found solution for event ID: {event_id}")
        else:
            logger.debug(f"Solution for event ID: {event_id} not found")
        return solution
    except Exception as e:
        logger.exception(f"Error fetching solution for event ID {event_id}: {e}")
        raise

async def update_solution(
    db: AsyncSession, event_id: int, answer: str
) -> Optional[SolutionModel]:
    """
    기존 솔루션 레코드의 'answer' 필드를 업데이트합니다.
    Args:
        db: SQLAlchemy AsyncSession 인스턴스.
        event_id: 업데이트할 솔루션의 이벤트 ID.
        answer: 업데이트할 새로운 솔루션 텍스트.
    Returns:
        업데이트된 SolutionModel 객체 또는 해당 ID의 레코드가 없는 경우 None.
    Raises:
        SQLAlchemyError: 데이터베이스 작업 중 오류 발생 시.
    """
    logger.info(f"Attempting to update solution answer for event ID: {event_id}")
    try:
        solution = await get_solution(db, event_id)

        if solution:
            solution.answer = answer
            await db.commit()
            await db.refresh(solution)
            return solution
        else:
            logger.warning(f"Solution for event ID {event_id} not found. Cannot update answer.")
            return None
    except Exception as e:
        logger.exception(f"Failed to update solution answer for event ID {event_id}. Error: {e}")
        await db.rollback()
        raise

async def update_solution_complete(
    db: AsyncSession, event_id: int, complete: bool
) -> Optional[SolutionModel]:
    """
    기존 솔루션 레코드의 'complete' 필드를 업데이트합니다.
    Args:
        db: SQLAlchemy AsyncSession 인스턴스.
        event_id: 업데이트할 솔루션의 이벤트 ID.
        complete: 업데이트할 완료 상태 (True 또는 False).
    Returns:
        업데이트된 SolutionModel 객체 또는 해당 ID의 레코드가 없는 경우 None.
    Raises:
        SQLAlchemyError: 데이터베이스 작업 중 오류 발생 시.
    """
    try:
        solution = await get_solution(db, event_id)

        if solution:
            # 'complete' 필드가 변경될 경우에만 업데이트 (선택적 최적화)
            if solution.complete != complete:
                logger.debug(f"Found solution. Updating complete status to '{complete}' for event ID: {event_id}")
                solution.complete = complete
                await db.commit()
                await db.refresh(solution)
                logger.info(f"Successfully updated solution complete status for event ID: {event_id}")
            else:
                logger.debug(f"Solution complete status for event ID {event_id} is already '{complete}'. No update needed.")
            return solution
        else:
            # 업데이트할 레코드가 없는 경우
            logger.warning(f"Solution for event ID {event_id} not found. Cannot update complete status.")
            return None
    except Exception as e:
        logger.exception(f"Failed to update solution complete status for event ID {event_id}. Error: {e}")
        await db.rollback() # 오류 발생 시 롤백
        raise # 예외를 다시 발생시켜 상위 계층에서 처리하도록 함
