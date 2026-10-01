from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.session import remember_session
from app.models.user import User
from app.schemas.user import MfaConfirm, MfaRequest, PasswordChange, UserResponse, UserUpdate
from app.services import auth_client
from app.services.user_service import update_user

# Inscription, connexion et session : voir /auth (auth_router)
router = APIRouter(prefix="/users", tags=["Users"])


def _response(user: User, request: Request) -> UserResponse:
    response = UserResponse.model_validate(user)
    response.mfa_enabled = bool(request.state.auth_profile.get("isMFAEnabled"))
    return response


@router.get("/me", response_model=UserResponse)
def get_me(request: Request, current_user: User = Depends(get_current_user)):
    """Profil de l'utilisateur connecté."""
    return _response(current_user, request)


@router.patch("/me", response_model=UserResponse)
def update_me(
    data: UserUpdate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Modifie le prénom, le nom (dans le service d'auth) ou le niveau de l'utilisateur connecté."""
    if data.firstName is not None or data.lastName is not None:
        auth_id = current_user.auth_user_id
        result = auth_client.call(
            f"/updateProfile/{auth_id}",
            method="PUT",
            body={"userId": auth_id, "newFirstName": data.firstName, "newLastName": data.lastName},
            access_token=request.state.access_token,
        )
        if not result.ok:
            return JSONResponse(status_code=result.status, content=result.data)
    return _response(update_user(db, current_user, data), request)


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def update_my_password(data: PasswordChange, request: Request, current_user: User = Depends(get_current_user)):
    """Change le mot de passe (mot de passe actuel exigé) ; les autres sessions sont fermées."""
    auth_id = current_user.auth_user_id
    result = auth_client.call(
        f"/updatePassword/{auth_id}",
        method="PUT",
        body={
            "userId": auth_id,
            "currentPassword": data.current_password,
            "password": data.new_password,
            "confirmPassword": data.new_password,
        },
        access_token=request.state.access_token,
    )
    if not result.ok:
        return JSONResponse(status_code=result.status, content=result.data)
    remember_session(request, result.data)  # nouvelle paire de tokens pour cet appareil


@router.post("/me/mfa/request")
def request_mfa(data: MfaRequest, request: Request, current_user: User = Depends(get_current_user)):
    """Envoie par e-mail le code qui confirme l'activation ou la désactivation de la MFA."""
    result = auth_client.call(
        "/requestMFA",
        body={"email": request.state.auth_profile["email"], "requestType": data.action},
        access_token=request.state.access_token,
    )
    return JSONResponse(status_code=result.status, content=result.data)


@router.post("/me/mfa/confirm")
def confirm_mfa(data: MfaConfirm, request: Request, current_user: User = Depends(get_current_user)):
    """Active ou désactive la MFA avec le code reçu par e-mail."""
    path, field = ("/activateMFA", "activationId") if data.action == "activate" else ("/deactivateMFA", "deactivationId")
    result = auth_client.call(
        path,
        body={"userId": current_user.auth_user_id, field: data.code.strip()},
        access_token=request.state.access_token,
    )
    return JSONResponse(status_code=result.status, content=result.data)
