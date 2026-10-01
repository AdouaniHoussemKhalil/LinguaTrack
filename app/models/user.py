import uuid
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    # Compte du service d'authentification (auth-web-app-api) : le mot de passe y est géré.
    # NULL pour un compte créé avant ce service, tant qu'il n'a pas été relié par son e-mail.
    auth_user_id = Column(String, unique=True, index=True, nullable=True)
    email = Column(String, unique=True, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    level = Column(String, default="A2") 
    created_at = Column(DateTime(timezone=True), server_default=func.now())