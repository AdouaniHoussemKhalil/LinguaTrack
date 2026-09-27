import json
from types import SimpleNamespace
from app.core.config import settings
from app.services import llm_service
from app.services.llm_common import normalize_analysis

RAW = {"corrected_text": "Ils jouent.", "score": 70, "feedback": "ok", "grammar_errors": []}

def test_mistral_request_uses_configured_model_and_strict_schema(monkeypatch):
    seen = {}
    class FakeChat:
        def complete(self, **kwargs):
            seen.update(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps(RAW)))])
    monkeypatch.setattr(llm_service, "Mistral", lambda api_key: SimpleNamespace(chat=FakeChat()))
    monkeypatch.setattr(settings, "MISTRAL_MODEL", "ministral-8b-latest")
    assert llm_service._analyze_with_mistral("S", "U") == RAW
    assert seen["model"] == "ministral-8b-latest"
    rf = seen["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True
    assert rf["json_schema"]["schema"]["required"] == ["corrected_text", "score", "feedback", "grammar_errors"]

def test_default_mistral_model_is_accessible_one():
    from app.core.config import Settings
    assert Settings(_env_file=None, SECRET_KEY="x").MISTRAL_MODEL == "ministral-8b-latest"

def test_feedback_object_becomes_text():
    raw = {**RAW, "feedback": {"global": "Deux erreurs d'accord.", "suggestions": ["Relisez les accords.", "Vérifiez les terminaisons."]}}
    assert normalize_analysis(raw)["feedback"] == "Deux erreurs d'accord.\nRelisez les accords.\nVérifiez les terminaisons."
    assert normalize_analysis({**RAW, "feedback": None})["feedback"] == ""

def test_incoherent_mistral_error_is_dropped_by_chain(monkeypatch):
    # Cas réel observé avec ministral-8b : « jouent → jouent » (fragment absent du texte, correction identique)
    text = "Les enfants joue dans le jardin pendant que les parents prépare le repas."
    raw = {"corrected_text": "Les enfants jouent dans le jardin pendant que les parents préparent le repas.", "score": 70, "feedback": "ok",
           "grammar_errors": [
               {"original": "jouent", "corrected": "jouent", "explanation": "x", "error_type": "accord", "severity": "high"},
               {"original": "prépare", "corrected": "préparent", "explanation": "y", "error_type": "conjugaison", "severity": "high"}]}
    monkeypatch.setattr(llm_service, "_analyze_with_mistral", lambda *a: raw)
    r = llm_service.generate_analysis(text, "correction", "B1")
    assert [(e["original"], e["corrected"]) for e in r["grammar_errors"]] == [("prépare", "préparent")]
    assert r["score"] == 70.0
