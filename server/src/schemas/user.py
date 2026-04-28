from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr

from schemas.base import BaseRead


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str


class UserRead(BaseRead):
    id: UUID
    email: EmailStr
    username: str
    created_at: datetime
    updated_at: Optional[datetime] = None


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str
