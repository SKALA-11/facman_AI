from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime, select
from sqlalchemy.exc import SQLAlchemyError
import logging
from config import DB_URL

logger = logging.getLogger(__name__)

try:
    engine = create_async_engine(
        DB_URL,
        pool_pre_ping=True,  # 연결 상태 확인
        pool_recycle=3600,   # 1시간마다 연결 재생성
        pool_size=5,         # 최소 연결 풀 크기
        max_overflow=10      # 최대 연결 풀 크기
    )
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    Base = declarative_base()
except Exception as e:
    logger.error(f"Failed to initialize database engine: {e}")
    raise

# 데이터베이스 모델 정의
class MeetingTranscriptDB(Base):
    __tablename__ = "meeting_transcripts"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    generated_at = Column(DateTime, default=datetime.now)

# 데이터베이스 세션 객체 생성 함수
async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

async def generate_meeting_summary(session_id: str, title: str, content: str):
    """
    Save meeting summary to database
    """
    try:
        async with async_session() as session:
            try:
                # session_id를 정확히 매칭하는 쿼리
                stmt = select(MeetingTranscriptDB).where(
                    MeetingTranscriptDB.session_id == str(session_id)
                )
                result = await session.execute(stmt)
                existing_transcript = result.scalar_one_or_none()
                
                if existing_transcript:
                    existing_transcript.title = title
                    existing_transcript.content = content
                    existing_transcript.generated_at = datetime.now()
                else:
                    new_transcript = MeetingTranscriptDB(
                        session_id=str(session_id),
                        title=title,
                        content=content,
                        generated_at=datetime.now()
                    )
                    session.add(new_transcript)
                
                await session.commit()
                
                return {
                    "session_id": str(session_id),
                    "title": title,
                    "content": content,
                    "generated_at": datetime.now().isoformat()
                }, 200
            except SQLAlchemyError as e:
                logger.error(f"Database error in generate_meeting_summary: {e}")
                await session.rollback()
                return {"error": f"Database error: {str(e)}"}, 500
    except Exception as e:
        logger.error(f"Connection error in generate_meeting_summary: {e}")
        return {"error": f"Connection error: {str(e)}"}, 502

async def get_meeting_summary(session_id: str):
    """
    Get meeting summary from DB
    """
    try:
        async with async_session() as session:
            try:
                # session_id를 정확히 매칭하는 쿼리
                stmt = select(MeetingTranscriptDB).where(
                    MeetingTranscriptDB.session_id == str(session_id)
                )
                result = await session.execute(stmt)
                transcript = result.scalar_one_or_none()
                
                if transcript:
                    return {
                        "session_id": transcript.session_id,
                        "title": transcript.title,
                        "content": transcript.content,
                        "generated_at": transcript.generated_at.isoformat()
                    }, 200
                else:
                    logger.warning(f"No transcript found for session_id: {session_id}")
                    return {"error": f"No summary found for session ID: {session_id}"}, 404
            except SQLAlchemyError as e:
                logger.error(f"Database error in get_meeting_summary: {e}")
                await session.rollback()
                return {"error": f"Database error: {str(e)}"}, 500
    except Exception as e:
        logger.error(f"Connection error in get_meeting_summary: {e}")
        return {"error": f"Connection error: {str(e)}"}, 502

async def list_meeting_transcripts():
    """
    List all meeting transcripts from DB
    """
    async with async_session() as session:
        try:
            stmt = select(MeetingTranscriptDB)
            result = await session.execute(stmt)
            transcripts = result.scalars().all()
            
            transcript_list = [
                {
                    "session_id": t.session_id,
                    "title": t.title,
                    "generated_at": t.generated_at.isoformat()
                } for t in transcripts
            ]
            return transcript_list, 200
        except Exception as e:
            print(f"Database error: {e}")
            return {"error": f"Database error: {str(e)}"}, 500

async def update_meeting_title(session_id: str, new_title: str):
    """
    Update the title of a meeting transcript
    """
    async with async_session() as session:
        try:
            stmt = select(MeetingTranscriptDB).where(MeetingTranscriptDB.session_id == session_id)
            result = await session.execute(stmt)
            transcript = result.scalar_one_or_none()
            
            if not transcript:
                return {"error": f"No transcript found for session ID: {session_id}"}, 404
            
            transcript.title = new_title
            await session.commit()
            return {"session_id": session_id, "title": new_title}, 200
        except Exception as e:
            await session.rollback()
            print(f"Database error: {e}")
            return {"error": f"Database error: {str(e)}"}, 500

async def delete_meeting_summary(session_id: str):
    try:
        async with async_session() as session:
            try:
                stmt = select(MeetingTranscriptDB).where(MeetingTranscriptDB.session_id == session_id)
                result = await session.execute(stmt)
                transcript = result.scalar_one_or_none()

                if not transcript:
                    logger.warning(f"Attempted to delete non-existent summary for session_id: {session_id}")
                    return {"error": f"ID '{session_id}'에 해당하는 회의록을 찾을 수 없습니다."}, 404

                await session.delete(transcript)
                await session.commit()

                logger.info(f"Successfully deleted meeting summary for session_id: {session_id}")
                return {"message": f"회의록(ID: {session_id})이 성공적으로 삭제되었습니다."}, 200
            except SQLAlchemyError as e:
                logger.error(f"Database error while deleting summary for session_id {session_id}: {e}", exc_info=True)
                await session.rollback()
                return {"error": f"데이터베이스 오류 발생: {str(e)}"}, 500
    except Exception as e:
        logger.error(f"Connection error in delete_meeting_summary: {e}")
        return {"error": f"Connection error: {str(e)}"}, 502

# 테이블 생성 함수
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# 테이블 존재 여부 확인 함수
async def check_tables():
    async with engine.begin() as conn:
        tables = await conn.run_sync(lambda conn: conn.dialect.get_table_names(conn))
        return "meeting_transcripts" in tables
