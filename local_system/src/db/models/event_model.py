from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from ..database import Base


class EventModel(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(Text, nullable=False)
    value = Column(Text, nullable=False)
    time = Column(DateTime, default=datetime.now, nullable=False)

    event_details = relationship(
        "EventDetailModel", back_populates="event", cascade="all, delete-orphan"
    )

    solutions = relationship(
        "SolutionModel", back_populates="event", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Event(id={self.id}, type='{self.type}', time='{self.time}')>"
