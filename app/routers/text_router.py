from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
from uuid import UUID
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.text import TextSubmission
from app.schemas.text import TextAnalyzeRequest, TextAnalyzeRequestManyModes, TextResponse
from app.services.text_service import analyze_text

router = APIRouter(prefix="/texts", tags=["Texts"])


@router.post("/analyze", response_model=TextResponse)
def analyze(
    data: TextAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    return analyze_text(db, current_user.id, data)

@router.post("/analyze-many", response_model=List[TextResponse])
def analyze_many(
    data: TextAnalyzeRequestManyModes,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    results = []
    for item in data.modes:

        result = analyze_text(db, current_user.id, TextAnalyzeRequest(
            text=item.text,
            mode=item.mode,
            target_level=item.target_level
        ))
        results.append(result)
    return results

@router.get("/history/{user_id}", response_model=List[TextResponse])
def get_history(user_id: UUID, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    if(current_user.id != user_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    return db.query(TextSubmission).filter(TextSubmission.user_id == user_id).all()

@router.get("/history/{user_id}/{text_id}", response_model=TextResponse)
def get_text_entry(user_id: UUID, text_id: UUID, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    if(current_user.id != user_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    entry = db.query(TextSubmission).filter(TextSubmission.user_id == user_id, TextSubmission.id == text_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Text entry not found")
    return entry