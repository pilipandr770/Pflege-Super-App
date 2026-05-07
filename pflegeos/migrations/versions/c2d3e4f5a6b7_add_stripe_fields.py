"""Add Stripe fields to companies and subscription_payments

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-06-02 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'c2d3e4f5a6b7'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. Stripe fields on companies ────────────────────────
    op.add_column('companies', sa.Column('stripe_customer_id',     sa.String(100), nullable=True))
    op.add_column('companies', sa.Column('stripe_subscription_id', sa.String(100), nullable=True))
    op.add_column('companies', sa.Column('subscription_status',    sa.String(30),  nullable=True))
    op.add_column('companies', sa.Column('current_period_end',     sa.DateTime(),  nullable=True))

    op.create_unique_constraint('uq_companies_stripe_customer_id',     'companies', ['stripe_customer_id'])
    op.create_unique_constraint('uq_companies_stripe_subscription_id', 'companies', ['stripe_subscription_id'])

    # ── 2. Stripe fields on subscription_payments ─────────────
    op.add_column('subscription_payments', sa.Column('stripe_invoice_id',      sa.String(100), nullable=True))
    op.add_column('subscription_payments', sa.Column('stripe_subscription_id', sa.String(100), nullable=True))

    op.create_index('ix_subscription_payments_stripe_invoice_id', 'subscription_payments', ['stripe_invoice_id'])


def downgrade():
    op.drop_index('ix_subscription_payments_stripe_invoice_id', 'subscription_payments')
    op.drop_column('subscription_payments', 'stripe_subscription_id')
    op.drop_column('subscription_payments', 'stripe_invoice_id')

    op.drop_constraint('uq_companies_stripe_subscription_id', 'companies', type_='unique')
    op.drop_constraint('uq_companies_stripe_customer_id',     'companies', type_='unique')
    op.drop_column('companies', 'current_period_end')
    op.drop_column('companies', 'subscription_status')
    op.drop_column('companies', 'stripe_subscription_id')
    op.drop_column('companies', 'stripe_customer_id')
