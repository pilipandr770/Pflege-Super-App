"""Add employee patient assignments table

Revision ID: 004
Revises: 003
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'employee_patient_assignments',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('company_id', sa.String(36), nullable=False),
        sa.Column('employee_id', sa.String(36), nullable=False),
        sa.Column('patient_id', sa.String(36), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, server_default='PRIMARY_NURSE'),
        sa.Column('assigned_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('assigned_by', sa.String(36), nullable=True),
        sa.Column('unassigned_at', sa.DateTime(), nullable=True),
        sa.Column('unassigned_by', sa.String(36), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['assigned_by'], ['employees.id'], ),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
        sa.ForeignKeyConstraint(['unassigned_by'], ['employees.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_employee_patient_assignments_employee_id'),
        'employee_patient_assignments',
        ['employee_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_employee_patient_assignments_patient_id'),
        'employee_patient_assignments',
        ['patient_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_employee_patient_assignments_company_id'),
        'employee_patient_assignments',
        ['company_id'],
        unique=False
    )


def downgrade():
    op.drop_index(
        op.f('ix_employee_patient_assignments_company_id'),
        table_name='employee_patient_assignments'
    )
    op.drop_index(
        op.f('ix_employee_patient_assignments_patient_id'),
        table_name='employee_patient_assignments'
    )
    op.drop_index(
        op.f('ix_employee_patient_assignments_employee_id'),
        table_name='employee_patient_assignments'
    )
    op.drop_table('employee_patient_assignments')
