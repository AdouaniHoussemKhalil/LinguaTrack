import os, uuid, pytest
from pydantic import ValidationError

@pytest.mark.parametrize("missing", ["AUTH_APP_ID", "AUTH_APP_SECRET"])
def test_settings_require_auth_credentials(monkeypatch, missing):
    from app.core.config import Settings
    monkeypatch.delenv(missing, raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)

def test_settings_defaults(monkeypatch):
    from app.core.config import Settings
    for k in ("DATABASE_URL", "CORS_ORIGINS"):
        monkeypatch.delenv(k, raising=False)
    s = Settings(_env_file=None, CORS_ORIGINS="http://a.test, http://b.test")
    assert s.DATABASE_URL.startswith("sqlite") and s.env == "dev"
    assert s.cors_origins == ["http://a.test", "http://b.test"]

def test_users_me(client):
    from helpers import register_user
    h, uid = register_user(client, email="ana@exemple.com")
    assert client.get("/users/me").status_code == 401
    me = client.get("/users/me", headers=h)
    assert me.status_code == 200 and me.json()["email"] == "ana@exemple.com" and me.json()["first_name"] == "Ana"
    assert "password" not in me.json() and "auth_user_id" not in me.json()
    # l'ancienne route publique et les anciennes routes de connexion n'existent plus
    assert client.get(f"/users/{uid}").status_code in (404, 405)
    for path in ("/users/register", "/users/login", "/users/token"):
        assert client.post(path, json={}).status_code in (404, 405)

def test_cors_only_allowed_origin(client):
    ok = client.get("/health/", headers={"Origin": "http://localhost:5173"})
    ko = client.get("/health/", headers={"Origin": "http://evil.test"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in ko.headers
