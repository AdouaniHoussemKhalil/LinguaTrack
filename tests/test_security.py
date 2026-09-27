import os, uuid, pytest
from pydantic import ValidationError

def test_settings_require_secret_key(monkeypatch):
    from app.core.config import Settings
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)

def test_settings_defaults(monkeypatch):
    from app.core.config import Settings
    for k in ("DATABASE_URL", "CORS_ORIGINS"):
        monkeypatch.delenv(k, raising=False)
    s = Settings(_env_file=None, SECRET_KEY="x", CORS_ORIGINS="http://a.test, http://b.test")
    assert s.DATABASE_URL.startswith("sqlite") and s.env == "dev"
    assert s.cors_origins == ["http://a.test", "http://b.test"]

def test_users_me(client):
    email = f"u{uuid.uuid4().hex[:8]}@exemple.com"
    r = client.post("/users/register", json={"email": email, "password": "Abcdef12", "firstName": "Ana", "lastName": "Lima"})
    body = r.json(); assert body["is_success"], body
    token, uid = body["access_token"], body["user_id"]
    assert client.get("/users/me").status_code == 401
    me = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["email"] == email and me.json()["first_name"] == "Ana" and "password" not in me.json()
    # l'ancienne route publique n'existe plus
    assert client.get(f"/users/{uid}").status_code in (404, 405)

def test_cors_only_allowed_origin(client):
    ok = client.get("/health/", headers={"Origin": "http://localhost:5173"})
    ko = client.get("/health/", headers={"Origin": "http://evil.test"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in ko.headers
