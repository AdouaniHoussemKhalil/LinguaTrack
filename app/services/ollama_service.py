"""Analyse de texte avec un modèle local via Ollama (par défaut deepseek-r1:1.5b).

Particularités gérées ici, observées sur deepseek-r1:1.5b :
- modèle de raisonnement : la réflexion arrive dans `message.thinking`, ou en
  `<think>…</think>` dans le contenu selon la version d'Ollama ; elle est ignorée ;
- sans contrainte, le JSON est entouré de ```json et contient des champs inventés :
  la sortie est donc contrainte par le schéma JSON (paramètre `format`) ;
- qualité limitée (1,5 milliard de paramètres) : erreurs incohérentes et score
  contradictoire, filtrés par `clean_small_model_output` ;
- lent sur CPU (souvent 50 à 100 s) : délai dédié, OLLAMA_TIMEOUT.
"""

import logging
import re
import unicodedata

import httpx
from app.core.config import settings
from app.services.llm_common import ANALYSIS_SCHEMA, LLMError, parse_json

logger = logging.getLogger(__name__)

# Texte ≤ 5 000 caractères (~1 500 tokens) + prompt (~1 000) + réponse : 4096 par défaut ne suffit pas
CONTEXT_TOKENS = 8192
MAX_OUTPUT_TOKENS = 4096

UNAVAILABLE = "Le service d'analyse est momentanément indisponible. Réessayez dans quelques instants."

# Corrections que le petit modèle renvoie à la place d'un vrai fragment corrigé
PLACEHOLDER_CORRECTIONS = {"correct", "correcte", "ok", "aucune", "aucun", "rien", "none", "n/a", "-", "..."}

THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def is_configured() -> bool:
    return bool(settings.OLLAMA_MODEL and settings.OLLAMA_URL)


def analyze(system_prompt: str, user_prompt: str, source_text: str) -> dict:
    """Renvoie la réponse du modèle local, nettoyée (à passer à normalize_analysis). Lève LLMError en cas d'échec."""

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
    return clean_small_model_output(raw, source_text)


def strip_reasoning(content: str) -> str:
    """Retire les balises <think>…</think> et les blocs ```json éventuels autour du JSON."""
    content = THINK_BLOCK.sub("", content)
    # Balise ouvrante sans fermeture (réponse coupée pendant la réflexion)
    if "<think>" in content.lower():
        content = content[content.lower().rfind("</think>") + len("</think>"):] if "</think>" in content.lower() else ""
    return CODE_FENCE.sub("", content.strip()).strip()


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFC", value).casefold()
    return re.sub(r"\s+", " ", value).strip()


def clean_small_model_output(raw: dict, source_text: str) -> dict:
    """Écarte ce que le petit modèle produit d'incohérent, sans rien inventer à sa place.

    - erreur retenue seulement si le fragment original figure dans le texte soumis
      et que la correction est réelle (non vide, différente, pas « correct ») ;
    - score ignoré (None) s'il annonce 100 alors qu'il reste des erreurs ou que
      le texte a été modifié : l'interface affiche alors « – » au lieu d'un score faux.
    """
    source = _normalize(source_text)
    kept, dropped = [], 0

    for error in raw.get("grammar_errors") or []:
        if not isinstance(error, dict):
            dropped += 1
            continue
        original = _normalize(str(error.get("original") or ""))
        corrected = _normalize(str(error.get("corrected") or ""))
        if not original or original not in source or not corrected or corrected == original or corrected in PLACEHOLDER_CORRECTIONS:
            dropped += 1
            continue
        kept.append(error)

    if dropped:
        logger.info("Ollama : %s erreur(s) incohérente(s) écartée(s) sur %s", dropped, dropped + len(kept))

    cleaned = {**raw, "grammar_errors": kept}

    text_changed = _normalize(str(raw.get("corrected_text") or "")) != source
    try:
        score = float(raw.get("score"))
    except (TypeError, ValueError):
        score = None
    if score is not None and score >= 100 and (kept or text_changed):
        logger.info("Ollama : score 100 contradictoire ignoré")
        cleaned["score"] = None

    return cleaned
