"""connection sync lock

Adds connections.sync_lock_until, a lock shared by every process that syncs (the API and the
optional worker), replacing an in-memory thread lock that only worked inside one process.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-13 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('connections', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sync_lock_until', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('connections', schema=None) as batch_op:
        batch_op.drop_column('sync_lock_until')
