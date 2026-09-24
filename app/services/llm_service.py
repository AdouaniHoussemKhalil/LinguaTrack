import json
import re
from mistralai import Mistral
from app.core.config import settings

MODEL = "mistral-medium-latest"


def generate_analysis(text: str, mode: str, target_level: str):

    api_key = settings.MISTRAL_API_KEY
    if not api_key:
        raise ValueError("MISTRAL_API_KEY not set in environment variables")

    client = Mistral(api_key=api_key)

    system_prompt = """
You are an expert French language teacher and evaluator.

IMPORTANT RULES:

- Always answer in French.
- Return ONLY valid JSON.
- Do not add markdown.
- Do not add explanations outside the JSON.
- Never invent JSON fields.
- Keep explanations short, clear and educational.

The field "error_type" MUST ALWAYS be EXACTLY one of these values:

- grammaire
- orthographe
- conjugaison
- vocabulaire
- syntaxe
- ponctuation
- accord
- article
- préposition
- temps
- style
- registre

Never use English values such as:
grammar
spelling
conjugation
syntax
register
style
etc.

Always use the French values listed above.
"""

    user_prompt = f"""
Analyse le texte suivant.

Texte :
{text}

Mode :
{mode}

Niveau cible :
{target_level}

Consignes :

- Corrige complètement le texte.
- Donne une note entre 0 et 100.
- Toutes les explications doivent être écrites en français.
- Tous les types d'erreurs doivent être écrits en français.
- Chaque erreur doit appartenir à UNE SEULE catégorie de la liste imposée.

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
            "error_type": "orthographe"
        }}
    ]
}}
"""

    chat_response = client.chat.complete(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        temperature=0.2,
        max_tokens=700
    )

    content = chat_response.choices[0].message.content

    json_match = re.search(r"\{.*\}", content, re.DOTALL)

    if not json_match:
        raise ValueError("No JSON found in LLM response")

    try:
        return json.loads(json_match.group())
    except json.JSONDecodeError:
        raise ValueError("LLM returned invalid JSON")