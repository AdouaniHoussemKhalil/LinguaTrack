from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
from uuid import UUID
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.enums import CorrectionMode
from app.models.text import TextSubmission
from app.schemas.text import (
    TextAnalyzeRequest,
    TextAnalyzeRequestManyModes,
    TextResponse,
    DashboardStatsResponse,
    DashboardPeriod,
    GetHistoryRequest
)
from datetime import datetime, timedelta, timezone
from app.services.text_service import analyze_text, get_user_text, get_user_texts, get_user_dashboard_stats, _build_period_filters_v2

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
    req: GetHistoryRequest =  Depends(),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    now = datetime.now(timezone.utc)
    current_filters, previous_filters, period_label = _build_period_filters_v2(
        current_user.id,
        req.period,
        now
    )
    return db.query(TextSubmission).filter(*current_filters).order_by(TextSubmission.created_at.desc()).all()

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


@router.get("/dashboard", response_model=DashboardStatsResponse)
def get_dashboard(
    period: DashboardPeriod = DashboardPeriod.all,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    return get_user_dashboard_stats(db, current_user.id, period.value)