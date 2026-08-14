"""add dienstschichten table (Schichtplanung)

Revision ID: f1a2b3c4d5e6
Revises: a57a595c3ee7
Create Date: 2026-08-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = 'a57a595c3ee7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('dienstschichten',
        sa.Column('id',          sa.String(length=36), nullable=False),
        sa.Column('company_id',  sa.String(length=36), nullable=False),
        sa.Column('employee_id', sa.String(length=36), nullable=False),
        sa.Column('datum',       sa.Date(),             nullable=False),
        sa.Column('schicht_typ', sa.String(length=20),  nullable=False),
        sa.Column('beginn',      sa.Time(),             nullable=True),
        sa.Column('ende',        sa.Time(),             nullable=True),
        sa.Column('bereich',     sa.String(length=100), nullable=True),
        sa.Column('notiz',       sa.String(length=500), nullable=True),
        sa.Column('created_by',  sa.String(length=36),  nullable=True),
        sa.Column('created_at',  sa.DateTime(),         nullable=True),
        sa.Column('updated_at',  sa.DateTime(),         nullable=True),
        sa.ForeignKeyConstraint(['company_id'],  ['companies.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
        sa.ForeignKeyConstraint(['created_by'],  ['employees.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'employee_id', 'datum',
                            name='uq_dienstschicht_employee_datum'),
    )
    with op.batch_alter_table('dienstschichten', schema=None) as batch_op:
        batch_op.create_index('ix_dienstschichten_company_id',  ['company_id'],  unique=False)
        batch_op.create_index('ix_dienstschichten_employee_id', ['employee_id'], unique=False)
        batch_op.create_index('ix_dienstschichten_datum',       ['datum'],       unique=False)


def downgrade():
    with op.batch_alter_table('dienstschichten', schema=None) as batch_op:
        batch_op.drop_index('ix_dienstschichten_datum')
        batch_op.drop_index('ix_dienstschichten_employee_id')
        batch_op.drop_index('ix_dienstschichten_company_id')

    op.drop_table('dienstschichten')
