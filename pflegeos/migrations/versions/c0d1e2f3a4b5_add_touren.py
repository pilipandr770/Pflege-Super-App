"""add touren and tour_stops tables

Revision ID: c0d1e2f3a4b5
Revises: a8b9c0d1e2f3
Create Date: 2024-01-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'c0d1e2f3a4b5'
down_revision = 'a8b9c0d1e2f3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'touren',
        sa.Column('id',          sa.String(36), primary_key=True),
        sa.Column('company_id',  sa.String(36), sa.ForeignKey('companies.id'),  nullable=False),
        sa.Column('employee_id', sa.String(36), sa.ForeignKey('employees.id'),  nullable=False),
        sa.Column('created_by',  sa.String(36), sa.ForeignKey('employees.id'),  nullable=False),
        sa.Column('tour_nr',     sa.String(50),  nullable=True),
        sa.Column('datum',       sa.Date(),      nullable=False),
        sa.Column('start_zeit',  sa.Time(),      nullable=True),
        sa.Column('end_zeit',    sa.Time(),      nullable=True),
        sa.Column('kfz_nr',      sa.String(50),  nullable=True),
        sa.Column('status',      sa.String(20),  server_default='GEPLANT'),
        sa.Column('notizen',     sa.Text(),      nullable=True),
        sa.Column('created_at',  sa.DateTime(),  nullable=True),
        sa.Column('updated_at',  sa.DateTime(),  nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_touren_company_datum',  'touren', ['company_id', 'datum'])
    op.create_index('ix_touren_employee_datum', 'touren', ['employee_id', 'datum'])

    op.create_table(
        'tour_stops',
        sa.Column('id',                    sa.String(36), primary_key=True),
        sa.Column('tour_id',               sa.String(36), sa.ForeignKey('touren.id'),   nullable=False),
        sa.Column('patient_id',            sa.String(36), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('reihenfolge',           sa.Integer(),  server_default='0'),
        sa.Column('geplante_ankunft',      sa.Time(),     nullable=True),
        sa.Column('geplante_dauer',        sa.Integer(),  server_default='30'),
        sa.Column('tatsaechliche_ankunft', sa.Time(),     nullable=True),
        sa.Column('tatsaechliche_dauer',   sa.Integer(),  nullable=True),
        sa.Column('status',                sa.String(20), server_default='GEPLANT'),
        sa.Column('notizen',               sa.Text(),     nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tour_stops_tour_id', 'tour_stops', ['tour_id'])


def downgrade():
    op.drop_index('ix_tour_stops_tour_id',   table_name='tour_stops')
    op.drop_table('tour_stops')
    op.drop_index('ix_touren_employee_datum', table_name='touren')
    op.drop_index('ix_touren_company_datum',  table_name='touren')
    op.drop_table('touren')
