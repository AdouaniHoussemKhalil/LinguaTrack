from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from app.models.enums import CorrectionMode, LanguageLevel
from typing import List
from sqlalchemy import DateTime



class TextAnalyzeRequest(BaseModel):
    text: str
    mode: CorrectionMode = CorrectionMode.correction
    target_level: Optional[LanguageLevel] = None

class ErrorResponse(BaseModel):
    error_type: str
    severity: Optional[str]
    original_fragment: str
    corrected_fragment: str
    explanation: Optional[str]

class TextAnalyzeResponse(BaseModel):
    corrected_text: str
    score: Optional[float]
    errors: List[ErrorResponse]

class TextResponse(BaseModel):
    id: UUID
    original_text: str
    corrected_text: str
    mode: CorrectionMode
    target_level: Optional[LanguageLevel]
    score: Optional[float]
    processing_time: Optional[float]
    created_at: DateTime
    errors: List[ErrorResponse] = []

    class Config:
        from_attributes = True


class TextListResponse(BaseModel):
    texts: List[TextResponse]
