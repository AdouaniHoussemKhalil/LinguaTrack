import time
import uuid
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.text import TextSubmission
from app.models.error import Error
from app.schemas.text import TextAnalyzeRequest
from app.services.llm_service import generate_analysis



def get_user_texts(db: Session, user_id: UUID):
    return db.query(TextSubmission).filter(TextSubmission.user_id == user_id).all()

def get_user_text(db: Session, user_id: UUID, text_id: UUID):
    return db.query(TextSubmission).filter(TextSubmission.user_id == user_id, TextSubmission.id == text_id).first()


def analyze_text(db: Session, user_id, base_request_id, data: TextAnalyzeRequest):
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
        base_request_id=base_request_id if base_request_id else None,
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