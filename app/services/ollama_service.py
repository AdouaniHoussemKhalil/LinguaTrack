"""Analyse de texte avec un modèle local via Ollama (par défaut deepseek-r1:1.5b).

Particularités gérées ici, observées sur deepseek-r1:1.5b :
- modèle de raisonnement : la réflexion arrive dans `message.thinking`, ou en
  `<think>…</think>` dans le contenu selon la version d'Ollama ; elle est ignorée ;
- sans contrainte, le JSON est entouré de ```json et contient des champs inventés :
  la sortie est donc contrainte par le schéma JSON (paramètre `format`) ;
- qualité limitée (1,5 milliard de paramètres) : erreurs incohérentes et score
  contradictoire, filtrés pour tous les fournisseurs par `llm_common.drop_incoherent` ;
- lent sur CPU (souvent 50 à 100 s) : délai dédié, OLLAMA_TIMEOUT.
"""

import logging
import re

import httpx
from app.core.config import settings
from app.services.llm_common import ANALYSIS_SCHEMA, LLMError, parse_json

logger = logging.getLogger(__name__)

# Texte ≤ 5 000 caractères (~1 500 tokens) + prompt (~1 000) + réponse : 4096 par défaut ne suffit pas
CONTEXT_TOKENS = 8192
MAX_OUTPUT_TOKENS = 4096

UNAVAILABLE = "Le service d'analyse est momentanément indisponible. Réessayez dans quelques instants."

THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def is_configured() -> bool:
    return bool(settings.OLLAMA_MODEL and settings.OLLAMA_URL)


def analyze(system_prompt: str, user_prompt: str, source_text: str) -> dict:
    """Renvoie la réponse du modèle local, sans sa réflexion (à passer à normalize_analysis). Lève LLMError en cas d'échec."""

    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        # Réflexion séparée du contenu (ignorée) ; JSON contraint par le schéma
        "think": True,
        "format": ANALYSIS_SCHEMA,
        "options": {"temperature": 0.2, "num_ctx": CONTEXT_TOKENS, "num_predict": MAX_OUTPUT_TOKENS},
    }

    try:
        response = httpx.post(f"{settings.OLLAMA_URL.rstrip('/')}/api/chat", json=payload, timeout=settings.OLLAMA_TIMEOUT)
    except httpx.TimeoutException as exc:
        logger.warning("Ollama : délai dépassé (%s s)", settings.OLLAMA_TIMEOUT)
        raise LLMError("L'analyse a pris trop de temps. Réessayez avec un texte plus court.") from exc
    except httpx.HTTPError as exc:
        logger.warning("Ollama injoignable sur %s : %s", settings.OLLAMA_URL, exc)
        raise LLMError(UNAVAILABLE) from exc

    if response.status_code == 404:
        logger.error("Modèle Ollama « %s » introuvable : lancer `ollama pull %s`", settings.OLLAMA_MODEL, settings.OLLAMA_MODEL)
        raise LLMError(UNAVAILABLE)
    if response.status_code != 200:
        logger.error("Ollama : erreur HTTP %s (%s)", response.status_code, response.text[:200])
        raise LLMError(UNAVAILABLE)

    try:
        body = response.json()
    except ValueError as exc:
        raise LLMError(UNAVAILABLE) from exc

    if body.get("done_reason") == "length":
        logger.warning("Réponse Ollama tronquée (num_predict=%s)", MAX_OUTPUT_TOKENS)
        raise LLMError("Le texte est trop long pour être analysé en une fois. Essayez de le découper.")

    content = strip_reasoning((body.get("message") or {}).get("content") or "")
    raw = parse_json(content)
    # Le filtrage des erreurs incohérentes est appliqué à tous les fournisseurs (llm_service)
    return raw


def strip_reasoning(content: str) -> str:
    """Retire les balises <think>…</think> et les blocs ```json éventuels autour du JSON."""
    content = THINK_BLOCK.sub("", content)
    # Balise ouvrante sans fermeture (réponse coupée pendant la réflexion)
    if "<think>" in content.lower():
        content = content[content.lower().rfind("</think>") + len("</think>"):] if "</think>" in content.lower() else ""
    return CODE_FENCE.sub("", content.strip()).strip()
