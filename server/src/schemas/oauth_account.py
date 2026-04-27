from datetime import datetime
from uuid import UUID

from schemas.base import BaseRead


class OAuthAccountRead(BaseRead):
    id: UUID
    provider: str
    created_at: datetime
