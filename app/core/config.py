from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Configuration de l'API, lue depuis les variables d'environnement puis `app/.env`."""

    model_config = SettingsConfigDict(env_file=APP_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "sqlite:///./linguatrack.db"
    SQL_ECHO: bool = False

    # Obligatoire : l'API refuse de démarrer sans.
    # Générer : python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY: str = Field(min_length=1)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Optionnelle au démarrage : vérifiée au moment de l'appel au LLM
    MISTRAL_API_KEY: Optional[str] = None

    # Repli quand Mistral échoue ; sans clé, pas de repli
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-opus-5"

    # Origines autorisées par CORS, séparées par des virgules
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def env(self) -> str:
        return "dev" if self.DATABASE_URL.startswith("sqlite") else "prod"


settings = Settings()

# Alias conservés pour les imports existants
DATABASE_URL = settings.DATABASE_URL
MISTRAL_API_KEY = settings.MISTRAL_API_KEY
ENV = settings.env
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
