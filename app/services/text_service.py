import time
import uuid
from sqlalchemy.orm import Session
from app.models.text import TextSubmission
from app.models.error import Error
from app.schemas.text import TextAnalyzeRequest


def analyze_text(db: Session, user_id, data: TextAnalyzeRequest):
    start = time.time()

    # 🔥 MOCK IA
    corrected = data.text.capitalize()
    score = 85.0

    text_entry = TextSubmission(
        id=uuid.uuid4(),
        user_id=user_id,
        original_text=data.text,
        corrected_text=corrected,
        mode=data.mode,
        target_level=data.target_level,
        score=score,
        processing_time=time.time() - start
    )

    db.add(text_entry)
    db.commit()
    db.refresh(text_entry)

    return text_entry