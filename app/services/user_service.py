from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate
import uuid


from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate
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