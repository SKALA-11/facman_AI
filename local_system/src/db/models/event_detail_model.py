from sqlalchemy import Column, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base


class EventDetailModel(Base):
    """
    이벤트 상세 정보(이미지, 설명)를 나타내는 SQLAlchemy 모델 클래스.
    'events' 테이블과 1:1 관계를 가집니다 (event_id가 PK이자 FK).
    """
    __tablename__ = "event_details"

    event_id = Column(
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"), # 부모 이벤트 삭제 시 자동 삭제 옵션 추가 고려
        primary_key=True,
        nullable=False,
        comment="참조하는 이벤트의 ID (PK, FK)"
    )
    
    file = Column(
        Text(length=16777215),
        nullable=False,
        comment="이벤트 관련 이미지 (Base64 인코딩된 문자열)"
    )
    
    explain = Column(
        Text,
        nullable=False,
        comment="이벤트에 대한 사용자 설명"
    )

    event = relationship(
        "EventModel",
        back_populates="event_details"
    )
    
    def __repr__(self):
        return f"<EventDetail(event_id={self.event_id})>"
