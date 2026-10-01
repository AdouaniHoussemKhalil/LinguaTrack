"""Comptes délégués au service d'authentification : users.auth_user_id remplace users.password

Les comptes existants gardent leurs données ; ils sont reliés à leur compte du service d'auth par
l'e-mail (vérifié) à la première connexion.

Revision ID: c0019cb706b1
Revises: 15f5db16a01c
Create Date: 2026-10-01 13:26:54.828498

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c0019cb706b1'
down_revision: Union[str, Sequence[str], None] = '15f5db16a01c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# SQLite recrée la table (mode batch) et relirait l'UUID comme NUMERIC : on impose le type d'origine
USERS_ID = [sa.Column('id', sa.UUID(), primary_key=True)]


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('users', schema=None, reflect_args=USERS_ID) as batch_op:
        batch_op.add_column(sa.Column('auth_user_id', sa.String(), nullable=True))
        batch_op.create_index(batch_op.f('ix_users_auth_user_id'), ['auth_user_id'], unique=True)
        batch_op.drop_column('password')


def downgrade() -> None:
    """Downgrade schema : les mots de passe supprimés ne reviennent pas (valeur vide, connexion impossible)."""
    with op.batch_alter_table('users', schema=None, reflect_args=USERS_ID) as batch_op:
        batch_op.add_column(sa.Column('password', sa.VARCHAR(), nullable=False, server_default=''))
        batch_op.drop_index(batch_op.f('ix_users_auth_user_id'))
        batch_op.drop_column('auth_user_id')
