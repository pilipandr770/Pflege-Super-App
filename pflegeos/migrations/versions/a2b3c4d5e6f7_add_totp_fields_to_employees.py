"""Add TOTP 2FA fields to employees table

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-08-14 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'a2b3c4d5e6f7'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('employees',
        sa.Column('totp_secret', sa.Text(), nullable=True))
    op.add_column('employees',
        sa.Column('totp_enabled', sa.Boolean(), nullable=False,
                  server_default=sa.text('false')))


def downgrade():
    op.drop_column('employees', 'totp_enabled')
    op.drop_column('employees', 'totp_secret')
