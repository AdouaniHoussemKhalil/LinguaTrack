"""Service d'authentification simulé en mémoire : remplace `auth_client.call` pendant les tests.

Reproduit le contrat utile de auth-web-app-api (/consumers/auth) : tokens au format JWT avec
`jwtPayload.id`, refresh token à usage unique, MFA par code, vérification d'e-mail.
"""

import base64
import json
import secrets
import uuid

from app.services.auth_client import AuthResult


def _error(status: int, code: str, message: str = "") -> AuthResult:
    return AuthResult(status, {"error": {"status": status, "code": code, "message": message or code, "details": None}})


def _jwt(user_id: str) -> str:
    def part(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    return f"{part({'alg': 'none'})}.{part({'jwtPayload': {'id': user_id}, 'n': secrets.token_hex(4)})}.sig"


class FakeAuthService:
    def __init__(self):
        self.users: dict[str, dict] = {}  # par e-mail
        self.access: dict[str, str] = {}  # token -> id
        self.refresh: dict[str, str] = {}  # token -> id (usage unique)
        self.require_email_verification = False
        self.calls: list[str] = []
        self.last_code: dict[str, str] = {}  # e-mail -> dernier code envoyé

    # -- outils ------------------------------------------------------------------------------
    def _by_id(self, user_id: str):
        return next((u for u in self.users.values() if u["id"] == user_id), None)

    def _public(self, user: dict) -> dict:
        return {k: user[k] for k in ("id", "firstName", "lastName", "email")}

    def _session(self, user: dict, status: int = 200, user_key: str = "user") -> AuthResult:
        access, refresh = _jwt(user["id"]), secrets.token_hex(16)
        self.access[access], self.refresh[refresh] = user["id"], user["id"]
        return AuthResult(status, {"access_token": access, "refresh_token": refresh, user_key: self._public(user), "isSuccess": True})

    def _send_code(self, email: str) -> None:
        self.last_code[email] = f"{secrets.randbelow(10**6):06d}"

    def revoke_all(self, user_id: str) -> None:
        for store in (self.access, self.refresh):
            for token in [t for t, uid in store.items() if uid == user_id]:
                del store[token]

    def add_user(self, email: str, password: str = "Abcdef1!", verified: bool = True, **extra) -> dict:
        user = {"id": uuid.uuid4().hex, "email": email, "password": password, "firstName": "Ana", "lastName": "Lima",
                "verified": verified, "mfa": False, "active": True, **extra}
        self.users[email] = user
        return user

    # -- routes ------------------------------------------------------------------------------
    def __call__(self, path, method="POST", body=None, access_token=None) -> AuthResult:
        self.calls.append(path)
        body = body or {}
        route, _, param = path.lstrip("/").partition("/")

        if route == "register":
            if body["email"] in self.users:
                return _error(400, "userAlreadyExists")
            user = self.add_user(body["email"], body["password"], verified=False,
                                 firstName=body["firstName"], lastName=body["lastName"])
            if self.require_email_verification:
                self._send_code(user["email"])
                return AuthResult(201, {"user": self._public(user), "emailVerificationRequired": True, "isSuccess": True})
            return self._session(user, 201)

        if route == "verifyEmail":
            if self.last_code.get(body["email"]) != body["code"]:
                return _error(400, "invalidCode")
            self.users[body["email"]]["verified"] = True
            return AuthResult(200, {"isSuccess": True})

        if route == "login":
            user = self.users.get(body["email"])
            if not user or user["password"] != body["password"]:
                return _error(401, "invalidCredentials")
            if self.require_email_verification and not user["verified"]:
                return _error(403, "emailNotVerified")
            if user["mfa"]:
                self._send_code(user["email"])
                return AuthResult(200, {"MFARequired": True})
            return self._session(user)

        if route == "loginByMFA":
            if self.last_code.get(body["email"]) != body["mfaCode"]:
                return _error(400, "invalidCode")
            return self._session(self.users[body["email"]], user_key="returnedUser")

        if route == "refresh":
            user_id = self.refresh.pop(body["refreshToken"], None)
            if user_id is None:
                return _error(401, "invalidRefreshToken")
            user = self._by_id(user_id)
            result = self._session(user)
            return AuthResult(200, {k: result.data[k] for k in ("access_token", "refresh_token")} | {"isSuccess": True})

        if route == "logout":
            user_id = self.refresh.pop(body["refreshToken"], None)
            if user_id and body.get("allDevices"):
                self.revoke_all(user_id)
            return AuthResult(200, {"isSuccess": True})

        # Routes protégées
        user_id = self.access.get(access_token or "")
        if user_id is None:
            return _error(403, "invalidToken")
        user = self._by_id(user_id)

        if route == "me":
            if param != user_id:
                return _error(403, "forbidden")
            return AuthResult(200, {"id": user["id"], "firstName": user["firstName"], "lastName": user["lastName"],
                                    "email": user["email"], "isActive": user["active"], "isMFAEnabled": user["mfa"],
                                    "isEmailVerified": user["verified"], "creationDate": "2026-01-01T00:00:00Z"})

        if route == "updateProfile":
            for field, key in (("newFirstName", "firstName"), ("newLastName", "lastName")):
                if body.get(field):
                    user[key] = body[field]
            return AuthResult(200, {"user": self._public(user), "isSuccess": True})

        if route == "updatePassword":
            if user["password"] != body["currentPassword"]:
                return _error(400, "currentPasswordNotCorrect")
            user["password"] = body["password"]
            self.revoke_all(user_id)
            result = self._session(user, 201)
            return AuthResult(201, {k: result.data[k] for k in ("access_token", "refresh_token")} | {"isSuccess": True})

        if route == "requestMFA":
            self._send_code(user["email"])
            return AuthResult(200, {"isSuccess": True})

        if route in ("activateMFA", "deactivateMFA"):
            code = body.get("activationId") or body.get("deactivationId")
            if self.last_code.get(user["email"]) != code:
                return _error(400, "invalidMfaVerification")
            user["mfa"] = route == "activateMFA"
            return AuthResult(200, {"isSuccess": True})

        raise AssertionError(f"Route du service d'auth non simulée : {method} {path}")
