"""Comptes LinguaTrack : copie locale des comptes du service d'authentification.

Le service d'auth gère identité, mot de passe, MFA et sessions ; la table `users` garde ce qui est
propre à LinguaTrack (niveau, lien avec les textes) et une copie du nom et de l'e-mail.
"""

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import LanguageLevel
from app.models.user import User
from app.schemas.user import UserUpdate


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(func.lower(User.email) == email.lower()).first()


def get_user_by_auth_id(db: Session, auth_user_id: str):
    return db.query(User).filter(User.auth_user_id == auth_user_id).first()


def create_registered_user(db: Session, auth_user: dict, level: LanguageLevel) -> None:
    """Crée le compte local dès l'inscription, pour mémoriser le niveau choisi.

    Si l'e-mail appartient déjà à un compte LinguaTrack, rien n'est fait ici : la liaison se fait à la
    première session, une fois l'adresse vérifiée (voir `sync_user`).
    """
    if get_user_by_auth_id(db, auth_user["id"]) or get_user_by_email(db, auth_user["email"]):
        return
    db.add(User(
        auth_user_id=auth_user["id"],
        email=auth_user["email"],
        first_name=auth_user["firstName"],
        last_name=auth_user["lastName"],
        level=level.value,
    ))
    try:
        db.commit()
    except IntegrityError:  # requête concurrente : le compte existe déjà
        db.rollback()


def sync_user(db: Session, profile: dict) -> User:
    """Compte local de l'utilisateur authentifié (profil renvoyé par GET /me du service d'auth)."""
    user = get_user_by_auth_id(db, profile["id"])
    if user is None:
        user = get_user_by_email(db, profile["email"])
        if user is not None:
            # Compte antérieur au service d'auth (ou compte d'auth recréé) : relié par l'e-mail,
            # seulement si l'adresse est prouvée, sinon n'importe qui pourrait reprendre l'historique.
            if not profile.get("isEmailVerified"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Confirmez votre adresse e-mail pour retrouver votre compte LinguaTrack",
                )
            user.auth_user_id = profile["id"]
        else:
            user = User(auth_user_id=profile["id"], email=profile["email"], level=LanguageLevel.A2.value)
            db.add(user)

    changes = {"email": profile["email"], "first_name": profile["firstName"], "last_name": profile["lastName"]}
    for attribute, value in changes.items():
        if getattr(user, attribute) != value:
            setattr(user, attribute, value)

    if db.new or db.dirty:
        try:
            db.commit()
        except IntegrityError:  # première requête simultanée : l'autre a créé le compte
            db.rollback()
            user = get_user_by_auth_id(db, profile["id"])
            if user is None:
                raise
        db.refresh(user)
    return user


def update_user(db: Session, user: User, data: UserUpdate) -> User:
    """Applique les champs fournis (prénom, nom, niveau) à la copie locale du profil."""
    if data.firstName is not None:
        user.first_name = data.firstName
    if data.lastName is not None:
        user.last_name = data.lastName
    if data.level is not None:
        user.level = data.level.value
    db.commit()
    db.refresh(user)
    return user
