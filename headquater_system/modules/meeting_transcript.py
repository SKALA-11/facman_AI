# modules/meeting_transcript.py
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import DB_URL
# Define the log directory
DATABASE_URL = DB_URL
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
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
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def generate_meeting_summary(session_id: str, title: str, content: str):
    """
    Save meeting summary to database
    """
    db = SessionLocal()
    try:
        existing_transcript = db.query(MeetingTranscriptDB).filter(MeetingTranscriptDB.session_id == session_id).first()
        if existing_transcript:
            existing_transcript.content = content
        else:
            db_transcript = MeetingTranscriptDB(
                session_id=session_id,
                title=title,
                content=content
            )
            db.add(db_transcript)

        db.commit()
        return {"session_id": session_id, "title": title, "content": content}, 200
    except Exception as e:
        db.rollback()
        print(f"Database error: {e}")
        return {"error": f"Database error: {str(e)}"}, 500
    finally:
        db.close()

async def get_meeting_summary(session_id: str):
    """
    Get meeting summary from DB
    """
    db = SessionLocal()
    try:
        transcript = db.query(MeetingTranscriptDB).filter(MeetingTranscriptDB.session_id == session_id).first()
        if transcript:
            return {"session_id": transcript.session_id, "title": transcript.title, "content": transcript.content, "generated_at": transcript.generated_at.isoformat()}, 200
        else:
            return {"error": f"No summary found for session ID: {session_id}"}, 404
    finally:
        db.close()

async def list_meeting_transcripts():
    """
    List all meeting transcripts from DB
    """
    db = SessionLocal()
    try:
        transcripts = db.query(MeetingTranscriptDB).all()
        transcript_list = [{"session_id": t.session_id, "title": t.title, "generated_at": t.generated_at.isoformat()} for t in transcripts]
        return transcript_list, 200
    finally:
        db.close()

async def update_meeting_title(session_id: str, new_title: str):
    """
    Update the title of a meeting transcript
    """
    db = SessionLocal()
    try:
        transcript = db.query(MeetingTranscriptDB).filter(MeetingTranscriptDB.session_id == session_id).first()
        if not transcript:
            return {"error": f"No transcript found for session ID: {session_id}"}, 404
        
        transcript.title = new_title
        db.commit()
        return {"session_id": session_id, "title": new_title}, 200
    finally:
        db.close()

# 테이블 생성 함수
def create_tables():
    Base.metadata.create_all(bind=engine)