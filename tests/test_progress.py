import uuid
from datetime import datetime, timedelta, timezone
from app.services.progress_service import auto_granularity, bucket_start, get_user_progress, next_bucket

UTC = timezone.utc

def test_bucket_boundaries():
    d = datetime(2026, 12, 31, 23, 45, tzinfo=UTC)
    assert bucket_start(d, "hour") == datetime(2026, 12, 31, 23, tzinfo=UTC)
    assert bucket_start(d, "day") == datetime(2026, 12, 31, tzinfo=UTC)
    assert bucket_start(d, "week") == datetime(2026, 12, 28, tzinfo=UTC)  # lundi
    assert bucket_start(d, "month") == datetime(2026, 12, 1, tzinfo=UTC)
    assert next_bucket(datetime(2026, 12, 1, tzinfo=UTC), "month") == datetime(2027, 1, 1, tzinfo=UTC)
    assert next_bucket(datetime(2026, 1, 1, tzinfo=UTC), "month") == datetime(2026, 2, 1, tzinfo=UTC)
    assert bucket_start(datetime(2026, 5, 3, 10), "day") == datetime(2026, 5, 3, tzinfo=UTC)  # date naïve = UTC

def test_auto_granularity():
    now = datetime(2026, 9, 25, tzinfo=UTC)
    assert auto_granularity(now - timedelta(days=10), now) == "day"
    assert auto_granularity(now - timedelta(days=200), now) == "week"
    assert auto_granularity(now - timedelta(days=800), now) == "month"

def _seed(client):
    from app.core.database import SessionLocal
    from app.models.error import Error
    from app.models.text import TextSubmission
    body = client.post("/users/register", json={"email": f"g{uuid.uuid4().hex[:8]}@x.com", "password": "Abcdef12", "firstName": "A", "lastName": "B"}).json()
    uid = uuid.UUID(body["user_id"]); now = datetime.now(UTC)
    db = SessionLocal()
    for days_ago, score, n_err in [(0, 90, 0), (0, 70, 2), (3, 60, 3), (20, None, 1)]:
        t = TextSubmission(id=uuid.uuid4(), user_id=uid, original_text="x", corrected_text="x", mode="correction",
                           score=score, created_at=now - timedelta(days=days_ago, minutes=5))
        t.errors = [Error(id=uuid.uuid4(), error_type="accord", original_fragment="a", corrected_fragment="b") for _ in range(n_err)]
        db.add(t)
    db.commit(); db.close()
    return uid, {"Authorization": f"Bearer {body['access_token']}"}

def test_progress_week(client):
    _, h = _seed(client)
    r = client.get("/texts/progress", params={"period": "week"}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json(); pts = body["points"]
    assert body["granularity"] == "day" and len(pts) == 8   # 7 jours + aujourd'hui
    today, three_days = pts[-1], pts[-4]
    assert (today["texts"], today["average_score"], today["errors"]) == (2, 80.0, 2)
    assert (three_days["texts"], three_days["average_score"], three_days["errors"]) == (1, 60.0, 3)
    assert sum(p["texts"] for p in pts) == 3 and pts[1]["average_score"] is None  # intervalle vide

def test_progress_all_auto_and_null_score(client):
    _, h = _seed(client)
    body = client.get("/texts/progress", headers=h).json()
    assert body["granularity"] == "day" and sum(p["texts"] for p in body["points"]) == 4
    old = next(p for p in body["points"] if p["texts"] == 1 and p["errors"] == 1)
    assert old["average_score"] is None  # texte sans score : compté, mais pas dans la moyenne

def test_progress_empty_and_auth(client):
    body = client.post("/users/register", json={"email": f"e{uuid.uuid4().hex[:8]}@x.com", "password": "Abcdef12", "firstName": "A", "lastName": "B"}).json()
    h = {"Authorization": f"Bearer {body['access_token']}"}
    assert client.get("/texts/progress", headers=h).json()["points"] == []
    assert len(client.get("/texts/progress", params={"period": "day"}, headers=h).json()["points"]) == 25
    assert client.get("/texts/progress").status_code == 401
    assert client.get("/texts/progress", params={"period": "decade"}, headers=h).status_code == 422
