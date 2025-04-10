from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from db.database import Base


class EventDetailModel(Base):
    __tablename__ = "event_details"

    event_id = Column(
        Integer, ForeignKey("events.id"), primary_key=True, nullable=False
    )
    file = Column(Text(length=16777215), nullable=False)
    explain = Column(String(1000), nullable=False)

    event = relationship("EventModel", back_populates="event_details")

    def __repr__(self):
        return f"<EventDetail(event_id={self.event_id})>"
