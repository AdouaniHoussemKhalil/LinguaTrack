import uuid

def register(client, password="Abcdef12"):
    email = f"p{uuid.uuid4().hex[:8]}@exemple.com"
    body = client.post("/users/register", json={"email": email, "password": password, "firstName": "Ana", "lastName": "Lima", "level": "A2"}).json()
    return email, {"Authorization": f"Bearer {body['access_token']}"}

def test_update_profile_partial(client):
    _, h = register(client)
    r = client.patch("/users/me", json={"firstName": "  Houssem ", "level": "C1"}, headers=h)
    assert r.status_code == 200, r.text
    me = client.get("/users/me", headers=h).json()
    assert (me["first_name"], me["last_name"], me["level"]) == ("Houssem", "Lima", "C1")

def test_update_profile_validation(client):
    _, h = register(client)
    assert client.patch("/users/me", json={"lastName": "   "}, headers=h).status_code == 422
    assert client.patch("/users/me", json={"level": "Z9"}, headers=h).status_code == 422
    assert client.patch("/users/me", json={"firstName": "X"}).status_code == 401

def test_new_level_is_used_for_analysis(client, monkeypatch):
    from app.services import text_service
    from app.services.llm_common import normalize_analysis
    seen = {}
    def fake(text, mode, target_level):
        seen["level"] = target_level
        return normalize_analysis({"corrected_text": "Ok.", "score": 100, "feedback": "", "grammar_errors": []})
    monkeypatch.setattr(text_service, "generate_analysis", fake)
    _, h = register(client)
    client.patch("/users/me", json={"level": "B2"}, headers=h)
    client.post("/texts/analyze", json={"text": "Ok."}, headers=h)
    assert seen["level"] == "B2"

def test_change_password_flow(client):
    email, h = register(client)
    wrong = client.put("/users/me/password", json={"current_password": "Mauvais1", "new_password": "Nouveau12"}, headers=h)
    assert wrong.status_code == 400 and wrong.json()["detail"] == "Mot de passe actuel incorrect"
    weak = client.put("/users/me/password", json={"current_password": "Abcdef12", "new_password": "faible"}, headers=h)
    assert weak.status_code == 422 and "trop faible" in weak.text
    same = client.put("/users/me/password", json={"current_password": "Abcdef12", "new_password": "Abcdef12"}, headers=h)
    assert same.status_code == 400 and "différent" in same.json()["detail"]
    ok = client.put("/users/me/password", json={"current_password": "Abcdef12", "new_password": "Nouveau12"}, headers=h)
    assert ok.status_code == 204
    assert client.post("/users/login", json={"username": email, "password": "Abcdef12"}).json()["is_success"] is False
    assert client.post("/users/login", json={"username": email, "password": "Nouveau12"}).json()["is_success"] is True
