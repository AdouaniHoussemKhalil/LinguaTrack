from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.session import ACCESS_COOKIE, REFRESH_COOKIE, forget_session, remember_session
from app.models.user import User
from app.services import auth_client
from app.services.user_service import sync_user

# Le front s'authentifie par cookies ; l'en-tête Bearer (access token du service d'auth) reste
# accepté pour les autres clients et pour les tests, sans renouvellement automatique.
bearer_scheme = HTTPBearer(auto_error=False, description="Access token du service d'authentification")


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Utilisateur de la session, vérifié auprès du service d'auth ; renouvelle la session si besoin."""
    if credentials is not None:
        access_token = credentials.credentials
        profile = auth_client.get_profile(access_token)
        if not profile.ok:
            raise _unauthorized("Token invalide ou expiré")
    else:
        access_token = request.cookies.get(ACCESS_COOKIE)
        profile = auth_client.get_profile(access_token) if access_token else auth_client.AuthResult(401)
        if not profile.ok:
            refresh_token = request.cookies.get(REFRESH_COOKIE)
            refreshed = auth_client.refresh_once(refresh_token) if refresh_token else auth_client.AuthResult(401)
            if not refreshed.ok:
                if access_token or refresh_token:
                    forget_session(request)
                raise _unauthorized("Session expirée, reconnectez-vous")
            remember_session(request, refreshed.data)
            access_token = refreshed.data["access_token"]
            profile = auth_client.get_profile(access_token)
            if not profile.ok:
                forget_session(request)
                raise _unauthorized("Session invalide, reconnectez-vous")

    if profile.data.get("isActive") is False:
        forget_session(request)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ce compte est bloqué")

    # Pour relayer les routes protégées du service d'auth (profil, mot de passe, MFA)
    request.state.access_token = access_token
    request.state.auth_profile = profile.data
    return sync_user(db, profile.data)
