import uuid
from sqlalchemy import Column, DateTime, String, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class UserErrorStats(Base):
    __tablename__ = "user_error_stats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    error_type = Column(String)
    count = Column(Integer, default=0)
    last_updated = Column(DateTime(timezone=True), server_default=func.now())