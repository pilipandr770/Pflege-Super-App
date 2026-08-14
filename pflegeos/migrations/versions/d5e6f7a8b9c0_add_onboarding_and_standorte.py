"""add onboarding_completed to companies, add standorte table

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2024-01-21 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'd5e6f7a8b9c0'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade():
    # onboarding_completed auf Company
    op.add_column('companies',
        sa.Column('onboarding_completed', sa.Boolean(), server_default='false', nullable=False)
    )

    # Standorte-Tabelle
    op.create_table(
        'standorte',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('kuerzel', sa.String(10)),
        sa.Column('beschreibung', sa.Text),
        sa.Column('strasse', sa.String(255)),
        sa.Column('hausnummer', sa.String(20)),
        sa.Column('plz', sa.String(10)),
        sa.Column('ort', sa.String(100)),
        sa.Column('telefon', sa.String(50)),
        sa.Column('leiter_id', sa.String(36), sa.ForeignKey('employees.id')),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('company_id', 'kuerzel', name='uq_standort_kuerzel'),
    )
    op.create_index('ix_standorte_company_id', 'standorte', ['company_id'])


def downgrade():
    op.drop_index('ix_standorte_company_id', table_name='standorte')
    op.drop_table('standorte')
    op.drop_column('companies', 'onboarding_completed')
