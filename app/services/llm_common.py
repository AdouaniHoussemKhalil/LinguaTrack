"""Éléments partagés par les fournisseurs d'analyse (Mistral, Claude) : prompt, validation, erreur."""

import json
import logging
import re
import unicodedata
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)

ERROR_TYPES = (
    "grammaire", "orthographe", "conjugaison", "vocabulaire", "syntaxe", "ponctuation",
    "accord", "article", "préposition", "temps", "style", "registre",
)
DEFAULT_ERROR_TYPE = "grammaire"
SEVERITIES = ("low", "medium", "high")


# Forme de la réponse demandée aux LLM ; imposée par sortie structurée (Claude, Ollama)
ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "corrected_text": {"type": "string"},
        "score": {"type": "integer"},
        "feedback": {"type": "string"},
        "grammar_errors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "original": {"type": "string"},
                    "corrected": {"type": "string"},
                    "explanation": {"type": "string"},
                    "error_type": {"type": "string", "enum": list(ERROR_TYPES)},
                    "severity": {"type": "string", "enum": list(SEVERITIES)},
                },
                "required": ["original", "corrected", "explanation", "error_type", "severity"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["corrected_text", "score", "feedback", "grammar_errors"],
    "additionalProperties": False,
}


class LLMError(Exception):
    """Échec de l'analyse par le LLM ; le message est destiné à l'utilisateur (en français)."""


def build_prompts(text: str, mode: str, target_level: Optional[str]) -> Tuple[str, str]:
    """Prompt système et prompt utilisateur, identiques quel que soit le fournisseur."""

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

    return system_prompt, user_prompt


def parse_json(content: Any) -> dict:
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


def _as_text(value: Any) -> str:
    """Texte lisible même si le modèle renvoie un objet ou une liste (ex. {"global": …, "suggestions": […]})."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, (list, tuple)):
        return "\n".join(part for part in (_as_text(v) for v in value) if part)
    return str(value)


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
        "feedback": _as_text(raw.get("feedback")),
        "grammar_errors": errors,
    }


# Corrections renvoyées à la place d'un vrai fragment corrigé (observé sur les petits modèles)
PLACEHOLDER_CORRECTIONS = {"correct", "correcte", "ok", "aucune", "aucun", "rien", "none", "n/a", "-", "..."}


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFC", value).casefold()
    return re.sub(r"\s+", " ", value).strip()


def drop_incoherent(raw: dict, source_text: str) -> dict:
    """Écarte ce qu'un modèle produit d'incohérent, sans rien inventer à sa place (tous fournisseurs).

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
        logger.info("%s erreur(s) incohérente(s) écartée(s) sur %s", dropped, dropped + len(kept))

    cleaned = {**raw, "grammar_errors": kept}

    text_changed = _normalize(str(raw.get("corrected_text") or "")) != source
    try:
        score = float(raw.get("score"))
    except (TypeError, ValueError):
        score = None
    if score is not None and score >= 100 and (kept or text_changed):
        logger.info("Score 100 contradictoire ignoré")
        cleaned["score"] = None

    return cleaned
