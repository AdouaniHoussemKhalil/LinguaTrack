"""Configuration commune des tests.

Les variables d'environnement sont fixées AVANT l'import de l'application :
aucune valeur n'est lue depuis app/.env, et la base est temporaire (ou
TEST_DATABASE_URL, fournie par la CI pour tester PostgreSQL).
"""

import os
import pathlib
import tempfile

import pytest

_TMP_DIR = pathlib.Path(tempfile.mkdtemp(prefix="linguatrack-tests-"))

os.environ.update({
    "DATABASE_URL": os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{(_TMP_DIR / 'test.db').as_posix()}",
    "SECRET_KEY": "test-secret-key-not-for-production-0123456789",
    "CORS_ORIGINS": "http://localhost:5173",
    "SQL_ECHO": "false",
    "LLM_PROVIDERS": "mistral,ollama,claude",
    "MISTRAL_API_KEY": "test-key",
    "MISTRAL_MODEL": "ministral-8b-latest",
    "ANTHROPIC_API_KEY": "",          # Claude désactivé sauf test explicite
    "ANTHROPIC_MODEL": "claude-opus-5",
    "OLLAMA_MODEL": "",               # Ollama désactivé sauf test explicite
    "OLLAMA_URL": "http://localhost:11434",
})


class _NoNetwork:
    """Remplace les clients LLM : un test qui oublie de simuler l'appel échoue clairement."""

    def __init__(self, *args, **kwargs):
        raise RuntimeError("Appel réseau vers un LLM interdit pendant les tests : simulez-le (monkeypatch).")


@pytest.fixture(autouse=True)
def _block_real_llm_calls(monkeypatch):
    from app.services import claude_service, llm_service, ollama_service

    def refuse(*args, **kwargs):
        raise RuntimeError("Appel réseau vers Ollama interdit pendant les tests : simulez-le (monkeypatch).")

    monkeypatch.setattr(llm_service, "Mistral", _NoNetwork)
    monkeypatch.setattr(ollama_service.httpx, "post", refuse)
    if claude_service.anthropic is not None:
        monkeypatch.setattr(claude_service.anthropic, "Anthropic", _NoNetwork)


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as test_client:  # applique les migrations Alembic au démarrage
        yield test_client
