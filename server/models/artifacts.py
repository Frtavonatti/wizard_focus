import enum
from uuid import uuid4

from sqlalchemy import Column, UUID, String, Enum, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class ArtifactRarity(str, enum.Enum):
    common = "common"
    uncommon = "uncommon"
    rare = "rare"
    epic = "epic"
    legendary = "legendary"


class ArtifactCategory(str, enum.Enum):
    spell = "spell"
    potion = "potion"
    relic = "relic"
    tome = "tome"
    staff = "staff"
    crystal = "crystal"


class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(UUID, primary_key=True, index=True, default=uuid4)
    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(
        UUID, ForeignKey("timer_sessions.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String, index=True, nullable=False)
    rarity = Column(Enum(ArtifactRarity), index=True, nullable=False)
    category = Column(Enum(ArtifactCategory), index=True, nullable=False)
    awarded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="artifacts")
    session = relationship("TimerSession", back_populates="artifacts")
