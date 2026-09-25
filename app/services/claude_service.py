"""Analyse de texte avec Claude (Anthropic) : fournisseur de repli quand Mistral échoue."""

import json
import logging

from app.core.config import settings
from app.services.llm_common import ANALYSIS_SCHEMA, LLMError

try:
    import anthropic
except ImportError:  # Claude est facultatif : l'API doit démarrer sans le paquet
    anthropic = None

logger = logging.getLogger(__name__)

# Correction d'un texte ≤ 5 000 caractères + ses erreurs : large marge sans streaming
MAX_OUTPUT_TOKENS = 16000

UNAVAILABLE = "Le service d'analyse est momentanément indisponible. Réessayez dans quelques instants."


def is_configured() -> bool:
    if not settings.ANTHROPIC_API_KEY:
        return False
    if anthropic is None:
        logger.warning("ANTHROPIC_API_KEY définie mais paquet `anthropic` absent : pip install -r requirements.txt")
        return False
    return True


def analyze(system_prompt: str, user_prompt: str) -> dict:
    """Renvoie la réponse brute de Claude (à passer à normalize_analysis). Lève LLMError en cas d'échec."""

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    try:
        # fallbacks="default" : si le modèle refuse la requête (classifieurs de sécurité),
        # l'API la rejoue côté serveur sur le modèle de repli recommandé.
        response = client.beta.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=MAX_OUTPUT_TOKENS,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            output_config={"format": {"type": "json_schema", "schema": ANALYSIS_SCHEMA}},
        )
    except anthropic.AuthenticationError as exc:
        logger.error("Clé ANTHROPIC_API_KEY refusée")
        raise LLMError(UNAVAILABLE) from exc
    except anthropic.RateLimitError as exc:
        logger.warning("Claude : limite de requêtes atteinte (request_id=%s)", exc.response.headers.get("request-id"))
        raise LLMError(UNAVAILABLE) from exc
    except anthropic.APIStatusError as exc:
        logger.error("Claude : erreur HTTP %s (%s)", exc.status_code, exc.message)
        raise LLMError(UNAVAILABLE) from exc
    except anthropic.APIConnectionError as exc:
        logger.error("Claude injoignable : %s", exc)
        raise LLMError(UNAVAILABLE) from exc

    if response.stop_reason == "refusal":
        logger.warning("Claude a refusé l'analyse (request_id=%s)", response._request_id)
        raise LLMError("Ce texte n'a pas pu être analysé. Reformulez-le puis réessayez.")
    if response.stop_reason == "max_tokens":
        logger.warning("Réponse Claude tronquée (max_tokens=%s)", MAX_OUTPUT_TOKENS)
        raise LLMError("Le texte est trop long pour être analysé en une fois. Essayez de le découper.")

    text = next((block.text for block in response.content if block.type == "text"), None)
    try:
        return json.loads(text) if text else {}
    except json.JSONDecodeError as exc:
        logger.error("JSON Claude invalide (request_id=%s)", response._request_id)
        raise LLMError("Le service d'analyse a renvoyé une réponse inattendue. Réessayez.") from exc
