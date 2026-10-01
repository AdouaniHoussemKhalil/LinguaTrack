import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.text import TextSubmission
from helpers import register_user
from app.services import text_service
from app.services.llm_common import LLMError, normalize_analysis

OK = {"corrected_text": "Ok.", "score": 100, "feedback": "", "grammar_errors": []}


def _user(client):
    headers, user_id = register_user(client)
    return uuid.UUID(user_id), headers


def _past_analyses(user_id, minutes_ago):
    db = SessionLocal(); now = datetime.now(timezone.utc)
    for m in minutes_ago:
        db.add(TextSubmission(id=uuid.uuid4(), user_id=user_id, original_text="x", corrected_text="x", mode="correction",
                              score=100, created_at=now - timedelta(minutes=m)))
    db.commit(); db.close()


@pytest.fixture
def llm_calls(monkeypatch):
    calls = []
    def fake(**kwargs):
        calls.append(kwargs)
        return normalize_analysis(OK)
    monkeypatch.setattr(text_service, "generate_analysis", fake)
    return calls


def test_hourly_limit_blocks_before_calling_llm(client, monkeypatch, llm_calls):
    monkeypatch.setattr(settings, "ANALYSES_PER_HOUR", 3)
    uid, h = _user(client)
    _past_analyses(uid, [50, 20, 5])  # 3 analyses dans l'heure ; la plus ancienne libère sa place dans ~10 min
    r = client.post("/texts/analyze", json={"text": "Bonjour."}, headers=h)
    assert r.status_code == 429
    assert r.json()["detail"] == "Limite de 3 analyses par heure atteinte. Réessayez dans 10 minutes."
    assert 500 <= int(r.headers["Retry-After"]) <= 600
    assert llm_calls == []


def test_older_analyses_do_not_count(client, monkeypatch, llm_calls):
    monkeypatch.setattr(settings, "ANALYSES_PER_HOUR", 2)
    uid, h = _user(client)
    _past_analyses(uid, [90, 70, 61])  # hors de la dernière heure
    assert client.post("/texts/analyze", json={"text": "Bonjour."}, headers=h).status_code == 200
    assert len(llm_calls) == 1


def test_daily_limit(client, monkeypatch, llm_calls):
    monkeypatch.setattr(settings, "ANALYSES_PER_HOUR", 0)
    monkeypatch.setattr(settings, "ANALYSES_PER_DAY", 2)
    uid, h = _user(client)
    _past_analyses(uid, [60 * 20, 60 * 5])
    r = client.post("/texts/analyze", json={"text": "Bonjour."}, headers=h)
    assert r.status_code == 429 and "2 analyses par jour" in r.json()["detail"] and "4 heures" in r.json()["detail"]


def test_zero_means_unlimited(client, monkeypatch, llm_calls):
    monkeypatch.setattr(settings, "ANALYSES_PER_HOUR", 0)
    monkeypatch.setattr(settings, "ANALYSES_PER_DAY", 0)
    uid, h = _user(client)
    _past_analyses(uid, list(range(1, 60)))
    assert client.post("/texts/analyze", json={"text": "Bonjour."}, headers=h).status_code == 200


def test_failed_analyses_do_not_consume_quota(client, monkeypatch):
    monkeypatch.setattr(settings, "ANALYSES_PER_HOUR", 1)
    _, h = _user(client)
    monkeypatch.setattr(text_service, "generate_analysis", lambda **_: (_ for _ in ()).throw(LLMError("indisponible")))
    assert client.post("/texts/analyze", json={"text": "Bonjour."}, headers=h).status_code == 502
    monkeypatch.setattr(text_service, "generate_analysis", lambda **_: normalize_analysis(OK))
    assert client.post("/texts/analyze", json={"text": "Bonjour."}, headers=h).status_code == 200
    assert client.post("/texts/analyze", json={"text": "Bonjour."}, headers=h).status_code == 429


def test_quota_is_per_user(client, monkeypatch, llm_calls):
    monkeypatch.setattr(settings, "ANALYSES_PER_HOUR", 1)
    uid, h = _user(client)
    _, other_h = _user(client)
    _past_analyses(uid, [5])
    assert client.post("/texts/analyze", json={"text": "Bonjour."}, headers=h).status_code == 429
    assert client.post("/texts/analyze", json={"text": "Bonjour."}, headers=other_h).status_code == 200
