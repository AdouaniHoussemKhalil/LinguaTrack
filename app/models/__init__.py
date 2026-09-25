# Importe toutes les tables pour qu'elles soient connues de Base.metadata (Alembic, create_all)
from app.models.error import Error
from app.models.error_stats import UserErrorStats
from app.models.text import TextSubmission
from app.models.user import User

__all__ = ["Error", "TextSubmission", "User", "UserErrorStats"]
