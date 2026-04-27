from datetime import datetime
from typing import Optional
from uuid import UUID

from schemas.base import BaseRead


class StatsRead(BaseRead):
    id: UUID
    total_minutes: int
    total_sessions: int
    current_strike: int
    longest_strike: int
    last_session_date: Optional[datetime] = None
