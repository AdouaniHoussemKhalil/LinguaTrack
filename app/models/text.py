import uuid
from sqlalchemy import Column, Text, ForeignKey, DateTime, String, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class TextSubmission(Base):
    __tablename__ = "texts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    original_text = Column(Text, nullable=False)
    corrected_text = Column(Text, nullable=False)

    mode = Column(String, nullable=False, default="correction")
    target_level = Column(String, nullable=True)

    score = Column(Float, nullable=True)  # ex: 78.5 / 100
    feedback = Column(Text, nullable=True)  # appréciation globale du LLM (NULL pour les textes antérieurs)
    processing_time = Column(Float, nullable=True)  # en secondes

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="texts")
    errors = relationship("Error", back_populates="text")