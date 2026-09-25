import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine
from app.core.migrations import run_migrations
from app.routers import health, text_router, user_router


# ------------------------------
# CONFIGURATION DES LOGS
# ------------------------------
logging.basicConfig(
    level=logging.INFO,  # DEBUG pour tout, INFO pour infos courantes
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


# ------------------------------
# DÉMARRAGE : SCHÉMA DE LA BASE
# ------------------------------
@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Alembic remplace create_all, qui n'ajoutait jamais de colonne à une table existante
    run_migrations(engine)
    yield


# ------------------------------
# CRÉATION DE L'APP FASTAPI
# ------------------------------
app = FastAPI(title="LinguaTrack API", lifespan=lifespan)

# ------------------------------
# CONFIGURATION CORS
# ------------------------------
# Origines lues dans CORS_ORIGINS (défaut : le front Vite en local)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------
# ROUTERS
# ------------------------------
# Import direct : une erreur dans un router doit empêcher le démarrage,
# pas donner une API silencieusement incomplète.
app.include_router(health.router)
app.include_router(text_router.router)
app.include_router(user_router.router)

# ------------------------------
# ROUTE TEST
# ------------------------------
@app.get("/")
def read_root():
    return {"message": "API is running"}
