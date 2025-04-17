# modules/meeting_transcript.py
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime
from config import DB_URL

# Define the log directory
engine = create_async_engine(DB_URL)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

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
    async with async_session() as session:
        try:
            existing_transcript = await session.execute(
                "SELECT * FROM meeting_transcripts WHERE session_id = :session_id",
                {"session_id": session_id}
            )
            existing_transcript = existing_transcript.first()
            
            if existing_transcript:
                await session.execute(
                    "UPDATE meeting_transcripts SET content = :content WHERE session_id = :session_id",
                    {"content": content, "session_id": session_id}
                )
            else:
                await session.execute(
                    "INSERT INTO meeting_transcripts (session_id, title, content) VALUES (:session_id, :title, :content)",
                    {"session_id": session_id, "title": title, "content": content}
                )
            
            await session.commit()
            return {"session_id": session_id, "title": title, "content": content}, 200
        except Exception as e:
            await session.rollback()
            print(f"Database error: {e}")
            return {"error": f"Database error: {str(e)}"}, 500

async def get_meeting_summary(session_id: str):
    """
    Get meeting summary from DB
    """
    async with async_session() as session:
        try:
            result = await session.execute(
                "SELECT * FROM meeting_transcripts WHERE session_id = :session_id",
                {"session_id": session_id}
            )
            transcript = result.first()
            
            if transcript:
                return {
                    "session_id": transcript.session_id,
                    "title": transcript.title,
                    "content": transcript.content,
                    "generated_at": transcript.generated_at.isoformat()
                }, 200
            else:
                return {"error": f"No summary found for session ID: {session_id}"}, 404
        except Exception as e:
            print(f"Database error: {e}")
            return {"error": f"Database error: {str(e)}"}, 500

async def list_meeting_transcripts():
    """
    List all meeting transcripts from DB
    """
    async with async_session() as session:
        try:
            result = await session.execute("SELECT * FROM meeting_transcripts")
            transcripts = result.fetchall()
            
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
            result = await session.execute(
                "SELECT * FROM meeting_transcripts WHERE session_id = :session_id",
                {"session_id": session_id}
            )
            transcript = result.first()
            
            if not transcript:
                return {"error": f"No transcript found for session ID: {session_id}"}, 404
            
            await session.execute(
                "UPDATE meeting_transcripts SET title = :title WHERE session_id = :session_id",
                {"title": new_title, "session_id": session_id}
            )
            await session.commit()
            return {"session_id": session_id, "title": new_title}, 200
        except Exception as e:
            await session.rollback()
            print(f"Database error: {e}")
            return {"error": f"Database error: {str(e)}"}, 500

# 테이블 생성 함수
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)