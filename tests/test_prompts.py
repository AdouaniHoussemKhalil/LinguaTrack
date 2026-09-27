from app.models.enums import CorrectionMode
from app.services.llm_common import MODE_INSTRUCTIONS, build_prompts

def test_every_mode_has_an_instruction():
    assert set(MODE_INSTRUCTIONS) == {m.value for m in CorrectionMode}

def test_prompt_contains_mode_instruction_and_level():
    _, user = build_prompts("Bonjour.", "simple", "B2")
    assert MODE_INSTRUCTIONS["simple"] in user
    assert "B2 (intermédiaire avancé)" in user and "Bonjour." in user

def test_unknown_mode_and_level_fall_back():
    _, user = build_prompts("Bonjour.", "inconnu", None)
    assert MODE_INSTRUCTIONS["correction"] in user and "non précisé" in user
