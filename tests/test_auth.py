"""Relais /auth et session en cookies httpOnly (service d'authentification simulé)."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.user import User
from helpers import PASSWORD


@pytest.fixture
def browser(client):
    """Navigateur isolé : son propre stockage de cookies (le schéma est déjà migré par `client`)."""
    return TestClient(app)


def signup_payload(email=None, **extra):
    return {"email": email or f"a{uuid.uuid4().hex[:8]}@exemple.com", "password": PASSWORD,
            "confirmPassword": PASSWORD, "firstName": "Ana", "lastName": "Lima", **extra}


def test_register_opens_cookie_session_without_exposing_tokens(browser):
    r = browser.post("/auth/register", json=signup_payload(level="B2"))
    assert r.status_code == 201
    assert "access_token" not in r.text and "refresh_token" not in r.text
    cookies = r.headers.get_list("set-cookie")
    assert all("HttpOnly" in c and "SameSite=lax" in c for c in cookies) and len(cookies) == 2
    me = browser.get("/users/me")
    assert me.status_code == 200 and me.json()["level"] == "B2" and me.json()["mfa_enabled"] is False


def test_secret_and_level_never_sent_to_browser_or_auth_service(browser, auth_service, monkeypatch):
    sent = {}
    original = auth_service.__call__

    def spy(path, method="POST", body=None, access_token=None):
        sent[path] = body
        return original(path, method, body, access_token)

    from app.services import auth_client
    monkeypatch.setattr(auth_client, "call", spy)
    r = browser.post("/auth/register", json=signup_payload(level="C1"))
    assert "test-app-secret" not in r.text
    assert "level" not in sent["/register"]


def test_login_errors_are_relayed(browser, auth_service):
    auth_service.add_user("ana@exemple.com")
    r = browser.post("/auth/login", json={"email": "ana@exemple.com", "password": "Mauvais1!"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalidCredentials"
    assert "set-cookie" not in r.headers


def test_email_verification_then_login(browser, auth_service):
    auth_service.require_email_verification = True
    r = browser.post("/auth/register", json=signup_payload("ver@exemple.com", level="C1"))
    assert r.status_code == 201 and r.json()["emailVerificationRequired"] is True and "set-cookie" not in r.headers
    assert browser.post("/auth/login", json={"email": "ver@exemple.com", "password": PASSWORD}).json()["error"]["code"] == "emailNotVerified"
    code = auth_service.last_code["ver@exemple.com"]
    assert browser.post("/auth/verify-email", json={"email": "ver@exemple.com", "code": code}).status_code == 200
    assert browser.post("/auth/login", json={"email": "ver@exemple.com", "password": PASSWORD}).status_code == 200
    assert browser.get("/users/me").json()["level"] == "C1"  # niveau gardé depuis l'inscription


def test_mfa_login_returns_user_and_opens_session(browser, auth_service):
    auth_service.add_user("mfa@exemple.com", mfa=True)
    first = browser.post("/auth/login", json={"email": "mfa@exemple.com", "password": PASSWORD})
    assert first.json() == {"MFARequired": True} and "set-cookie" not in first.headers
    code = auth_service.last_code["mfa@exemple.com"]
    second = browser.post("/auth/login/mfa", json={"email": "mfa@exemple.com", "mfaCode": code})
    assert second.status_code == 200 and second.json()["user"]["email"] == "mfa@exemple.com"
    assert "returnedUser" not in second.json() and "access_token" not in second.json()
    assert browser.get("/users/me").json()["mfa_enabled"] is True


def test_expired_access_token_is_refreshed_once(browser, auth_service):
    browser.post("/auth/register", json=signup_payload())
    old_refresh = browser.cookies["lt_refresh"]
    auth_service.access.clear()  # access token expiré
    r = browser.get("/users/me")
    assert r.status_code == 200 and browser.cookies["lt_refresh"] != old_refresh
    assert auth_service.calls.count("/refresh") == 1


def test_concurrent_requests_share_one_refresh(client, auth_service):
    from app.services import auth_client
    tab = TestClient(app)
    tab.post("/auth/register", json=signup_payload())
    stale = dict(tab.cookies)
    auth_service.access.clear()
    assert tab.get("/users/me").status_code == 200
    # Une requête partie en même temps avec les anciens cookies ne réutilise pas le refresh token consommé
    other = TestClient(app, cookies=stale)
    assert other.get("/users/me").status_code == 200
    assert auth_service.calls.count("/refresh") == 1
    assert len(auth_client._refreshes) == 1


def test_refreshed_cookies_are_set_even_on_error_response(browser, auth_service):
    browser.post("/auth/register", json=signup_payload())
    old_refresh = browser.cookies["lt_refresh"]
    auth_service.access.clear()
    r = browser.get(f"/texts/{uuid.uuid4()}")
    assert r.status_code == 404 and browser.cookies["lt_refresh"] != old_refresh


def test_invalid_session_clears_cookies(browser, auth_service):
    browser.post("/auth/register", json=signup_payload())
    auth_service.access.clear()
    auth_service.refresh.clear()
    r = browser.get("/users/me")
    assert r.status_code == 401
    assert "lt_access" not in browser.cookies and "lt_refresh" not in browser.cookies


def test_logout_revokes_and_clears(browser, auth_service):
    browser.post("/auth/register", json=signup_payload())
    refresh = browser.cookies["lt_refresh"]
    assert browser.post("/auth/logout").json() == {"isSuccess": True}
    assert refresh not in auth_service.refresh
    assert browser.get("/users/me").status_code == 401


def test_blocked_account_is_refused(browser, auth_service):
    browser.post("/auth/register", json=signup_payload("bloque@exemple.com"))
    auth_service.users["bloque@exemple.com"]["active"] = False
    assert browser.get("/users/me").status_code == 403


def test_auth_service_down_returns_503(browser, monkeypatch):
    from app.services import auth_client

    def down(*_a, **_k):
        raise auth_client.AuthServiceUnavailable()

    monkeypatch.setattr(auth_client, "call", down)
    r = browser.post("/auth/login", json={"email": "x@exemple.com", "password": PASSWORD})
    assert r.status_code == 503 and r.json()["error"]["code"] == "authUnavailable"
    # la déconnexion efface quand même les cookies
    browser.cookies.set("lt_refresh", "abc")
    assert browser.post("/auth/logout").status_code == 200


def _legacy_user(email: str, level: str = "C2") -> uuid.UUID:
    db = SessionLocal()
    user = User(id=uuid.uuid4(), email=email, first_name="Ancien", last_name="Compte", level=level)
    db.add(user)
    db.commit()
    user_id = user.id
    db.close()
    return user_id


def test_existing_account_linked_by_verified_email(browser, auth_service):
    legacy_id = _legacy_user("Ancien@Exemple.com")
    auth_service.add_user("ancien@exemple.com", verified=True)
    browser.post("/auth/login", json={"email": "ancien@exemple.com", "password": PASSWORD})
    me = browser.get("/users/me").json()
    assert me["id"] == str(legacy_id) and me["level"] == "C2"  # historique et niveau retrouvés
    assert me["first_name"] == "Ana"  # copie du profil du service d'auth


def test_existing_account_not_linked_with_unverified_email(browser, auth_service):
    _legacy_user("pirate@exemple.com")
    browser.post("/auth/register", json=signup_payload("pirate@exemple.com"))
    r = browser.get("/users/me")
    assert r.status_code == 403 and "Confirmez" in r.json()["detail"]


def test_mfa_activation_from_settings(browser, auth_service):
    browser.post("/auth/register", json=signup_payload("set@exemple.com"))
    assert browser.post("/users/me/mfa/request", json={"action": "activate"}).status_code == 200
    bad = browser.post("/users/me/mfa/confirm", json={"action": "activate", "code": "000000x"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalidMfaVerification"
    code = auth_service.last_code["set@exemple.com"]
    assert browser.post("/users/me/mfa/confirm", json={"action": "activate", "code": code}).status_code == 200
    assert browser.get("/users/me").json()["mfa_enabled"] is True
