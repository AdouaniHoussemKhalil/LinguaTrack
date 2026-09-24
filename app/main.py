import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import Base, engine


# ------------------------------
# CONFIGURATION DES LOGS
# ------------------------------
logging.basicConfig(
    level=logging.INFO,  # DEBUG pour tout, INFO pour infos courantes
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# ------------------------------
# CHARGEMENT DU .ENV
# ------------------------------
try:
    env_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=env_path)
    logger.info(".env loaded successfully")
except Exception as e:
    logger.error(f"Error loading .env: {e}")



# ------------------------------
# CRÉATION DE L'APP FASTAPI
# ------------------------------
app = FastAPI()


# ------------------------------
# Database
#-------------------------------

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

# ------------------------------
# CONFIGURATION CORS
# ------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------
# IMPORT DES ROUTERS
# ------------------------------
try:
    from app.routers import health, text_router, user_router

    app.include_router(health.router)
    app.include_router(text_router.router)
    app.include_router(user_router.router)
    logger.info("Routers included successfully")
except Exception as e:
    logger.error(f"Error importing routers: {e}")

# ------------------------------
# ROUTE TEST
# ------------------------------
@app.get("/")
def read_root():
    logger.info("Root endpoint called")
    return {"message": "API is running"}