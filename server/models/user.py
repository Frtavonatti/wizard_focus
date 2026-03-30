from uuid import uuid4

from sqlalchemy import Column, UUID, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID, primary_key=True, index=True, default=uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)  # nullable to allow Oauth strategy
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    oauth_accounts = relationship(
        "OAuthAccount", back_populates="user", cascade="all, delete-orphan"
    )
    timer_sessions = relationship(
        "TimerSession", back_populates="user", cascade="all, delete-orphan"
    )
    stats = relationship(
        "Stats", back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    artifacts = relationship(
        "Artifact", back_populates="user", cascade="all, delete-orphan"
    )
