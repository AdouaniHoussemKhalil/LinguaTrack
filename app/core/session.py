"""Session du navigateur : tokens du service d'authentification en cookies httpOnly.

Le front ne voit jamais les tokens (pas de vol par XSS). Les routes notent le changement de session
dans `request.state` ; le middleware de `main.py` l'applique à la réponse, y compris aux réponses
d'erreur : un refresh token échangé doit toujours être remplacé chez le navigateur, sinon sa
réutilisation fermerait toutes les sessions de l'utilisateur.
"""

from typing import Optional

from fastapi import Request, Response

from app.core.config import settings

ACCESS_COOKIE = "lt_access"
REFRESH_COOKIE = "lt_refresh"
REFRESH_MAX_AGE = 7 * 24 * 60 * 60  # durée de vie du refresh token côté service d'auth

_CLEAR = object()


def remember_session(request: Request, tokens: dict) -> None:
    request.state.session_update = {"access": tokens["access_token"], "refresh": tokens["refresh_token"]}


def forget_session(request: Request) -> None:
    request.state.session_update = _CLEAR


def apply_session(request: Request, response: Response) -> None:
    update: Optional[object] = getattr(request.state, "session_update", None)
    if update is None:
        return
    # SameSite=Lax : pas de cookie sur un POST venu d'un autre site (protection CSRF)
    options = {"httponly": True, "samesite": "lax", "secure": settings.COOKIE_SECURE, "path": "/"}
    if update is _CLEAR:
        response.delete_cookie(ACCESS_COOKIE, **options)
        response.delete_cookie(REFRESH_COOKIE, **options)
    else:
        response.set_cookie(ACCESS_COOKIE, update["access"], **options)
        response.set_cookie(REFRESH_COOKIE, update["refresh"], max_age=REFRESH_MAX_AGE, **options)
