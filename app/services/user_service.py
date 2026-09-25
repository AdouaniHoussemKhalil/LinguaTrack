from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate
import uuid


from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import PasswordChange, UserCreate, UserUpdate
from app.core.security import create_access_token, hash_password, verify_password
from uuid import UUID



def create_user(db: Session, user_data: UserCreate):

    existing_user = get_user_by_email(db, user_data.email)
    if existing_user:
        return (None, False, "Un utilisateur avec cet email existe déjà")

    hashed_pwd = hash_password(user_data.password)

    user = User(
        id=uuid.uuid4(),
        email=user_data.email,
        password=hashed_pwd,
        first_name=user_data.firstName,
        last_name=user_data.lastName,
        level=user_data.level.value
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    created_user = User(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        level=user.level,
        created_at=user.created_at
    )

    return (created_user, True, None)


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: UUID):
    return db.query(User).filter(User.id == user_id).first()

def authenticate_user(db, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()

    if not user:
        return (None, False, "Nom d'utilisateur ou mot de passe incorrect")

    if not verify_password(password, user.password):
        return (None, False, "Nom d'utilisateur ou mot de passe incorrect")

    return (user, True, None)


def login_user(db, email: str, password: str):
    user = authenticate_user(db, email, password)

    if not user:
        return None

    token = create_access_token({"sub": str(user.id)})

    return token


def update_user(db: Session, user: User, data: UserUpdate) -> User:
    """Applique les champs fournis (prénom, nom, niveau) au profil."""
    if data.firstName is not None:
        user.first_name = data.firstName
    if data.lastName is not None:
        user.last_name = data.lastName
    if data.level is not None:
        user.level = data.level.value
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, data: PasswordChange):
    """Change le mot de passe ; renvoie un message d'erreur, ou None en cas de succès."""
    if not verify_password(data.current_password, user.password):
        return "Mot de passe actuel incorrect"
    if verify_password(data.new_password, user.password):
        return "Le nouveau mot de passe doit être différent de l'actuel"
    user.password = hash_password(data.new_password)
    db.commit()
    return None
