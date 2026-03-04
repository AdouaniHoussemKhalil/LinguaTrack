from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate
import uuid


from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import create_access_token, hash_password, verify_password
import uuid


def create_user(db: Session, user_data: UserCreate):
    hashed_pwd = hash_password(user_data.password)

    user = User(
        id=uuid.uuid4(),
        email=user_data.email,
        password=hashed_pwd,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        level="A2"
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id):
    return db.query(User).filter(User.id == user_id).first()

def authenticate_user(db, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()

    if not user:
        return None

    if not verify_password(password, user.password):
        return None

    return user


def login_user(db, email: str, password: str):
    user = authenticate_user(db, email, password)

    if not user:
        return None

    token = create_access_token({"sub": str(user.id)})

    return token