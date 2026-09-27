import uuid
from datetime import datetime, timedelta, timezone

from app.core.database import SessionLocal
from app.models.error import Error
from app.models.text import TextSubmission


def _user(client):
    body = client.post("/users/register", json={"email": f"h{uuid.uuid4().hex[:8]}@x.com", "password": "Abcdef12", "firstName": "A", "lastName": "B"}).json()
    return uuid.UUID(body["user_id"]), {"Authorization": f"Bearer {body['access_token']}"}


def _texts(user_id, specs):
    """specs : (texte original, âge en heures, nombre d'erreurs)."""
    db, now, ids = SessionLocal(), datetime.now(timezone.utc), []
    for original, hours_ago, n_errors in specs:
        text = TextSubmission(id=uuid.uuid4(), user_id=user_id, original_text=original, corrected_text=original.upper(),
                              mode="correction", score=80, created_at=now - timedelta(hours=hours_ago))
        text.errors = [Error(id=uuid.uuid4(), error_type="accord", original_fragment="a", corrected_fragment="b") for _ in range(n_errors)]
        db.add(text)
        ids.append(str(text.id))
    db.commit(); db.close()
    return ids


def test_list_is_paginated_and_most_recent_first(client):
    uid, h = _user(client)
    _texts(uid, [(f"texte {i}", i, 1) for i in range(12)])
    first = client.get("/texts", params={"page_size": 5}, headers=h).json()
    assert (first["total"], first["pages"], first["page"]) == (12, 3, 1)
    assert [t["original_text"] for t in first["items"]] == [f"texte {i}" for i in range(5)]
    assert all(len(t["errors"]) == 1 for t in first["items"])
    last = client.get("/texts", params={"page_size": 5, "page": 3}, headers=h).json()
    assert [t["original_text"] for t in last["items"]] == ["texte 10", "texte 11"]


def test_search_is_case_insensitive_on_original_and_corrected(client):
    uid, h = _user(client)
    _texts(uid, [("Les enfants jouent", 1, 0), ("Le chat dort", 2, 0), ("Rien à voir", 3, 0)])
    assert [t["original_text"] for t in client.get("/texts", params={"q": "ENFANTS"}, headers=h).json()["items"]] == ["Les enfants jouent"]
    assert client.get("/texts", params={"q": "CHAT DORT"}, headers=h).json()["total"] == 1  # corrigé en majuscules
    assert client.get("/texts", params={"q": "absent"}, headers=h).json() == {"items": [], "total": 0, "page": 1, "page_size": 10, "pages": 1}


def test_period_filter_and_validation(client):
    uid, h = _user(client)
    _texts(uid, [("récent", 1, 0), ("ancien", 24 * 10, 0)])
    assert client.get("/texts", params={"period": "week"}, headers=h).json()["total"] == 1
    assert client.get("/texts", params={"page_size": 500}, headers=h).status_code == 422
    assert client.get("/texts").status_code == 401


def test_users_only_see_and_delete_their_own_texts(client):
    uid, h = _user(client)
    _, other_h = _user(client)
    [text_id] = _texts(uid, [("à moi", 1, 2)])
    assert client.get(f"/texts/{text_id}", headers=h).json()["original_text"] == "à moi"
    assert client.get(f"/texts/{text_id}", headers=other_h).status_code == 404
    assert client.delete(f"/texts/{text_id}", headers=other_h).status_code == 404
    assert client.get("/texts", headers=other_h).json()["total"] == 0


def test_delete_removes_text_and_its_errors(client):
    uid, h = _user(client)
    [text_id] = _texts(uid, [("à supprimer", 1, 3)])
    assert client.delete(f"/texts/{text_id}", headers=h).status_code == 204
    assert client.get(f"/texts/{text_id}", headers=h).status_code == 404
    assert client.delete(f"/texts/{text_id}", headers=h).status_code == 404
    db = SessionLocal()
    assert db.query(Error).filter(Error.text_id == uuid.UUID(text_id)).count() == 0
    db.close()


def test_static_routes_still_reachable(client):
    _, h = _user(client)
    assert client.get("/texts/modes").status_code == 200
    assert client.get("/texts/dashboard", headers=h).status_code == 200
    assert client.get("/texts/progress", headers=h).status_code == 200
    assert client.get("/texts/pas-un-uuid", headers=h).status_code == 422


def test_errors_loaded_without_one_query_per_text(client):
    from sqlalchemy import event
    from app.core.database import engine

    uid, h = _user(client)
    _texts(uid, [(f"texte {i}", i, 2) for i in range(10)])
    statements = []
    listener = lambda *args: statements.append(args[2])  # noqa: E731 (before_cursor_execute : 3e argument = SQL)
    event.listen(engine, "before_cursor_execute", listener)
    try:
        page = client.get("/texts", params={"page_size": 10}, headers=h).json()
    finally:
        event.remove(engine, "before_cursor_execute", listener)
    assert len(page["items"]) == 10 and all(len(t["errors"]) == 2 for t in page["items"])
    text_queries = [s for s in statements if "texts" in s or "errors" in s]
    assert len(text_queries) <= 3, text_queries  # total + page + erreurs de la page (pas 1 requête par texte)
