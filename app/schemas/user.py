from pydantic import BaseModel, ConfigDict, EmailStr, Field
from uuid import UUID
from datetime import datetime
from typing import Optional
from app.models.enums import LanguageLevel


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    firstName: str
    lastName: str
    level: LanguageLevel = LanguageLevel.A2


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    firstName: str = Field(alias="first_name")
    lastName: str = Field(alias="last_name")
    level: Optional[LanguageLevel]
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )


class LoginRequest(BaseModel):
    username: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"