"""add hkp_verordnungen table

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'e6f7a8b9c0d1'
down_revision = 'd5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'hkp_verordnungen',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('verordnungs_nr', sa.String(50), nullable=True),
        sa.Column('arzt_name', sa.String(255), nullable=False),
        sa.Column('arzt_lanr', sa.String(9), nullable=True),
        sa.Column('arzt_bsnr', sa.String(9), nullable=True),
        sa.Column('arzt_adresse', sa.Text(), nullable=True),
        sa.Column('arzt_telefon', sa.String(50), nullable=True),
        sa.Column('diagnosen', sa.Text(), nullable=True),
        sa.Column('leistungen', sa.Text(), nullable=True),
        sa.Column('gueltig_von', sa.Date(), nullable=False),
        sa.Column('gueltig_bis', sa.Date(), nullable=False),
        sa.Column('dauer_wochen', sa.Integer(), nullable=True),
        sa.Column('begruendung_langzeit', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=True, server_default='ENTWURF'),
        sa.Column('eingereicht_am', sa.DateTime(), nullable=True),
        sa.Column('genehmigt_am', sa.DateTime(), nullable=True),
        sa.Column('genehmigungsnummer', sa.String(100), nullable=True),
        sa.Column('ablehnungsgrund', sa.Text(), nullable=True),
        sa.Column('notizen', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_hkp_company_patient', 'hkp_verordnungen',
                    ['company_id', 'patient_id'])
    op.create_index('ix_hkp_status', 'hkp_verordnungen', ['status'])


def downgrade():
    op.drop_index('ix_hkp_status', table_name='hkp_verordnungen')
    op.drop_index('ix_hkp_company_patient', table_name='hkp_verordnungen')
    op.drop_table('hkp_verordnungen')
