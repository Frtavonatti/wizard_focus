import enum
from uuid import uuid4

from sqlalchemy import Column, ForeignKey, UUID, Integer, Enum, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class SessionStatus(str, enum.Enum):
    completed = "completed"
    abandoned = "abandoned"
    interrupted = "interrupted"


class TimerSession(Base):
    """
    A single focus session started by a user.

    - duration_minutes: the target time the user set.
    - actual_minutes: real time focused. NULL if the session was abandoned before
      any progress was recorded.
    - completed_at: NULL for abandoned or interrupted sessions.
    - status: enforced at DB level via SessionStatus enum.

    Artifacts earned during a session are cascaded on delete.
    """

    __tablename__ = "timer_sessions"

    id = Column(UUID, primary_key=True, index=True, default=uuid4)
    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    actual_minutes = Column(Integer, nullable=True)  # NULL if session was abandoned
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(Enum(SessionStatus), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="timer_sessions")
    artifacts = relationship(
        "Artifact", back_populates="session", cascade="all, delete-orphan"
    )
