from uuid import uuid4

from sqlalchemy import Column, ForeignKey, UUID, Integer, DateTime, text
from sqlalchemy.orm import relationship

from database import Base


class Stats(Base):
    __tablename__ = "user_stats"

    id = Column(UUID, primary_key=True, index=True, default=uuid4)
    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    total_minutes = Column(Integer, nullable=False, default=0, server_default=text("0"))
    total_sessions = Column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    current_strike = Column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    longest_strike = Column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    last_session_date = Column(DateTime(timezone=True))

    # Relationships
    user = relationship("User", back_populates="stats")
