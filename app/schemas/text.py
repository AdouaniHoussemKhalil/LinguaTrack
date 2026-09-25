from pydantic import BaseModel, ConfigDict, Field, field_validator
from uuid import UUID
from typing import Dict, Literal, Optional
from app.models.enums import CorrectionMode, LanguageLevel
from typing import List
from datetime import datetime
from enum import Enum




# Aligné sur la limite du front (et sur la taille de réponse du LLM)
MAX_TEXT_LENGTH = 5000


class TextAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    mode: CorrectionMode = CorrectionMode.correction
    target_level: Optional[LanguageLevel] = None

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Le texte à analyser est vide")
        return value

class TextAnalyzeRequestManyModes(BaseModel):
    text: str
    modes: List[CorrectionMode]
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
    feedback: Optional[str] = None
    processing_time: Optional[float]
    created_at: datetime
    errors: List[ErrorResponse] = []

    model_config = ConfigDict(from_attributes=True)


class TextListResponse(BaseModel):
    texts: List[TextResponse]


class DashboardStatsResponse(BaseModel):
    total_texts: int
    average_score: Optional[float]
    total_errors: int
    average_processing_time: Optional[float]
    recent_texts: List[TextResponse]
    mode_counts: Dict[str, int]
    error_type_counts: Dict[str, int]
    average_score_change: Optional[float]
    total_texts_change: Optional[float]
    total_errors_change: Optional[float]
    change_notes: Dict[str, str]
    average_errors_per_text: float

    mode_percentages: Dict[str, float]

    error_type_percentages: Dict[str, float]
    model_config = ConfigDict(from_attributes=True)

class DashboardPeriod(str, Enum):
    all = "all"
    day = "day"
    week = "week"
    month = "month"
    year = "year" 

class ProgressPoint(BaseModel):
    start: datetime  # début de l'intervalle (UTC)
    texts: int
    average_score: Optional[float]  # None si aucun texte dans l'intervalle
    errors: int


class ProgressResponse(BaseModel):
    period: DashboardPeriod
    granularity: Literal["hour", "day", "week", "month"]
    points: List[ProgressPoint]


class HistoryPeriod(str, Enum):
    all = "all"
    day = "day"
    week = "week"
    month = "month"
    year = "year"

class GetHistoryRequest(BaseModel) :
    period: HistoryPeriod
