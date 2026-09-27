from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
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
    ProgressResponse,
    TextPage,
    DashboardPeriod,
    GetHistoryRequest
)
from datetime import datetime, timedelta, timezone
from app.services.llm_service import LLMError
from app.services.progress_service import get_user_progress
from app.services.quota_service import check_analysis_quota
from app.services.text_service import delete_user_text, list_user_texts
from app.services.text_service import analyze_text, get_user_text, get_user_texts, get_user_dashboard_stats, _build_period_filters_v2

router = APIRouter(prefix="/texts", tags=["Texts"])


@router.post("/analyze", response_model=TextResponse)
def analyze(
    data: TextAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # Avant l'appel au LLM : un utilisateur au-delà de son quota ne coûte rien
    exceeded = check_analysis_quota(db, current_user.id)
    if exceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=exceeded.message,
            headers={"Retry-After": str(exceeded.retry_after_seconds)},
        )
    try:
        return analyze_text(db, current_user.id, data, default_level=current_user.level)
    except LLMError as exc:
        # 502 : l'échec vient du service d'analyse externe, pas de la requête
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/modes", response_model=List[str])
def get_modes():
    return [mode.value for mode in CorrectionMode]

@router.get("/history", response_model=List[TextResponse], deprecated=True)
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

@router.get("/history/{user_id}/{text_id}", response_model=TextResponse, deprecated=True)
def get_text_entry(user_id: UUID, text_id: UUID, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    # UUID typés : un identifiant mal formé donne 422 au lieu d'un 500
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Accès refusé")
    entry = get_user_text(db, user_id, text_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Texte introuvable")
    return entry


@router.get("/dashboard", response_model=DashboardStatsResponse)
def get_dashboard(
    period: DashboardPeriod = DashboardPeriod.all,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    return get_user_dashboard_stats(db, current_user.id, period.value)


@router.get("/progress", response_model=ProgressResponse)
def get_progress(
    period: DashboardPeriod = DashboardPeriod.all,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Évolution du score : nombre de textes, score moyen et erreurs par intervalle de temps."""
    return get_user_progress(db, current_user.id, period.value)


# ------------------------------------------------------------------
# Textes de l'utilisateur connecté. Routes avec {text_id} déclarées en
# dernier : sinon « /texts/modes » serait lu comme un identifiant.
# ------------------------------------------------------------------

@router.get("", response_model=TextPage)
def list_texts(
    period: DashboardPeriod = DashboardPeriod.all,
    q: Optional[str] = Query(default=None, max_length=200, description="Recherche dans le texte original ou corrigé"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Historique paginé, du plus récent au plus ancien (remplace GET /texts/history)."""
    return list_user_texts(db, current_user.id, period.value, q, page, page_size)


@router.get("/{text_id}", response_model=TextResponse)
def get_text(text_id: UUID, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Détail d'un texte de l'utilisateur connecté (remplace GET /texts/history/{user_id}/{text_id})."""
    entry = get_user_text(db, current_user.id, text_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Texte introuvable")
    return entry


@router.delete("/{text_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_text(text_id: UUID, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Supprime un texte de l'utilisateur connecté et ses erreurs."""
    if not delete_user_text(db, current_user.id, text_id):
        raise HTTPException(status_code=404, detail="Texte introuvable")
