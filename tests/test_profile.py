from helpers import PASSWORD, register_user


def test_update_profile_partial(client, auth_service):
    h, _ = register_user(client)
    r = client.patch("/users/me", json={"firstName": "  Houssem ", "level": "C1"}, headers=h)
    assert r.status_code == 200, r.text
    me = client.get("/users/me", headers=h).json()
    assert (me["first_name"], me["last_name"], me["level"]) == ("Houssem", "Lima", "C1")
    # le nom vit dans le service d'auth ; la base locale en garde une copie
    assert next(iter(auth_service.users.values()))["firstName"] == "Houssem"


def test_level_only_does_not_call_auth_service(client, auth_service):
    h, _ = register_user(client)
    client.patch("/users/me", json={"level": "B1"}, headers=h)
    assert not any(c.startswith("/updateProfile") for c in auth_service.calls)


def test_update_profile_validation(client):
    h, _ = register_user(client)
    assert client.patch("/users/me", json={"lastName": "   "}, headers=h).status_code == 422
    assert client.patch("/users/me", json={"lastName": "Li"}, headers=h).status_code == 422  # 3 caractères min.
    assert client.patch("/users/me", json={"level": "Z9"}, headers=h).status_code == 422
    assert client.patch("/users/me", json={"firstName": "Xavier"}).status_code == 401


def test_new_level_is_used_for_analysis(client, monkeypatch):
    from app.services import text_service
    from app.services.llm_common import normalize_analysis
    seen = {}
    def fake(text, mode, target_level):
        seen["level"] = target_level
        return normalize_analysis({"corrected_text": "Ok.", "score": 100, "feedback": "", "grammar_errors": []})
    monkeypatch.setattr(text_service, "generate_analysis", fake)
    h, _ = register_user(client)
    client.patch("/users/me", json={"level": "B2"}, headers=h)
    client.post("/texts/analyze", json={"text": "Ok."}, headers=h)
    assert seen["level"] == "B2"


def test_change_password_flow(client, auth_service):
    h, _ = register_user(client)
    wrong = client.put("/users/me/password", json={"current_password": "Mauvais1!", "new_password": "Nouveau12!"}, headers=h)
    assert wrong.status_code == 401 and wrong.json()["error"]["code"] == "invalidCredentials"
    weak = client.put("/users/me/password", json={"current_password": PASSWORD, "new_password": "Nouveau12"}, headers=h)
    assert weak.status_code == 422 and "caractère spécial" in weak.text
    ok = client.put("/users/me/password", json={"current_password": PASSWORD, "new_password": "Nouveau12!"}, headers=h)
    assert ok.status_code == 204
    assert "lt_access" in ok.cookies and "lt_refresh" in ok.cookies  # nouvelle session pour cet appareil
    client.cookies.clear()
    assert next(iter(auth_service.users.values()))["password"] == "Nouveau12!"
