from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# URL de connexion PostgreSQL (ajuste selon ton docker-compose)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@db:5432/linguatrack")

engine = create_engine(DATABASE_URL, echo=True)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base pour déclarer les models
Base = declarative_base()


# Dépendance FastAPI pour injecter la session DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()