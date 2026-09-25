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


# Ce que chaque mode demande au modèle d'écrire dans "corrected_text".
# Quel que soit le mode, seules les vraies fautes sont listées et notées (voir build_prompts).
MODE_INSTRUCTIONS = {
    "correction": (
        "Correction seule. Corrige uniquement les fautes de langue, sans rien reformuler : garde les mots, "
        "le style, le registre et la structure de l'auteur. Une phrase correcte doit rester strictement identique. "
        "Si le texte ne contient aucune faute, renvoie-le tel quel, sans erreur, avec la note 100."
    ),
    "professional": (
        "Réécriture professionnelle. Après correction, réécris le texte dans un registre professionnel : "
        "vouvoiement, ton courtois et soutenu, vocabulaire précis, sans familiarités ni abréviations "
        "(« stp », « t'as »…). Garde le même message et la même longueur approximative."
    ),
    "simple": (
        "Simplification. Après correction, réécris le texte pour qu'il soit facile à lire : phrases courtes "
        "(une idée par phrase), mots courants à la place des mots rares ou soutenus, tournures directes. "
        "Garde tout le sens du texte."
    ),
    "natural": (
        "Formulation naturelle. Après correction, reformule ce qui sonne maladroit ou non idiomatique pour que "
        "le texte se lise comme s'il avait été écrit par un francophone natif, en gardant le registre d'origine."
    ),
    "persuasive": (
        "Réécriture persuasive. Après correction, rends le texte plus convaincant : mets en valeur les bénéfices, "
        "enchaîne les idées avec des connecteurs logiques, termine par une phrase qui pousse à agir si c'est "
        "pertinent. Reste crédible : pas d'exagération ni d'affirmation que le texte ne permet pas de faire."
    ),
}

LEVEL_LABELS = {
    "A1": "débutant", "A2": "élémentaire", "B1": "intermédiaire",
    "B2": "intermédiaire avancé", "C1": "avancé", "C2": "maîtrise",
}


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

    mode_instruction = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["correction"])
    level = (
        f"{target_level} ({LEVEL_LABELS[target_level]}) : adapte le vocabulaire des explications à ce niveau."
        if target_level in LEVEL_LABELS
        else "non précisé"
    )

    user_prompt = f"""
Analyse le texte suivant.

Texte :
{text}

Mode — {mode_instruction}

Niveau de l'apprenant : {level}

Consignes :

- "corrected_text" : le texte produit selon le mode ci-dessus.
- "grammar_errors" : UNIQUEMENT les vraies fautes de langue du texte original (orthographe, grammaire,
  conjugaison, accord, ponctuation…). Une reformulation, un choix de style ou un changement de registre
  demandé par le mode n'est PAS une faute : ne le liste pas. Une tournure familière correcte n'est pas une faute.
  Pas des fautes (à ne pas lister) : « super » → « excellent », « boulot » → « travail », « ok » → « d'accord »,
  « on » → « nous ». De vraies fautes (à lister) : « si j'aurais » → « si j'avais », « les fleurs qu'il a cueilli »
  → « les fleurs qu'il a cueillies », « bien qu'il est » → « bien qu'il soit ».
- "original" : le passage fautif recopié exactement tel qu'il apparaît dans le texte ; "corrected" : sa correction.
- "score" : note de 0 à 100 de la correction de la langue du texte original. 100 = aucune faute.
  Les reformulations demandées par le mode ne font pas baisser la note.
- "feedback" : deux ou trois phrases d'appréciation globale et un conseil pour progresser.
- N'invente aucune information : pas de signature, pas de nom, pas de texte entre crochets à compléter,
  pas de nouvelle idée ni de phrase de conclusion ajoutée (seul le mode persuasif peut ajouter un appel à l'action).
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


# Variantes typographiques que les modèles substituent sans que ce soit une correction
TYPOGRAPHY = str.maketrans({
    "’": "'", "‘": "'", "ʼ": "'",   # apostrophes courbes → droite
    "“": '"', "”": '"', "«": '"', "»": '"',  # guillemets
    " ": " ", " ": " ",                  # espaces insécables (avant ; : ! ?)
})


def _normalize(value: str) -> str:
    """Forme de comparaison : insensible à la casse, aux espaces et à la typographie."""
    value = unicodedata.normalize("NFC", value).translate(TYPOGRAPHY).casefold()
    return re.sub(r"\s+", " ", value).strip()


def drop_incoherent(raw: dict, source_text: str) -> dict:
    """Écarte ce qu'un modèle produit d'incohérent, sans rien inventer à sa place (tous fournisseurs).

    - erreur retenue seulement si le fragment original figure dans le texte soumis
      et que la correction est réelle (non vide, différente, pas « correct ») ;
    - score ignoré (None) s'il annonce 100 alors qu'il liste des erreurs : l'interface
      affiche alors « – » au lieu d'un score faux. Un texte corrigé différent ne suffit
      pas : les modes de réécriture (professionnel, simple…) le modifient par principe.
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

    try:
        score = float(raw.get("score"))
    except (TypeError, ValueError):
        score = None
    if score is not None and score >= 100 and kept:
        logger.info("Score 100 contradictoire ignoré")
        cleaned["score"] = None

    return cleaned
