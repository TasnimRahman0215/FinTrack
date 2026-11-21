"""security events

Adds security_events: sign-ins, password changes and access changes (IDs, IPs and browsers only),
shown to each user as "Recent activity" and kept for a year.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-21 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('security_events',
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('event', sa.String(length=40), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('household_id', sa.Integer(), nullable=True),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.Column('user_agent', sa.String(length=255), nullable=True),
    sa.Column('details', sa.JSON(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['household_id'], ['households.id'], name=op.f('fk_security_events_household_id_households'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_security_events_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_security_events'))
    )
    with op.batch_alter_table('security_events', schema=None) as batch_op:
        batch_op.create_index('ix_security_events_created_at', ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_security_events_household_id'), ['household_id'], unique=False)
        batch_op.create_index('ix_security_events_user_id_created_at', ['user_id', 'created_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('security_events', schema=None) as batch_op:
        batch_op.drop_index('ix_security_events_user_id_created_at')
        batch_op.drop_index(batch_op.f('ix_security_events_household_id'))
        batch_op.drop_index('ix_security_events_created_at')
    op.drop_table('security_events')
