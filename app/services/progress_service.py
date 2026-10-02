"""Évolution du score dans le temps (courbe de progression du dashboard).

Le regroupement par intervalle est fait en Python plutôt qu'en SQL : les fonctions
de date diffèrent entre SQLite et PostgreSQL, et les volumes par utilisateur sont faibles.
Tous les intervalles sont calculés en UTC.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.error import Error
from app.models.text import TextSubmission
from app.services.text_service import _build_period_filters_v2

# Granularité imposée par la période ; « all » est choisie selon l'ancienneté des textes
GRANULARITY_BY_PERIOD = {"day": "hour", "week": "day", "month": "day", "year": "month"}
PERIOD_LENGTH = {"day": timedelta(days=1), "week": timedelta(days=7), "month": timedelta(days=30), "year": timedelta(days=365)}


def _as_utc(value: datetime) -> datetime:
    # SQLite renvoie des dates sans fuseau : elles sont enregistrées en UTC
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def bucket_start(value: datetime, granularity: str) -> datetime:
    value = _as_utc(value)
    if granularity == "hour":
        return value.replace(minute=0, second=0, microsecond=0)
    day = value.replace(hour=0, minute=0, second=0, microsecond=0)
    if granularity == "day":
        return day
    if granularity == "week":
        return day - timedelta(days=day.weekday())  # semaine commençant le lundi
    return day.replace(day=1)  # month


def next_bucket(start: datetime, granularity: str) -> datetime:
    if granularity == "hour":
        return start + timedelta(hours=1)
    if granularity == "day":
        return start + timedelta(days=1)
    if granularity == "week":
        return start + timedelta(days=7)
    return (start.replace(day=28) + timedelta(days=4)).replace(day=1)  # month


def auto_granularity(first: datetime, now: datetime) -> str:
    span = now - _as_utc(first)
    if span <= timedelta(days=31):
        return "day"
    if span <= timedelta(days=366):
        return "week"
    return "month"


def get_user_progress(db: Session, user_id: UUID, period: str = "all", now: Optional[datetime] = None) -> dict:
    now = _as_utc(now or datetime.now(timezone.utc))
    filters, _previous, _label = _build_period_filters_v2(user_id, period, now)

    rows = (
        db.query(TextSubmission.id, TextSubmission.created_at, TextSubmission.score)
        .filter(*filters)
        .order_by(TextSubmission.created_at)
        .all()
    )
    error_counts: Dict[UUID, int] = dict(
        db.query(Error.text_id, func.count(Error.id))
        .join(TextSubmission, Error.text_id == TextSubmission.id)
        .filter(*filters)
        .group_by(Error.text_id)
        .all()
    )

    if period in GRANULARITY_BY_PERIOD:
        granularity = GRANULARITY_BY_PERIOD[period]
        first_bucket = bucket_start(now - PERIOD_LENGTH[period], granularity)
    elif rows:
        granularity = auto_granularity(rows[0].created_at, now)
        first_bucket = bucket_start(rows[0].created_at, granularity)
    else:
        return {"period": period, "granularity": "day", "points": []}

    scores: Dict[datetime, List[float]] = defaultdict(list)
    texts: Dict[datetime, int] = defaultdict(int)
    errors: Dict[datetime, int] = defaultdict(int)
    for row in rows:
        start = bucket_start(row.created_at, granularity)
        texts[start] += 1
        errors[start] += error_counts.get(row.id, 0)
        if row.score is not None:
            scores[start].append(row.score)

    points = []
    start, last_bucket = first_bucket, bucket_start(now, granularity)
    while start <= last_bucket:
        bucket_scores = scores.get(start)
        points.append({
            "start": start,
            "texts": texts.get(start, 0),
            "average_score": round(sum(bucket_scores) / len(bucket_scores), 1) if bucket_scores else None,
            "errors": errors.get(start, 0),
        })
        start = next_bucket(start, granularity)

    return {"period": period, "granularity": granularity, "points": points}
