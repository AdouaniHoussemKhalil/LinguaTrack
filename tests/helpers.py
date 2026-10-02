"""Outils communs aux tests (le service d'auth est simulé par la fixture autouse `auth_service`)."""

import uuid

PASSWORD = "Abcdef1!"


def register_user(client, level=None, email=None, password=PASSWORD):
    """Crée un compte et renvoie (en-têtes Bearer, id LinguaTrack en texte).

    Le client de test est partagé : ses cookies sont vidés pour que chaque test choisisse son utilisateur.
    """
    payload = {"email": email or f"u{uuid.uuid4().hex[:8]}@exemple.com", "password": password,
               "confirmPassword": password, "firstName": "Ana", "lastName": "Lima"}
    if level:
        payload["level"] = level
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201, response.text
    headers = {"Authorization": f"Bearer {response.cookies['lt_access']}"}
    client.cookies.clear()
    return headers, client.get("/users/me", headers=headers).json()["id"]
