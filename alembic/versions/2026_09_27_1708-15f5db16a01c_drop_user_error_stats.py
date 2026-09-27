"""Supprime la table user_error_stats, jamais utilisée

Revision ID: 15f5db16a01c
Revises: 9d39f47dc696
Create Date: 2026-09-27 17:08:48.378409

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '15f5db16a01c'
down_revision: Union[str, Sequence[str], None] = '9d39f47dc696'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # IF EXISTS : une base peut ne jamais avoir eu cette table (SQLite et PostgreSQL l'acceptent)
    op.execute("DROP TABLE IF EXISTS user_error_stats")


def downgrade() -> None:
    """Downgrade schema : recrée la table telle que dans la migration initiale."""
    op.create_table('user_error_stats',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('error_type', sa.String(), nullable=True),
    sa.Column('count', sa.Integer(), nullable=True),
    sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
