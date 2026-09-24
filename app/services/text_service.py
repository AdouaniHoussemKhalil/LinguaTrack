import time
import uuid
from uuid import UUID
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.text import TextSubmission
from app.models.error import Error
from app.schemas.text import TextAnalyzeRequest
from app.services.llm_service import generate_analysis



def get_user_texts(db: Session, user_id: UUID):
    return db.query(TextSubmission).filter(TextSubmission.user_id == user_id).all()

def get_user_text(db: Session, user_id: UUID, text_id: UUID):
    return db.query(TextSubmission).filter(TextSubmission.user_id == user_id, TextSubmission.id == text_id).first()


def _compute_change(current_value: Optional[float], previous_value: Optional[float]) -> Optional[float]:
    if current_value is None or previous_value is None:
        return None
    if previous_value == 0:
        return None
    return round((current_value - previous_value) / previous_value * 100, 2)


def _normalize_note(metric_name: str, change: Optional[float], period_label: str, previous_value: Optional[float]) -> str:
    if change is None:
        if previous_value == 0:
            return f"this {period_label} no previous data"
        return f"this {period_label} change unavailable"

    prefix = "+" if change >= 0 else ""
    return f"this {period_label} {prefix}{change:.1f}%"


def _build_period_filters(user_id: UUID, period: str, now: datetime):
    current_filters = [TextSubmission.user_id == user_id]
    previous_filters = None
    period_label = "period"

    if period == "last_week":
        current_filters.append(TextSubmission.created_at >= now - timedelta(days=7))
        previous_filters = [TextSubmission.user_id == user_id,
                            TextSubmission.created_at >= now - timedelta(days=14),
                            TextSubmission.created_at < now - timedelta(days=7)]
        period_label = "week"
    elif period == "last_month":
        current_filters.append(TextSubmission.created_at >= now - timedelta(days=30))
        previous_filters = [TextSubmission.user_id == user_id,
                            TextSubmission.created_at >= now - timedelta(days=60),
                            TextSubmission.created_at < now - timedelta(days=30)]
        period_label = "month"

    return current_filters, previous_filters, period_label


def _build_period_filters_v2(user_id: UUID, period: str, now: datetime):
    base_filter = [TextSubmission.user_id == user_id]

    current_filters = base_filter.copy()
    previous_filters = None
    period_label = period

    # helper
    def add_days(filters, start_days, end_days=None):
        filters.append(TextSubmission.created_at >= now - timedelta(days=start_days))
        if end_days is not None:
            filters.append(TextSubmission.created_at < now - timedelta(days=end_days))

    if period == "all":
        # pas de filtre date
        period_label = "all"

    elif period == "day":
        add_days(current_filters, 1)
        previous_filters = [
            TextSubmission.user_id == user_id,
            TextSubmission.created_at >= now - timedelta(days=2),
            TextSubmission.created_at < now - timedelta(days=1),
        ]
        period_label = "day"

    elif period == "week":
        add_days(current_filters, 7)
        previous_filters = [
            TextSubmission.user_id == user_id,
            TextSubmission.created_at >= now - timedelta(days=14),
            TextSubmission.created_at < now - timedelta(days=7),
        ]
        period_label = "week"

    elif period == "month":
        add_days(current_filters, 30)
        previous_filters = [
            TextSubmission.user_id == user_id,
            TextSubmission.created_at >= now - timedelta(days=60),
            TextSubmission.created_at < now - timedelta(days=30),
        ]
        period_label = "month"

    elif period == "year":
        add_days(current_filters, 365)
        previous_filters = [
            TextSubmission.user_id == user_id,
            TextSubmission.created_at >= now - timedelta(days=730),
            TextSubmission.created_at < now - timedelta(days=365),
        ]
        period_label = "year"

    else:
        # fallback sécurité
        period_label = "all"

    return current_filters, previous_filters, period_label


def get_user_dashboard_stats(db: Session, user_id: UUID, period: str = "all"):
    now = datetime.now(timezone.utc)
    current_filters, previous_filters, period_label = _build_period_filters(
        user_id,
        period,
        now
    )

    total_texts = (
        db.query(func.count(TextSubmission.id))
        .filter(*current_filters)
        .scalar()
        or 0
    )

    average_score = (
        db.query(func.avg(TextSubmission.score))
        .filter(*current_filters)
        .scalar()
    )

    average_processing_time = (
        db.query(func.avg(TextSubmission.processing_time))
        .filter(*current_filters)
        .scalar()
    )

    total_errors = (
        db.query(func.count(Error.id))
        .join(TextSubmission, Error.text_id == TextSubmission.id)
        .filter(*current_filters)
        .scalar()
        or 0
    )

    average_errors_per_text = (
        round(total_errors / total_texts, 2)
        if total_texts > 0
        else 0
    )

    mode_counts = (
        db.query(
            TextSubmission.mode,
            func.count(TextSubmission.id)
        )
        .filter(*current_filters)
        .group_by(TextSubmission.mode)
        .all()
    )

    mode_counts = {
        mode: count
        for mode, count in mode_counts
    }

    mode_percentages = {
        mode: round(count * 100 / total_texts, 2)
        for mode, count in mode_counts.items()
    } if total_texts > 0 else {}

    error_type_counts = (
        db.query(
            Error.error_type,
            func.count(Error.id)
        )
        .join(TextSubmission, Error.text_id == TextSubmission.id)
        .filter(*current_filters)
        .group_by(Error.error_type)
        .all()
    )

    error_type_counts = {
        error_type: count
        for error_type, count in error_type_counts
    }

    error_type_percentages = {
        error_type: round(count * 100 / total_errors, 2)
        for error_type, count in error_type_counts.items()
    } if total_errors > 0 else {}

    recent_texts = (
        db.query(TextSubmission)
        .filter(*current_filters)
        .order_by(TextSubmission.created_at.desc())
        .limit(5)
        .all()
    )

    average_score_change = None
    total_texts_change = None
    total_errors_change = None

    change_notes = {}

    if previous_filters is not None:

        prev_total_texts = (
            db.query(func.count(TextSubmission.id))
            .filter(*previous_filters)
            .scalar()
            or 0
        )

        prev_average_score = (
            db.query(func.avg(TextSubmission.score))
            .filter(*previous_filters)
            .scalar()
        )

        prev_total_errors = (
            db.query(func.count(Error.id))
            .join(TextSubmission, Error.text_id == TextSubmission.id)
            .filter(*previous_filters)
            .scalar()
            or 0
        )

        average_score_change = _compute_change(
            average_score,
            prev_average_score
        )

        total_texts_change = _compute_change(
            float(total_texts),
            float(prev_total_texts)
        )

        total_errors_change = _compute_change(
            float(total_errors),
            float(prev_total_errors)
        )

        change_notes = {
            "average_score": _normalize_note(
                "average score",
                average_score_change,
                period_label,
                prev_average_score
            ),
            "total_texts": _normalize_note(
                "total texts",
                total_texts_change,
                period_label,
                float(prev_total_texts)
            ),
            "total_errors": _normalize_note(
                "total errors",
                total_errors_change,
                period_label,
                float(prev_total_errors)
            ),
        }

    return {
        "total_texts": total_texts,
        "average_score": (
            float(average_score)
            if average_score is not None
            else None
        ),
        "total_errors": total_errors,
        "average_processing_time": (
            float(average_processing_time)
            if average_processing_time is not None
            else None
        ),

        "average_errors_per_text": average_errors_per_text,

        "mode_counts": mode_counts,
        "mode_percentages": mode_percentages,

        "error_type_counts": error_type_counts,
        "error_type_percentages": error_type_percentages,

        "recent_texts": recent_texts,

        "average_score_change": average_score_change,
        "total_texts_change": total_texts_change,
        "total_errors_change": total_errors_change,

        "change_notes": change_notes,
    }


def analyze_text(db: Session, user_id, data: TextAnalyzeRequest, base_request_id=None):
    start = time.time()

    llm_result = generate_analysis(
        text=data.text,
        mode=data.mode,
        target_level=data.target_level
    )

    print("=== LLM RESULT ===")
    print(llm_result)

    text_entry = TextSubmission(
        id=uuid.uuid4(),
        user_id=user_id,
        original_text=data.text,
        corrected_text=llm_result["corrected_text"],
        mode=data.mode,
        target_level=data.target_level,
        score=llm_result["score"],
        processing_time=time.time() - start,
    )

    db.add(text_entry)
    db.commit()
    db.refresh(text_entry)

    errors_to_add = []
    for e in llm_result.get("grammar_errors", []):
        error_entry = Error(
            id=uuid.uuid4(),
            text_id=text_entry.id,
            error_type=e.get("error_type", "grammar"),  # par défaut grammar
            severity=e.get("severity"),  # peut être None
            original_fragment=e.get("original", ""),
            corrected_fragment=e.get("corrected", ""),
            explanation=e.get("explanation", ""),
            position_start=e.get("position_start"),
            position_end=e.get("position_end")
        )
        errors_to_add.append(error_entry)

    if errors_to_add:
        db.add_all(errors_to_add)
        db.commit()
        
    return text_entry