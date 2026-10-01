"""Relais vers le service d'authentification : le navigateur ne voit ni le secret de l'application
ni les tokens (posés en cookies httpOnly). Statuts et erreurs `{error: {code, message, details}}`
du service sont renvoyés tels quels."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.session import REFRESH_COOKIE, forget_session, remember_session
from app.schemas.auth import (
    EmailRequest,
    GoogleLoginRequest,
    LoginRequest,
    LogoutRequest,
    MfaLoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
    VerifyResetCodeRequest,
)
from app.services import auth_client
from app.services.auth_client import AuthResult, AuthServiceUnavailable
from app.services.user_service import create_registered_user

router = APIRouter(prefix="/auth", tags=["Auth"])


def _relay(result: AuthResult) -> JSONResponse:
    return JSONResponse(status_code=result.status, content=result.data)


def _open_session(request: Request, result: AuthResult) -> JSONResponse:
    """Pose les cookies quand le service renvoie des tokens, sans les transmettre au navigateur.

    Sinon (MFARequired, emailVerificationRequired, erreur) la réponse est relayée telle quelle.
    """
    data = result.data
    if not (result.ok and data.get("access_token")):
        return _relay(result)
    remember_session(request, data)
    rest = {k: v for k, v in data.items() if k not in ("access_token", "refresh_token", "returnedUser")}
    # /loginByMFA renvoie l'utilisateur sous `returnedUser`
    rest["user"] = data.get("user") or data.get("returnedUser")
    return JSONResponse(status_code=result.status, content=rest)


def _body(model: BaseModel) -> dict:
    return model.model_dump(mode="json")


@router.post("/register")
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Crée le compte ; si l'application exige la vérification, renvoie `emailVerificationRequired`."""
    result = auth_client.call("/register", body=payload.model_dump(mode="json", exclude={"level"}))
    if result.ok and result.data.get("user"):
        create_registered_user(db, result.data["user"], payload.level)
    return _open_session(request, result)


@router.post("/verify-email")
def verify_email(payload: VerifyEmailRequest):
    """Confirme l'adresse avec le code reçu ; n'ouvre pas de session (se connecter ensuite)."""
    return _relay(auth_client.call("/verifyEmail", body=_body(payload)))


@router.post("/resend-verification")
def resend_verification(payload: EmailRequest):
    return _relay(auth_client.call("/resendEmailVerification", body=_body(payload)))


@router.post("/login")
def login(payload: LoginRequest, request: Request):
    """Connexion ; si la MFA est active, renvoie `MFARequired` et un code part par e-mail."""
    return _open_session(request, auth_client.call("/login", body=_body(payload)))


@router.post("/login/mfa")
def login_mfa(payload: MfaLoginRequest, request: Request):
    return _open_session(request, auth_client.call("/loginByMFA", body=_body(payload)))


@router.post("/google")
def google(payload: GoogleLoginRequest, request: Request):
    """Connexion (ou inscription) avec l'ID token Google ; peut renvoyer `MFARequired`."""
    return _open_session(request, auth_client.call("/google", body=_body(payload)))


@router.post("/forgot-password")
def forgot_password(payload: EmailRequest):
    return _relay(auth_client.call("/forgotPassword", body=_body(payload)))


@router.post("/verify-reset-code")
def verify_reset_code(payload: VerifyResetCodeRequest):
    """Renvoie un `resetToken` à usage unique."""
    return _relay(auth_client.call("/verifyResetCode", body=_body(payload)))


@router.put("/reset-password")
def reset_password(payload: ResetPasswordRequest):
    """Nouveau mot de passe ; ferme toutes les sessions de l'utilisateur."""
    return _relay(auth_client.call("/resetPassword", method="PUT", body=_body(payload)))


@router.post("/logout")
def logout(request: Request, payload: LogoutRequest | None = None):
    """Révoque la session (ou toutes avec `allDevices`) et efface les cookies, même si le service
    d'auth est injoignable."""
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if refresh_token:
        body = {"refreshToken": refresh_token, "allDevices": bool(payload and payload.allDevices)}
        try:
            auth_client.call("/logout", body=body)
        except AuthServiceUnavailable:
            pass
    forget_session(request)
    return {"isSuccess": True}
