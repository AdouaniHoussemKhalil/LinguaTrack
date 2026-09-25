import logging
from typing import Callable, Dict, Optional, Tuple

from mistralai import Mistral
from app.core.config import settings
from app.services import claude_service, ollama_service
from app.services.llm_common import ANALYSIS_SCHEMA, LLMError, build_prompts, drop_incoherent, normalize_analysis, parse_json

# Réexportés pour les imports existants (routers, tests)
__all__ = ["LLMError", "generate_analysis", "normalize_analysis"]

logger = logging.getLogger(__name__)

# 700 tronquait le JSON sur les textes longs ; 4096 couvre un texte de 5 000 caractères corrigé + ses erreurs
MAX_OUTPUT_TOKENS = 4096

NOT_CONFIGURED = "Le service d'analyse n'est pas configuré. Réessayez plus tard."


def generate_analysis(text: str, mode: str, target_level: Optional[str]) -> dict:
    """Analyse validée (texte corrigé, score 0-100, erreurs normalisées).

    Les fournisseurs de LLM_PROVIDERS (défaut : mistral, ollama, claude) sont essayés
    dans l'ordre ; un fournisseur non configuré est ignoré, un échec passe au suivant.
    Lève la dernière LLMError si aucun n'aboutit.
    """
    system_prompt, user_prompt = build_prompts(text, mode, target_level)
    providers = _providers()
    last_error: Optional[LLMError] = None

    for name in settings.llm_providers:
        if name not in providers:
            logger.warning("Fournisseur LLM inconnu ignoré : %s", name)
            continue
        is_configured, analyze = providers[name]
        if not is_configured():
            continue
        try:
            result = normalize_analysis(drop_incoherent(analyze(system_prompt, user_prompt, text), text))
        except LLMError as exc:
            logger.warning("Fournisseur %s en échec (%s) : passage au suivant", name, exc)
            last_error = exc
            continue
        logger.info("Analyse réalisée par %s", name if name != "mistral" else f"mistral ({settings.MISTRAL_MODEL})")
        return result

    if last_error is None:
        logger.error("Aucun fournisseur LLM configuré (LLM_PROVIDERS=%s)", settings.LLM_PROVIDERS)
        raise LLMError(NOT_CONFIGURED)
    raise last_error


def _providers() -> Dict[str, Tuple[Callable[[], bool], Callable[[str, str, str], dict]]]:
    # Résolu à l'appel : les tests peuvent remplacer les fonctions des modules
    return {
        "mistral": (lambda: bool(settings.MISTRAL_API_KEY), _analyze_with_mistral),
        "ollama": (ollama_service.is_configured, ollama_service.analyze),
        "claude": (claude_service.is_configured, lambda system, user, _text: claude_service.analyze(system, user)),
    }


def _analyze_with_mistral(system_prompt: str, user_prompt: str, _source_text: str = "") -> dict:
    client = Mistral(api_key=settings.MISTRAL_API_KEY)

    try:
        chat_response = client.chat.complete(
            model=settings.MISTRAL_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=MAX_OUTPUT_TOKENS,
            # Sortie structurée : forme imposée (json_object ne garantissait qu'un JSON valide)
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "analyse_texte", "schema": ANALYSIS_SCHEMA, "strict": True},
            },
        )
    except Exception as exc:  # réseau, quota, clé invalide… : détail dans les logs, pas pour l'utilisateur
        logger.exception("Appel Mistral en échec")
        raise LLMError("Le service d'analyse est momentanément indisponible. Réessayez dans quelques instants.") from exc

    choice = chat_response.choices[0]
    if choice.finish_reason == "length":
        logger.warning("Réponse Mistral tronquée (max_tokens=%s)", MAX_OUTPUT_TOKENS)
        raise LLMError("Le texte est trop long pour être analysé en une fois. Essayez de le découper.")

    return parse_json(choice.message.content)
