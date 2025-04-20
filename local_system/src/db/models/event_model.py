from sqlalchemy import Column, Integer, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from ..database import Base


class EventModel(Base):
    """
    발생한 이벤트 정보를 나타내는 SQLAlchemy 모델 클래스.
    EventDetailModel 및 SolutionModel과 관계를 가집니다.
    """
    __tablename__ = "events"

    id = Column(
        Integer,
        primary_key=True,
        index=True, # 기본 키는 자동으로 인덱싱되지만 명시적으로 추가
        comment="이벤트 고유 식별자 (PK)"
    )
    
    type = Column(
        Text,
        nullable=False,
        comment="이벤트 유형"
    )
    
    value = Column(
        Text,
        nullable=False,
        comment="이벤트 상세 내용 또는 관련 값"
    )

    time = Column(
        DateTime,
        default=datetime.now,
        nullable=False,
        index=True,
        comment="이벤트 발생 시간"
    )

    event_details = relationship(
        "EventDetailModel",
        back_populates="event",
        cascade="all, delete-orphan", # Event 삭제 시 연관 EventDetail 삭제
        uselist=False, # 1:1 관계 명시
        lazy="selectin"
    )

    solutions = relationship(
        "SolutionModel",
        back_populates="event",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self):
        return f"<Event(id={self.id}, type='{self.type}', time='{self.time}')>"
