import json
import logging
import re
from typing import Any, Optional

from mistralai import Mistral
from app.core.config import settings

logger = logging.getLogger(__name__)

MODEL = "mistral-medium-latest"
# 700 tronquait le JSON sur les textes longs ; 4096 couvre un texte de 5 000 caractères corrigé + ses erreurs
MAX_OUTPUT_TOKENS = 4096

ERROR_TYPES = (
    "grammaire", "orthographe", "conjugaison", "vocabulaire", "syntaxe", "ponctuation",
    "accord", "article", "préposition", "temps", "style", "registre",
)
DEFAULT_ERROR_TYPE = "grammaire"
SEVERITIES = ("low", "medium", "high")


class LLMError(Exception):
    """Échec de l'analyse par le LLM ; le message est destiné à l'utilisateur (en français)."""


def generate_analysis(text: str, mode: str, target_level: Optional[str]) -> dict:
    """Appelle Mistral et renvoie une analyse validée : texte corrigé, score 0-100, erreurs normalisées."""

    api_key = settings.MISTRAL_API_KEY
    if not api_key:
        logger.error("MISTRAL_API_KEY absente : analyse impossible")
        raise LLMError("Le service d'analyse n'est pas configuré. Réessayez plus tard.")

    client = Mistral(api_key=api_key)

    system_prompt = f"""
You are an expert French language teacher and evaluator.

IMPORTANT RULES:

- Always answer in French.
- Return ONLY valid JSON.
- Do not add markdown.
- Do not add explanations outside the JSON.
- Never invent JSON fields.
- Keep explanations short, clear and educational.

The field "error_type" MUST ALWAYS be EXACTLY one of these values:

{chr(10).join(f"- {error_type}" for error_type in ERROR_TYPES)}

Never use English values such as:
grammar
spelling
conjugation
syntax
register
style
etc.

Always use the French values listed above.

The field "severity" MUST ALWAYS be EXACTLY one of: low, medium, high.
- low: minor issue (typography, style preference, small punctuation)
- medium: noticeable mistake that does not block understanding
- high: serious mistake (meaning changed, wrong conjugation or agreement, gross spelling error)
"""

    user_prompt = f"""
Analyse le texte suivant.

Texte :
{text}

Mode :
{mode}

Niveau cible :
{target_level or "non précisé"}

Consignes :

- Corrige complètement le texte.
- Donne une note entre 0 et 100.
- Toutes les explications doivent être écrites en français.
- Tous les types d'erreurs doivent être écrits en français.
- Chaque erreur doit appartenir à UNE SEULE catégorie de la liste imposée.
- Chaque erreur doit avoir une sévérité : low, medium ou high.

Retourne STRICTEMENT ce JSON :

{{
    "corrected_text": "...",
    "score": 0,
    "feedback": "...",
    "grammar_errors": [
        {{
            "original": "...",
            "corrected": "...",
            "explanation": "...",
            "error_type": "orthographe",
            "severity": "medium"
        }}
    ]
}}
"""

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

    return normalize_analysis(_parse_json(choice.message.content))


def _parse_json(content: Any) -> dict:
    if not isinstance(content, str):
        raise LLMError("Le service d'analyse a renvoyé une réponse inattendue. Réessayez.")

    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if not json_match:
        logger.warning("Aucun JSON dans la réponse Mistral")
        raise LLMError("Le service d'analyse a renvoyé une réponse inattendue. Réessayez.")

    try:
        return json.loads(json_match.group())
    except json.JSONDecodeError as exc:
        logger.warning("JSON Mistral invalide")
        raise LLMError("Le service d'analyse a renvoyé une réponse inattendue. Réessayez.") from exc


def normalize_analysis(raw: dict) -> dict:
    """Valide et nettoie la réponse du LLM (types d'erreurs imposés, sévérité, score borné)."""

    corrected_text = raw.get("corrected_text")
    if not isinstance(corrected_text, str) or not corrected_text.strip():
        raise LLMError("Le service d'analyse a renvoyé une réponse incomplète. Réessayez.")

    try:
        score: Optional[float] = min(max(float(raw.get("score")), 0.0), 100.0)
    except (TypeError, ValueError):
        score = None

    errors = []
    for item in raw.get("grammar_errors") or []:
        if not isinstance(item, dict):
            continue
        error_type = str(item.get("error_type", "")).strip().lower()
        severity = str(item.get("severity", "")).strip().lower()
        errors.append({
            "original": str(item.get("original") or ""),
            "corrected": str(item.get("corrected") or ""),
            "explanation": str(item.get("explanation") or ""),
            "error_type": error_type if error_type in ERROR_TYPES else DEFAULT_ERROR_TYPE,
            "severity": severity if severity in SEVERITIES else None,
            "position_start": item.get("position_start") if isinstance(item.get("position_start"), int) else None,
            "position_end": item.get("position_end") if isinstance(item.get("position_end"), int) else None,
        })

    return {
        "corrected_text": corrected_text,
        "score": score,
        "feedback": str(raw.get("feedback") or ""),
        "grammar_errors": errors,
    }
