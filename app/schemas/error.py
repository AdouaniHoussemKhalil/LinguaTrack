from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from app.models.enums import ErrorSeverity


class ErrorBase(BaseModel):
    error_type: str
    severity: Optional[ErrorSeverity]
    original_fragment: str
    corrected_fragment: str
    explanation: Optional[str]
    position_start: Optional[int]
    position_end: Optional[int]


class ErrorResponse(ErrorBase):
    id: UUID

    class Config:
        from_attributes = True