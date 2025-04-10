from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    ForeignKey,
    PrimaryKeyConstraint,
)
from sqlalchemy.orm import relationship
from db.database import Base


class SolutionModel(Base):
    __tablename__ = "solutions"

    event_id = Column(
        Integer, ForeignKey("events.id"), primary_key=True, nullable=False
    )
    answer = Column(Text, nullable=False)
    complete = Column(Boolean, default=False, nullable=False)

    event = relationship("EventModel", back_populates="solutions")

    def __repr__(self):
        return f"<Solution(event_id={self.event_id}, complete={self.complete})>"
