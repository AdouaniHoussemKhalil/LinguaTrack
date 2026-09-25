from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.user import LoginRequest, UserCreate, UserResponse
from app.services.user_service import authenticate_user, create_user


router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/register")
def create_new_user(user: UserCreate, db: Session = Depends(get_db)):
    (created_user, is_success, error) = create_user(db, user)
    if not is_success:
        return {"is_success": False, "error": error}
    
    access_token = create_access_token(data={"sub": str(created_user.id)})
    return {"user_id": created_user.id,"access_token": access_token, "is_success": True, "error": None}

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Profil de l'utilisateur connecté (remplace GET /users/{user_id}, accessible sans authentification)."""
    return current_user

@router.post("/login")
def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    (user, is_success, error) = authenticate_user(db, request.username, request.password)
    if not is_success:
        return {"is_success": False, "error": error}
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"user_id":user.id ,"access_token": access_token, "token_type": "bearer", "is_success": True, "error": None}



@router.post("/token")
def login_oauth(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    (user, is_success, error) = authenticate_user(db, form_data.username, form_data.password)
    if not is_success:
        return {"is_success": False, "error": error}
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer", "is_success": True, "error": None}
