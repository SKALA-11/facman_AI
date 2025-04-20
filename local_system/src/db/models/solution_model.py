from sqlalchemy import (
    Column,
    Integer,
    Text,
    Boolean,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from ..database import Base


class SolutionModel(Base):
    """
    이벤트에 대한 AI 분석 결과(해결 방안) 및 완료 상태를 나타내는 SQLAlchemy 모델 클래스.
    'events' 테이블과 1:1 관계를 가집니다 (event_id가 PK이자 FK).
    """
    __tablename__ = "solutions"

    event_id = Column(
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        comment="참조하는 이벤트의 ID (PK, FK)"
    )
    
    answer = Column(
        Text,
        nullable=False,
        comment="AI가 생성한 해결 방안 텍스트"
    )
    
    complete = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True, # 완료 여부로 조회할 경우를 대비해 인덱스 추가 고려
        comment="이벤트 해결 완료 여부 (True: 완료, False: 미완료)"
    )

    event = relationship(
        "EventModel",
        back_populates="solutions"
    )

    def __repr__(self):
        return f"<Solution(event_id={self.event_id}, complete={self.complete})>"
