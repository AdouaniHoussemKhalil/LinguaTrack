"""Ajoute texts.feedback (appréciation globale du LLM)

Revision ID: 9d39f47dc696
Revises: 8de2cf1f0969
Create Date: 2026-09-25 16:35:41.464200

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d39f47dc696'
down_revision: Union[str, Sequence[str], None] = '8de2cf1f0969'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('texts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('feedback', sa.Text(), nullable=True))



def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('texts', schema=None) as batch_op:
        batch_op.drop_column('feedback')

