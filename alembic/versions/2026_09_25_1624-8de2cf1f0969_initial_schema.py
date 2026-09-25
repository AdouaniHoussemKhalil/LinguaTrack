"""Schéma initial (identique aux tables créées par create_all avant Alembic)

Revision ID: 8de2cf1f0969
Revises: 
Create Date: 2026-09-25 16:24:57.539118

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8de2cf1f0969'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('password', sa.String(), nullable=False),
    sa.Column('first_name', sa.String(), nullable=False),
    sa.Column('last_name', sa.String(), nullable=False),
    sa.Column('level', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_index('ix_users_id', 'users', ['id'], unique=False)

    op.create_table('texts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('original_text', sa.Text(), nullable=False),
    sa.Column('corrected_text', sa.Text(), nullable=False),
    sa.Column('mode', sa.String(), nullable=False),
    sa.Column('target_level', sa.String(), nullable=True),
    sa.Column('score', sa.Float(), nullable=True),
    sa.Column('processing_time', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_texts_id', 'texts', ['id'], unique=False)

    op.create_table('user_error_stats',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('error_type', sa.String(), nullable=True),
    sa.Column('count', sa.Integer(), nullable=True),
    sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('errors',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('text_id', sa.UUID(), nullable=True),
    sa.Column('error_type', sa.String(), nullable=False),
    sa.Column('severity', sa.String(), nullable=True),
    sa.Column('original_fragment', sa.Text(), nullable=False),
    sa.Column('corrected_fragment', sa.Text(), nullable=False),
    sa.Column('explanation', sa.Text(), nullable=True),
    sa.Column('position_start', sa.Integer(), nullable=True),
    sa.Column('position_end', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    sa.ForeignKeyConstraint(['text_id'], ['texts.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_errors_id', 'errors', ['id'], unique=False)



def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_errors_id', table_name='errors')

    op.drop_table('errors')
    op.drop_table('user_error_stats')
    op.drop_index('ix_texts_id', table_name='texts')

    op.drop_table('texts')
    op.drop_index('ix_users_id', table_name='users')

    op.drop_table('users')
