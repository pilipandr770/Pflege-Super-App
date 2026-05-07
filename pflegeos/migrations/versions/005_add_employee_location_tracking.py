"""Add employee location tracking table (Phase 4)

Revision ID: 005
Revises: 004
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'employee_locations',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('company_id', sa.String(36), nullable=False),
        sa.Column('employee_id', sa.String(36), nullable=False),
        sa.Column('geo_lat', sa.Float(), nullable=False),
        sa.Column('geo_lng', sa.Float(), nullable=False),
        sa.Column('geo_accuracy', sa.Float(), nullable=True),
        sa.Column('device_mac', sa.String(17), nullable=True),
        sa.Column('device_model', sa.String(255), nullable=True),
        sa.Column('speed', sa.Float(), nullable=True),
        sa.Column('heading', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_employee_locations_company_id',
        'employee_locations',
        ['company_id'],
        unique=False
    )
    op.create_index(
        'ix_employee_locations_employee_id',
        'employee_locations',
        ['employee_id'],
        unique=False
    )
    op.create_index(
        'ix_employee_locations_created_at',
        'employee_locations',
        ['created_at'],
        unique=False
    )
    op.create_index(
        'ix_employee_locations_is_active',
        'employee_locations',
        ['is_active'],
        unique=False
    )


def downgrade():
    op.drop_index('ix_employee_locations_is_active', table_name='employee_locations')
    op.drop_index('ix_employee_locations_created_at', table_name='employee_locations')
    op.drop_index('ix_employee_locations_employee_id', table_name='employee_locations')
    op.drop_index('ix_employee_locations_company_id', table_name='employee_locations')
    op.drop_table('employee_locations')
