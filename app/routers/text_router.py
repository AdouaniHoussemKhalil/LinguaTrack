from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
from uuid import UUID
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.enums import CorrectionMode
from app.models.text import TextSubmission
from app.schemas.text import TextAnalyzeRequest, TextAnalyzeRequestManyModes, TextResponse
from app.services.text_service import analyze_text, get_user_text, get_user_texts

router = APIRouter(prefix="/texts", tags=["Texts"])


@router.post("/analyze", response_model=TextResponse)
def analyze(
    data: TextAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    return analyze_text(db, current_user.id, data)


@router.get("/modes", response_model=List[str])
def get_modes():
    return [mode.value for mode in CorrectionMode]

@router.get("/history", response_model=List[TextResponse])
def get_history(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    return db.query(TextSubmission).filter(TextSubmission.user_id == current_user.id).all()

@router.get("/history/{user_id}/{text_id}", response_model=TextResponse)
def get_text_entry(user_id: str, text_id: str, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    user_id_uuid = UUID(user_id)
    text_id_uuid = UUID(text_id)
    if(current_user.id != user_id_uuid):
        raise HTTPException(status_code=403, detail="Forbidden")
    entry = get_user_text(db, user_id_uuid, text_id_uuid)
    if not entry:
        raise HTTPException(status_code=404, detail="Text entry not found")
    return entry