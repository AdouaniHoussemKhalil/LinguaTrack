"""Corps des routes /auth, relayés tels quels au service d'authentification (noms en camelCase).

La validation fine (mot de passe, longueur des noms…) reste celle du service d'auth : ses erreurs
`validationError` sont renvoyées au front.
"""

from pydantic import BaseModel, EmailStr

from app.models.enums import LanguageLevel


class RegisterRequest(BaseModel):
    firstName: str
    lastName: str
    email: EmailStr
    password: str
    confirmPassword: str
    # Propre à LinguaTrack : gardé dans la base locale, jamais envoyé au service d'auth
    level: LanguageLevel = LanguageLevel.A2


class EmailRequest(BaseModel):
    email: EmailStr


class VerifyEmailRequest(EmailRequest):
    code: str


class LoginRequest(EmailRequest):
    password: str


class MfaLoginRequest(EmailRequest):
    mfaCode: str


class GoogleLoginRequest(BaseModel):
    token: str  # ID token renvoyé par Google Identity Services


class VerifyResetCodeRequest(EmailRequest):
    resetCode: str


class ResetPasswordRequest(EmailRequest):
    resetToken: str
    password: str
    confirmPassword: str


class LogoutRequest(BaseModel):
    allDevices: bool = False
