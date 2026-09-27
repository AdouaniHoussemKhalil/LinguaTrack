"""Limite du nombre d'analyses par utilisateur (chaque analyse appelle un LLM)."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.text import TextSubmission


@dataclass
class QuotaExceeded:
    message: str
    retry_after_seconds: int


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _format_wait(seconds: int) -> str:
    minutes = max(1, math.ceil(seconds / 60))
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes > 1 else ''}"
    hours = math.ceil(minutes / 60)
    return f"{hours} heure{'s' if hours > 1 else ''}"


def check_analysis_quota(db: Session, user_id: UUID, now: Optional[datetime] = None) -> Optional[QuotaExceeded]:
    """None si l'utilisateur peut analyser un texte, sinon le motif et le délai d'attente.

    Seules les analyses enregistrées comptent : une analyse en échec (rien d'enregistré)
    n'entame pas le quota.
    """
    now = now or datetime.now(timezone.utc)
    windows = (
        (settings.ANALYSES_PER_HOUR, timedelta(hours=1), "par heure"),
        (settings.ANALYSES_PER_DAY, timedelta(days=1), "par jour"),
    )
    for limit, window, label in windows:
        if limit <= 0:  # 0 = sans limite
            continue
        since = now - window
        used = (
            db.query(func.count(TextSubmission.id))
            .filter(TextSubmission.user_id == user_id, TextSubmission.created_at >= since)
            .scalar()
            or 0
        )
        if used >= limit:
            # La plus ancienne analyse de la fenêtre qui doit en sortir pour libérer une place
            oldest = (
                db.query(TextSubmission.created_at)
                .filter(TextSubmission.user_id == user_id, TextSubmission.created_at >= since)
                .order_by(TextSubmission.created_at)
                .offset(used - limit)
                .limit(1)
                .scalar()
            )
            retry_after = max(1, int((_as_utc(oldest) + window - now).total_seconds())) if oldest else int(window.total_seconds())
            return QuotaExceeded(
                message=f"Limite de {limit} analyses {label} atteinte. Réessayez dans {_format_wait(retry_after)}.",
                retry_after_seconds=retry_after,
            )
    return None
