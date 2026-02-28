from enum import Enum
import uuid
from sqlalchemy.dialects.postgresql import UUID

class CorrectionMode(str, Enum):
    correction = "correction"
    professional = "professional"
    simple = "simple"
    natural = "natural"
    persuasive = "persuasive"


class LanguageLevel(str, Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class ErrorSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"