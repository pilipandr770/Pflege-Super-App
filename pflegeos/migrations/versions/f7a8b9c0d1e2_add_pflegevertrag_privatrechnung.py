"""add pflegevertraege and privatrechnungen tables

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2024-01-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'f7a8b9c0d1e2'
down_revision = 'e6f7a8b9c0d1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'pflegevertraege',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('patient_id', sa.String(36), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('employees.id'), nullable=False),
        sa.Column('vertrag_nr', sa.String(50), nullable=True),
        sa.Column('abschluss_datum', sa.Date(), nullable=False),
        sa.Column('beginn_datum', sa.Date(), nullable=False),
        sa.Column('ende_datum', sa.Date(), nullable=True),
        sa.Column('leistungen', sa.Text(), nullable=True),
        sa.Column('verguetung', sa.Text(), nullable=True),
        sa.Column('kuendigungsfrist_patient', sa.String(100), nullable=True),
        sa.Column('kuendigungsfrist_dienst', sa.String(100), nullable=True),
        sa.Column('unterschrift_patient', sa.Boolean(), default=False),
        sa.Column('unterschrift_vertreter', sa.Boolean(), default=False),
        sa.Column('vertreter_name', sa.String(255), nullable=True),
        sa.Column('unterschrift_pdl', sa.Boolean(), default=False),
        sa.Column('unterzeichnet_am', sa.Date(), nullable=True),
        sa.Column('status', sa.String(20), server_default='ENTWURF'),
        sa.Column('kuendigung_datum', sa.Date(), nullable=True),
        sa.Column('kuendigung_durch', sa.String(50), nullable=True),
        sa.Column('kuendigung_grund', sa.Text(), nullable=True),
        sa.Column('notizen', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pflegevertraege_company_id', 'pflegevertraege', ['company_id'])
    op.create_index('ix_pflegevertraege_patient_id', 'pflegevertraege', ['patient_id'])
    op.create_index('ix_pflegevertraege_status', 'pflegevertraege', ['status'])

    op.create_table(
        'privatrechnungen',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('patient_id', sa.String(36), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('employees.id'), nullable=False),
        sa.Column('rechnung_nr', sa.String(50), nullable=False),
        sa.Column('rechnungsdatum', sa.Date(), nullable=False),
        sa.Column('leistungsmonat', sa.String(7), nullable=True),
        sa.Column('positionen', sa.Text(), nullable=True),
        sa.Column('betrag_netto', sa.Numeric(10, 2), server_default='0'),
        sa.Column('mwst_betrag', sa.Numeric(10, 2), server_default='0'),
        sa.Column('betrag_brutto', sa.Numeric(10, 2), server_default='0'),
        sa.Column('zahlungsziel_tage', sa.Integer(), server_default='14'),
        sa.Column('faellig_am', sa.Date(), nullable=True),
        sa.Column('status', sa.String(20), server_default='ENTWURF'),
        sa.Column('bezahlt_am', sa.Date(), nullable=True),
        sa.Column('zahlungsart', sa.String(30), nullable=True),
        sa.Column('notizen', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_privatrechnungen_company_id',     'privatrechnungen', ['company_id'])
    op.create_index('ix_privatrechnungen_patient_id',     'privatrechnungen', ['patient_id'])
    op.create_index('ix_privatrechnungen_status',         'privatrechnungen', ['status'])
    op.create_index('ix_privatrechnungen_rechnungsdatum', 'privatrechnungen', ['rechnungsdatum'])


def downgrade():
    op.drop_index('ix_privatrechnungen_rechnungsdatum', table_name='privatrechnungen')
    op.drop_index('ix_privatrechnungen_status',         table_name='privatrechnungen')
    op.drop_index('ix_privatrechnungen_patient_id',     table_name='privatrechnungen')
    op.drop_index('ix_privatrechnungen_company_id',     table_name='privatrechnungen')
    op.drop_table('privatrechnungen')

    op.drop_index('ix_pflegevertraege_status',     table_name='pflegevertraege')
    op.drop_index('ix_pflegevertraege_patient_id', table_name='pflegevertraege')
    op.drop_index('ix_pflegevertraege_company_id', table_name='pflegevertraege')
    op.drop_table('pflegevertraege')
