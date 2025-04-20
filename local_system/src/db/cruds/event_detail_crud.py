import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from ..models import EventDetailModel

logger = logging.getLogger(__name__)

async def create_event_detail(
    db: AsyncSession, event_id: int, file: str, explain: str
) -> EventDetailModel:
    """
    새로운 이벤트 상세 정보 레코드를 데이터베이스에 생성합니다.
    Args:
        db: SQLAlchemy AsyncSession 인스턴스.
        event_id: 연결될 이벤트의 ID.
        file: Base64 인코딩된 이미지 파일 문자열.
        explain: 이벤트에 대한 설명 문자열.
    Returns:
        생성된 EventDetailModel 객체.
    Raises:
        SQLAlchemyError: 데이터베이스 작업 중 오류 발생 시.
    """
    logger.info(f"Creating event detail for event ID: {event_id}")
    try:
        db_event_detail = EventDetailModel(event_id=event_id, file=file, explain=explain)
        db.add(db_event_detail)
        await db.commit()
        # 생성된 객체 새로고침
        await db.refresh(db_event_detail)
        logger.info(f"Successfully created event detail for event ID: {event_id}")
        return db_event_detail
    except Exception as e:
        logger.exception(f"Failed to create event detail for event ID {event_id}. Error: {e}")
        await db.rollback() # 오류 발생 시 롤백
        raise # 예외를 다시 발생시켜 상위 계층에서 처리하도록 함

async def get_event_detail(
    db: AsyncSession, event_id: int
) -> Optional[EventDetailModel]:
    """
    주어진 이벤트 ID에 해당하는 이벤트 상세 정보를 데이터베이스에서 조회합니다.

    Args:
        db: SQLAlchemy AsyncSession 인스턴스.
        event_id: 조회할 이벤트 상세 정보의 이벤트 ID.

    Returns:
        조회된 EventDetailModel 객체 또는 찾지 못한 경우 None.
    """
    logger.debug(f"Fetching event detail for event ID: {event_id}")
    try:
        # event_id를 기준으로 EventDetailModel 조회 쿼리 생성
        stmt = select(EventDetailModel).filter(EventDetailModel.event_id == event_id)
        # 쿼리 실행 및 결과 가져오기
        result = await db.execute(stmt)
        # 단일 결과 반환 (없으면 None)
        event_detail = result.scalar_one_or_none()
        if event_detail:
            logger.debug(f"Found event detail for event ID: {event_id}")
        else:
            logger.debug(f"Event detail for event ID: {event_id} not found")
        return event_detail
    except Exception as e:
        logger.exception(f"Error fetching event detail for event ID {event_id}: {e}")
        raise

async def update_event_detail(
    db: AsyncSession, event_id: int, file: str, explain: str
) -> Optional[EventDetailModel]:
    """
    기존 이벤트 상세 정보 레코드를 업데이트합니다.

    Args:
        db: SQLAlchemy AsyncSession 인스턴스.
        event_id: 업데이트할 이벤트 상세 정보의 이벤트 ID.
        file: 업데이트할 Base64 인코딩된 이미지 파일 문자열.
        explain: 업데이트할 이벤트 설명 문자열.

    Returns:
        업데이트된 EventDetailModel 객체 또는 해당 ID의 레코드가 없는 경우 None.

    Raises:
        SQLAlchemyError: 데이터베이스 작업 중 오류 발생 시.
    """
    logger.info(f"Attempting to update event detail for event ID: {event_id}")
    try:
        # 기존 레코드 조회
        event_detail = await get_event_detail(db, event_id)

        if event_detail:
            logger.debug(f"Found event detail for update. Updating fields for event ID: {event_id}")
            # 필드 업데이트
            event_detail.file = file
            event_detail.explain = explain
            # 변경사항 커밋
            await db.commit()
            # 업데이트된 객체 새로고침
            await db.refresh(event_detail)
            logger.info(f"Successfully updated event detail for event ID: {event_id}")
            return event_detail
        else:
            # 업데이트할 레코드가 없는 경우
            logger.warning(f"Event detail for event ID {event_id} not found. Cannot update.")
            return None
    except Exception as e:
        logger.exception(f"Failed to update event detail for event ID {event_id}. Error: {e}")
        await db.rollback() # 오류 발생 시 롤백
        raise # 예외를 다시 발생시켜 상위 계층에서 처리하도록 함

