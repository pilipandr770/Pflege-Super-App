"""Add medication_documents table for auto-generated medication documents

Revision ID: 006
Revises: 005
Create Date: 2026-05-04

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    # Create medication_documents table
    op.create_table(
        'medication_documents',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('company_id', sa.String(36), nullable=False),
        sa.Column('patient_id', sa.String(36), nullable=False),
        sa.Column('medication_plan_id', sa.String(36), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=False),
        sa.Column('document_type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('superseded_at', sa.DateTime, nullable=True),
        sa.Column('superseded_by', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id']),
        sa.ForeignKeyConstraint(['medication_plan_id'], ['medication_plans.id']),
        sa.ForeignKeyConstraint(['created_by'], ['employees.id']),
        sa.ForeignKeyConstraint(['superseded_by'], ['medication_documents.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_medication_documents_patient_id', 'medication_documents', ['patient_id'])
    op.create_index('ix_medication_documents_company_id', 'medication_documents', ['company_id'])
    op.create_index('ix_medication_documents_status', 'medication_documents', ['status'])
    op.create_index('ix_medication_documents_created_at', 'medication_documents', ['created_at'])


def downgrade():
    op.drop_index('ix_medication_documents_created_at', 'medication_documents')
    op.drop_index('ix_medication_documents_status', 'medication_documents')
    op.drop_index('ix_medication_documents_company_id', 'medication_documents')
    op.drop_index('ix_medication_documents_patient_id', 'medication_documents')
    op.drop_table('medication_documents')
