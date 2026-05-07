"""Add superadmin flag to employees and subscription_payments table

Revision ID: b1c2d3e4f5a6
Revises: 4daa807bb1f3
Create Date: 2026-06-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b1c2d3e4f5a6'
down_revision = '4daa807bb1f3'
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. is_superadmin column on employees ──────────────────
    op.add_column(
        'employees',
        sa.Column('is_superadmin', sa.Boolean(), nullable=False,
                  server_default=sa.text('false'))
    )

    # ── 2. subscription_payments table ───────────────────────
    op.create_table(
        'subscription_payments',
        sa.Column('id',             sa.String(36),           nullable=False),
        sa.Column('company_id',     sa.String(36),           nullable=False),
        sa.Column('plan',           sa.String(20),           nullable=False),
        sa.Column('betrag',         sa.Numeric(10, 2),       nullable=False),
        sa.Column('waehrung',       sa.String(3),            nullable=True,  server_default='EUR'),
        sa.Column('period_start',   sa.Date(),               nullable=False),
        sa.Column('period_end',     sa.Date(),               nullable=False),
        sa.Column('status',         sa.String(20),           nullable=True,  server_default='PENDING'),
        sa.Column('payment_method', sa.String(50),           nullable=True),
        sa.Column('payment_ref',    sa.String(255),          nullable=True),
        sa.Column('rechnung_nr',    sa.String(50),           nullable=True),
        sa.Column('paid_at',        sa.DateTime(),           nullable=True),
        sa.Column('notiz',          sa.Text(),               nullable=True),
        sa.Column('created_at',     sa.DateTime(),           nullable=True,
                  server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_subscription_payments_company_id', 'subscription_payments', ['company_id'])
    op.create_index('ix_subscription_payments_paid_at',    'subscription_payments', ['paid_at'])


def downgrade():
    op.drop_index('ix_subscription_payments_paid_at',    'subscription_payments')
    op.drop_index('ix_subscription_payments_company_id', 'subscription_payments')
    op.drop_table('subscription_payments')
    op.drop_column('employees', 'is_superadmin')
