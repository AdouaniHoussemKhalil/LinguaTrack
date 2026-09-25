import logging
from typing import Optional

from mistralai import Mistral
from app.core.config import settings
from app.services import claude_service
from app.services.llm_common import LLMError, build_prompts, normalize_analysis, parse_json

# Réexportés pour les imports existants (routers, tests)
__all__ = ["LLMError", "generate_analysis", "normalize_analysis"]

logger = logging.getLogger(__name__)

MODEL = "mistral-medium-latest"
# 700 tronquait le JSON sur les textes longs ; 4096 couvre un texte de 5 000 caractères corrigé + ses erreurs
MAX_OUTPUT_TOKENS = 4096


def generate_analysis(text: str, mode: str, target_level: Optional[str]) -> dict:
    """Analyse validée (texte corrigé, score 0-100, erreurs normalisées).

    Mistral d'abord ; en cas d'échec (quota, panne, réponse invalide ou tronquée),
    repli sur Claude si ANTHROPIC_API_KEY est configurée. Lève LLMError si tout échoue.
    """
    system_prompt, user_prompt = build_prompts(text, mode, target_level)

    try:
        result = _analyze_with_mistral(system_prompt, user_prompt)
        logger.info("Analyse réalisée par Mistral (%s)", MODEL)
        return result
    except LLMError as mistral_error:
        if not claude_service.is_configured():
            raise
        logger.warning("Mistral en échec (%s) : repli sur Claude", mistral_error)

    result = normalize_analysis(claude_service.analyze(system_prompt, user_prompt))
    logger.info("Analyse réalisée par Claude (%s)", settings.ANTHROPIC_MODEL)
    return result


def _analyze_with_mistral(system_prompt: str, user_prompt: str) -> dict:
    api_key = settings.MISTRAL_API_KEY
    if not api_key:
        logger.error("MISTRAL_API_KEY absente : analyse Mistral impossible")
        raise LLMError("Le service d'analyse n'est pas configuré. Réessayez plus tard.")

    client = Mistral(api_key=api_key)

    try:
        chat_response = client.chat.complete(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=MAX_OUTPUT_TOKENS,
            response_format={"type": "json_object"},
        )
    except Exception as exc:  # réseau, quota, clé invalide… : détail dans les logs, pas pour l'utilisateur
        logger.exception("Appel Mistral en échec")
        raise LLMError("Le service d'analyse est momentanément indisponible. Réessayez dans quelques instants.") from exc

    choice = chat_response.choices[0]
    if choice.finish_reason == "length":
        logger.warning("Réponse Mistral tronquée (max_tokens=%s)", MAX_OUTPUT_TOKENS)
        raise LLMError("Le texte est trop long pour être analysé en une fois. Essayez de le découper.")

    return normalize_analysis(parse_json(choice.message.content))
