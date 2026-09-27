import uuid
from datetime import datetime, timedelta, timezone
import pytest
from app.services import text_service
from app.services.llm_service import LLMError, normalize_analysis

def register(client, level=None):
    payload = {"email": f"u{uuid.uuid4().hex[:8]}@exemple.com", "password": "Abcdef12", "firstName": "A", "lastName": "B"}
    if level: payload["level"] = level
    body = client.post("/users/register", json=payload).json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["user_id"]

FAKE = {"corrected_text": "Ça va.", "score": 130, "feedback": "Bien", "grammar_errors": [
    {"original": "sa", "corrected": "ça", "explanation": "cédille", "error_type": "Orthographe", "severity": "HIGH"},
    {"original": "x", "corrected": "y", "explanation": "", "error_type": "grammar", "severity": "critical"}]}

def test_normalize_analysis():
    r = normalize_analysis(FAKE)
    assert r["score"] == 100.0
    assert [e["error_type"] for e in r["grammar_errors"]] == ["orthographe", "grammaire"]
    assert [e["severity"] for e in r["grammar_errors"]] == ["high", None]
    with pytest.raises(LLMError):
        normalize_analysis({"score": 50})

def test_register_keeps_level(client):
    headers, _ = register(client, "C1")
    assert client.get("/users/me", headers=headers).json()["level"] == "C1"
    headers, _ = register(client)
    assert client.get("/users/me", headers=headers).json()["level"] == "A2"

def test_analyze_uses_user_level_and_saves_errors(client, monkeypatch):
    seen = {}
    def fake(text, mode, target_level):
        seen.update(mode=mode, level=target_level); return normalize_analysis(FAKE)
    monkeypatch.setattr(text_service, "generate_analysis", fake)
    headers, uid = register(client, "B2")
    r = client.post("/texts/analyze", json={"text": "sa va", "mode": "simple"}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert seen == {"mode": "simple", "level": "B2"}
    assert body["target_level"] == "B2" and body["score"] == 100.0
    assert [e["severity"] for e in body["errors"]] == ["high", None]
    detail = client.get(f"/texts/history/{uid}/{body['id']}", headers=headers)
    assert detail.status_code == 200 and len(detail.json()["errors"]) == 2

def test_llm_failure_returns_502_and_saves_nothing(client, monkeypatch):
    def boom(**_): raise LLMError("Le service d'analyse est momentanément indisponible.")
    monkeypatch.setattr(text_service, "generate_analysis", boom)
    headers, _ = register(client)
    r = client.post("/texts/analyze", json={"text": "Bonjour"}, headers=headers)
    assert r.status_code == 502 and "indisponible" in r.json()["detail"]
    assert client.get("/texts/history?period=all", headers=headers).json() == []

def test_request_validation(client):
    headers, uid = register(client)
    assert client.post("/texts/analyze", json={"text": "   "}, headers=headers).status_code == 422
    assert client.post("/texts/analyze", json={"text": "a" * 5001}, headers=headers).status_code == 422
    assert client.get(f"/texts/history/{uid}/pas-un-uuid", headers=headers).status_code == 422
    assert client.get(f"/texts/history/{uuid.uuid4()}/{uuid.uuid4()}", headers=headers).status_code == 403

def test_dashboard_period_filter(client, monkeypatch):
    monkeypatch.setattr(text_service, "generate_analysis", lambda **_: normalize_analysis(FAKE))
    headers, uid = register(client)
    for _ in range(3):
        client.post("/texts/analyze", json={"text": "sa va"}, headers=headers)
    # vieillir 2 textes de 10 jours directement en base
    from app.core.database import SessionLocal
    from app.models.text import TextSubmission
    db = SessionLocal()
    rows = db.query(TextSubmission).filter(TextSubmission.user_id == uuid.UUID(uid)).limit(2).all()
    for row in rows: row.created_at = datetime.now(timezone.utc) - timedelta(days=10)
    db.commit(); db.close()
    all_ = client.get("/texts/dashboard?period=all", headers=headers).json()
    week = client.get("/texts/dashboard?period=week", headers=headers).json()
    month = client.get("/texts/dashboard?period=month", headers=headers).json()
    assert (all_["total_texts"], week["total_texts"], month["total_texts"]) == (3, 1, 3)
    assert week["total_texts_change"] == -50.0  # 1 cette semaine vs 2 la semaine d'avant

def test_feedback_saved_and_returned(client, monkeypatch):
    raw = {**FAKE, "feedback": "Bon travail ; attention aux accords."}
    monkeypatch.setattr(text_service, "generate_analysis", lambda **_: normalize_analysis(raw))
    headers, uid = register(client)
    body = client.post("/texts/analyze", json={"text": "sa va"}, headers=headers).json()
    assert body["feedback"] == "Bon travail ; attention aux accords."
    assert client.get(f"/texts/history/{uid}/{body['id']}", headers=headers).json()["feedback"] == body["feedback"]
