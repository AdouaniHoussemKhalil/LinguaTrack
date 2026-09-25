import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import Base, engine
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
# CRÉATION DE L'APP FASTAPI
# ------------------------------
app = FastAPI(title="LinguaTrack API")


# ------------------------------
# Database
#-------------------------------

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

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
