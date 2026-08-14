"""add gkv_abrechnungen table

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2024-01-20 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'c4d5e6f7a8b9'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'gkv_abrechnungen',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('patient_id', sa.String(36), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('employees.id'), nullable=False),
        sa.Column('abrechnungsmonat', sa.String(7), nullable=False),
        sa.Column('krankenkasse', sa.String(255)),
        sa.Column('ik_nummer_kasse', sa.String(20)),
        sa.Column('ik_nummer_dienst', sa.String(20)),
        sa.Column('pflegegrad', sa.String(1)),
        sa.Column('sachleistungen_betrag', sa.Numeric(10, 2), server_default='0'),
        sa.Column('verhinderungspflege', sa.Numeric(10, 2), server_default='0'),
        sa.Column('pflegehilfsmittel', sa.Numeric(10, 2), server_default='0'),
        sa.Column('entlastungsbetrag', sa.Numeric(10, 2), server_default='0'),
        sa.Column('gesamtbetrag', sa.Numeric(10, 2), server_default='0'),
        sa.Column('anzahl_einsaetze', sa.Integer, server_default='0'),
        sa.Column('anzahl_stunden', sa.Numeric(6, 2), server_default='0'),
        sa.Column('status', sa.String(20), server_default='ENTWURF'),
        sa.Column('eingereicht_am', sa.DateTime),
        sa.Column('notizen', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('company_id', 'patient_id', 'abrechnungsmonat',
                            name='uq_gkv_patient_monat'),
    )
    op.create_index('ix_gkv_company_monat', 'gkv_abrechnungen',
                    ['company_id', 'abrechnungsmonat'])
    op.create_index('ix_gkv_patient', 'gkv_abrechnungen', ['patient_id'])


def downgrade():
    op.drop_index('ix_gkv_patient', table_name='gkv_abrechnungen')
    op.drop_index('ix_gkv_company_monat', table_name='gkv_abrechnungen')
    op.drop_table('gkv_abrechnungen')
