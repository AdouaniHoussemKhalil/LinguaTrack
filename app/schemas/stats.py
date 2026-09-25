from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class UserErrorStatsResponse(BaseModel):
    id: UUID
    user_id: UUID
    error_type: str
    count: int
    last_updated: datetime

    class Config:
        from_attributes = True