"""Add patient_photos table for storing patient images

Revision ID: 001
Revises: 978a3c261b7e
Create Date: 2026-05-04

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001'
down_revision = '978a3c261b7e'  # Comes after initial schema
branch_labels = None
depends_on = None


def upgrade():
    # Create patient_photos table
    op.create_table(
        'patient_photos',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('company_id', sa.String(36), nullable=False),
        sa.Column('patient_id', sa.String(36), nullable=False),
        sa.Column('employee_id', sa.String(36), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('file_size', sa.Integer, nullable=True),
        sa.Column('mime_type', sa.String(50), nullable=True, server_default='image/jpeg'),
        sa.Column('geo_lat', sa.Float, nullable=True),
        sa.Column('geo_lng', sa.Float, nullable=True),
        sa.Column('geo_accuracy', sa.Float, nullable=True),
        sa.Column('device_mac', sa.String(17), nullable=True),
        sa.Column('device_model', sa.String(255), nullable=True),
        sa.Column('photo_type', sa.String(50), nullable=True, server_default='GENERAL'),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('tags', sa.String(500), nullable=True),
        sa.Column('verified_by', sa.String(36), nullable=True),
        sa.Column('verified_at', sa.DateTime, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
        sa.ForeignKeyConstraint(['verified_by'], ['employees.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_patient_photos_patient_id', 'patient_photos', ['patient_id'])
    op.create_index('ix_patient_photos_company_id', 'patient_photos', ['company_id'])
    op.create_index('ix_patient_photos_created_at', 'patient_photos', ['created_at'])
    op.create_index('ix_patient_photos_is_active', 'patient_photos', ['is_active'])


def downgrade():
    op.drop_index('ix_patient_photos_is_active', 'patient_photos')
    op.drop_index('ix_patient_photos_created_at', 'patient_photos')
    op.drop_index('ix_patient_photos_company_id', 'patient_photos')
    op.drop_index('ix_patient_photos_patient_id', 'patient_photos')
    op.drop_table('patient_photos')
