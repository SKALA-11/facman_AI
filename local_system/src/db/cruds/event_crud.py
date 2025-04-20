import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime

from ..models import EventModel

logger = logging.getLogger(__name__)

async def create_event(db: AsyncSession, type: str, value: str) -> EventModel:
    """
    새로운 이벤트 레코드를 데이터베이스에 생성합니다.
    Args:
        db: SQLAlchemy AsyncSession 인스턴스.
        type: 이벤트 유형 (문자열).
        value: 이벤트 내용 (문자열).
    Returns:
        생성된 EventModel 객체.
    Raises:
        SQLAlchemyError: 데이터베이스 작업 중 오류 발생 시.
    """
    try:
        db_event = EventModel(type=type, value=value, time=datetime.now())
        db.add(db_event)
        await db.commit()
        await db.refresh(db_event) # 생성된 객체 새로고침 (ID 등 자동 생성 값 로드)
        logger.info(f"Successfully created event with ID: {db_event.id}")
        return db_event
    except Exception as e:
        logger.exception(f"Failed to create event - Type: {type}, Value: {value[:50]}... Error: {e}")
        await db.rollback() # 오류 발생 시 롤백
        raise # 예외를 다시 발생시켜 상위 계층에서 처리하도록 함

async def get_event(db: AsyncSession, event_id: int) -> Optional[EventModel]:
    """
    주어진 ID에 해당하는 이벤트를 데이터베이스에서 조회합니다.
    Args:
        db: SQLAlchemy AsyncSession 인스턴스.
        event_id: 조회할 이벤트의 ID.
    Returns:
        조회된 EventModel 객체 또는 찾지 못한 경우 None.
    """
    logger.debug(f"Fetching event with ID: {event_id}")
    try:
        stmt = select(EventModel).filter(EventModel.id == event_id) # ID를 기준으로 EventModel 조회 쿼리 생성
        result = await db.execute(stmt)     # 쿼리 실행 및 결과 가져오기
        event = result.scalar_one_or_none() # 단일 결과 반환 (없으면 None)
        if event:
            logger.debug(f"Found event with ID: {event_id}")
        else:
            logger.debug(f"Event with ID: {event_id} not found")
        return event
    except Exception as e:
        logger.exception(f"Error fetching event with ID {event_id}: {e}")
        raise

async def get_events(
    db: AsyncSession, skip: int = 0, limit: int = 30
) -> List[EventModel]:
    """
    이벤트 목록을 시간 역순으로 데이터베이스에서 조회합니다 (페이지네이션 지원).
    Args:
        db: SQLAlchemy AsyncSession 인스턴스.
        skip: 건너뛸 레코드 수 (기본값: 0).
        limit: 반환할 최대 레코드 수 (기본값: 30).
    Returns:
        조회된 EventModel 객체의 리스트.
    """
    logger.debug(f"Fetching events with skip: {skip}, limit: {limit}")
    try:
        stmt = ( # 시간(time) 기준 내림차순 정렬, offset, limit 적용 쿼리 생성
            select(EventModel)
            .order_by(EventModel.time.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        events = list(result.scalars().all()) # 모든 결과 스칼라 값(EventModel 객체)을 리스트로 변환
        return events
    except Exception as e:
        logger.exception(f"Error fetching events with skip {skip}, limit {limit}: {e}")
        raise

