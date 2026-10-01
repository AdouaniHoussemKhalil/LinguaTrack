"""Client du service d'authentification auth-web-app-api (routes /consumers/auth).

Seul ce module connaît x-app-id / x-app-secret : ils ne doivent jamais atteindre le navigateur.
"""

import base64
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AuthResult:
    status: int
    data: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


class AuthServiceUnavailable(Exception):
    """Le service d'authentification ne répond pas (arrêté, base injoignable…)."""


def call(path: str, method: str = "POST", body: Optional[dict] = None, access_token: Optional[str] = None) -> AuthResult:
    headers = {"x-app-id": settings.AUTH_APP_ID, "x-app-secret": settings.AUTH_APP_SECRET}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    try:
        response = httpx.request(
            method,
            f"{settings.AUTH_API_URL.rstrip('/')}/consumers/auth{path}",
            headers=headers,
            json=body,
            timeout=settings.AUTH_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        logger.error("Service d'authentification injoignable (%s %s) : %s", method, path, type(exc).__name__)
        raise AuthServiceUnavailable() from exc
    try:
        data: Any = response.json()
    except ValueError:
        data = {}
    if response.status_code >= 500:
        logger.error("Service d'authentification : HTTP %s sur %s %s", response.status_code, method, path)
    return AuthResult(response.status_code, data if isinstance(data, dict) else {})


def user_id_from(access_token: str) -> Optional[str]:
    """Identifiant du consumer lu dans le token, sans vérifier la signature : l'API la vérifie."""
    try:
        payload = access_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))["jwtPayload"]["id"]
    except (IndexError, KeyError, TypeError, ValueError):
        return None


def get_profile(access_token: str) -> AuthResult:
    user_id = user_id_from(access_token)
    if not user_id:
        return AuthResult(401)
    return call(f"/me/{user_id}", method="GET", access_token=access_token)


# Refresh token à usage unique : réutiliser un token déjà échangé ferme toutes les sessions de
# l'utilisateur. Les requêtes simultanées qui portent le même refresh token partagent donc UN seul
# échange, dont le résultat reste en mémoire un moment (valable pour un seul processus uvicorn).
_REFRESH_RESULT_TTL = 60.0


@dataclass
class _Refresh:
    lock: threading.Lock = field(default_factory=threading.Lock)
    result: Optional[AuthResult] = None
    created: float = field(default_factory=time.monotonic)


_refreshes: dict[str, _Refresh] = {}
_refreshes_lock = threading.Lock()


def refresh_once(refresh_token: str) -> AuthResult:
    with _refreshes_lock:
        now = time.monotonic()
        for token in [t for t, entry in _refreshes.items() if now - entry.created > _REFRESH_RESULT_TTL]:
            del _refreshes[token]
        entry = _refreshes.setdefault(refresh_token, _Refresh())
    with entry.lock:
        if entry.result is None:
            entry.result = call("/refresh", body={"refreshToken": refresh_token})
        return entry.result
