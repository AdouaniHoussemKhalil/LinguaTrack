import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
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


# Même politique que le front (features/auth/schemas/registerSchema.ts)
PASSWORD_RULES = (
    (lambda value: len(value) >= 8, "au moins 8 caractères"),
    (lambda value: re.search(r"[a-z]", value) is not None, "une lettre minuscule"),
    (lambda value: re.search(r"[A-Z]", value) is not None, "une lettre majuscule"),
    (lambda value: re.search(r"[0-9]", value) is not None, "un chiffre"),
)


def check_password_strength(value: str) -> str:
    for rule, label in PASSWORD_RULES:
        if not rule(value):
            raise ValueError(f"Mot de passe trop faible : {label} requis")
    return value


class UserUpdate(BaseModel):
    """Champs modifiables du profil ; un champ absent n'est pas modifié."""

    firstName: Optional[str] = Field(default=None, max_length=100)
    lastName: Optional[str] = Field(default=None, max_length=100)
    level: Optional[LanguageLevel] = None

    @field_validator("firstName", "lastName")
    @classmethod
    def not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Ce champ ne peut pas être vide")
        return value


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong_enough(cls, value: str) -> str:
        return check_password_strength(value)


class LoginRequest(BaseModel):
    username: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"