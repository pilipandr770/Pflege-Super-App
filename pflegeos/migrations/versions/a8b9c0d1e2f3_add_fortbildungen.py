"""add fortbildungen table

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2024-01-03 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'a8b9c0d1e2f3'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'fortbildungen',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company_id',  sa.String(36), sa.ForeignKey('companies.id'),  nullable=False),
        sa.Column('employee_id', sa.String(36), sa.ForeignKey('employees.id'),  nullable=False),
        sa.Column('created_by',  sa.String(36), sa.ForeignKey('employees.id'),  nullable=False),
        sa.Column('titel',    sa.String(255), nullable=False),
        sa.Column('anbieter', sa.String(255), nullable=True),
        sa.Column('ort',      sa.String(255), nullable=True),
        sa.Column('datum_von', sa.Date(), nullable=False),
        sa.Column('datum_bis', sa.Date(), nullable=True),
        sa.Column('stunden', sa.Numeric(5, 1), server_default='8'),
        sa.Column('themenbereich', sa.String(30), server_default='PFLEGE'),
        sa.Column('pflicht_fortbildung', sa.Boolean(), server_default='false'),
        sa.Column('zertifikat_pfad', sa.String(500), nullable=True),
        sa.Column('kosten', sa.Numeric(8, 2), nullable=True),
        sa.Column('status', sa.String(20), server_default='GEPLANT'),
        sa.Column('notizen', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_fortbildungen_company_id',  'fortbildungen', ['company_id'])
    op.create_index('ix_fortbildungen_employee_id', 'fortbildungen', ['employee_id'])
    op.create_index('ix_fortbildungen_datum_von',   'fortbildungen', ['datum_von'])
    op.create_index('ix_fortbildungen_status',      'fortbildungen', ['status'])


def downgrade():
    op.drop_index('ix_fortbildungen_status',      table_name='fortbildungen')
    op.drop_index('ix_fortbildungen_datum_von',   table_name='fortbildungen')
    op.drop_index('ix_fortbildungen_employee_id', table_name='fortbildungen')
    op.drop_index('ix_fortbildungen_company_id',  table_name='fortbildungen')
    op.drop_table('fortbildungen')
