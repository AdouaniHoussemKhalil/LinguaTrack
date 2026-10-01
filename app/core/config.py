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

    # Service d'authentification (auth-web-app-api) : identifiants de l'application déclarée
    # dans son dashboard. Obligatoires ; le secret ne quitte jamais le serveur.
    AUTH_API_URL: str = "http://localhost:8080"
    AUTH_APP_ID: str = Field(min_length=1)
    AUTH_APP_SECRET: str = Field(min_length=1)
    AUTH_TIMEOUT: float = 30.0
    # Cookies de session réservés à HTTPS (à activer en production)
    COOKIE_SECURE: bool = False

    # Optionnelle au démarrage : vérifiée au moment de l'appel au LLM
    MISTRAL_API_KEY: Optional[str] = None
    # L'abonnement actuel n'ouvre que les modèles Ministral (medium/small : 0 requête/min)
    MISTRAL_MODEL: str = "ministral-8b-latest"

    # Fournisseurs d'analyse essayés dans cet ordre jusqu'au premier succès
    # (un fournisseur non configuré est ignoré)
    LLM_PROVIDERS: str = "mistral,ollama,claude"

    # Claude : facultatif, actif seulement avec une clé (payant)
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-opus-5"

    # Ollama : modèle local gratuit ; OLLAMA_MODEL vide pour le désactiver
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "deepseek-r1:1.5b"
    OLLAMA_TIMEOUT: float = 180.0

    # Nombre maximal d'analyses par utilisateur (chaque analyse appelle un LLM) ; 0 = sans limite
    ANALYSES_PER_HOUR: int = Field(default=30, ge=0)
    ANALYSES_PER_DAY: int = Field(default=200, ge=0)

    # Origines autorisées par CORS, séparées par des virgules
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def llm_providers(self) -> List[str]:
        return [name.strip().lower() for name in self.LLM_PROVIDERS.split(",") if name.strip()]

    @property
    def env(self) -> str:
        return "dev" if self.DATABASE_URL.startswith("sqlite") else "prod"


settings = Settings()

# Alias conservés pour les imports existants
DATABASE_URL = settings.DATABASE_URL
MISTRAL_API_KEY = settings.MISTRAL_API_KEY
ENV = settings.env
