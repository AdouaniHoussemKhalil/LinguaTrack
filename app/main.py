import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.database import engine
from app.core.migrations import run_migrations
from app.core.session import apply_session
from app.routers import auth_router, health, text_router, user_router
from app.services.auth_client import AuthServiceUnavailable


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
# SESSION (cookies httpOnly) ET SERVICE D'AUTHENTIFICATION
# ------------------------------
@app.middleware("http")
async def apply_session_cookies(request: Request, call_next):
    """Pose ou efface les cookies de session décidés pendant la requête, y compris sur une erreur."""
    response = await call_next(request)
    apply_session(request, response)
    return response


@app.exception_handler(AuthServiceUnavailable)
async def auth_service_unavailable(_request: Request, _exc: AuthServiceUnavailable):
    message = "Service d'authentification indisponible, réessayez dans un instant"
    return JSONResponse(status_code=503, content={"detail": message, "error": {"code": "authUnavailable", "message": message}})


# ------------------------------
# ROUTERS
# ------------------------------
# Import direct : une erreur dans un router doit empêcher le démarrage,
# pas donner une API silencieusement incomplète.
app.include_router(health.router)
app.include_router(auth_router.router)
app.include_router(text_router.router)
app.include_router(user_router.router)

# ------------------------------
# ROUTE TEST
# ------------------------------
@app.get("/")
def read_root():
    return {"message": "API is running"}
