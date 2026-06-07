import os
import json
import re
from mistralai import Mistral

MODEL = "mistral-medium-latest"  

def generate_analysis(text: str, mode: str, target_level: str):

    api_key = os.getenv("MISTRAL_API_KEY") or "5zvcf6eju5u4MoFvCK5gsd9k6xyOI7KB"
    if not api_key:
        raise ValueError("MISTRAL_API_KEY not set in environment variables")
    
    client = Mistral(api_key=api_key)

    system_prompt = """
You are an expert language evaluation AI.

You MUST return valid JSON only.
No explanations outside JSON.
"""

    user_prompt = f"""
Analyze the following text.

TEXT:
{text}

MODE:
{mode}

TARGET LEVEL:
{target_level}

Return strictly this JSON format:

{{
    "corrected_text": "...",
    "score": number between 0 and 100,
    "feedback": "...",
    "grammar_errors": [
        {{
            "original": "...",
            "corrected": "...",
            "explanation": "...",
            "error_type": "...",
        }}
    ]
}}
"""

    chat_response = client.chat.complete(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2,
        max_tokens=500
    )

    content = chat_response.choices[0].message.content

    json_match = re.search(r"\{.*\}", content, re.DOTALL)

    if not json_match:
      raise ValueError("No JSON found in LLM response")

    try:
        return json.loads(json_match.group())
    except json.JSONDecodeError:
        raise ValueError("LLM returned invalid JSON")