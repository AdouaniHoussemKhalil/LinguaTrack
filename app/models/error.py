import uuid
from sqlalchemy import Column, DateTime, Integer, String, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

class Error(Base):
    __tablename__ = "errors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    text_id = Column(UUID(as_uuid=True), ForeignKey("texts.id"))

    error_type = Column(String, nullable=False)
    severity = Column(String, nullable=True)

    original_fragment = Column(Text, nullable=False)
    corrected_fragment = Column(Text, nullable=False)

    explanation = Column(Text)

    position_start = Column(Integer, nullable=True)
    position_end = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    text = relationship("TextSubmission", back_populates="errors")