"""Add care_type and address fields to patients table

Revision ID: 007
Revises: 006
Create Date: 2026-05-04

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    # Add address fields for home care
    op.add_column('patients', sa.Column('strasse', sa.String(255), nullable=True))
    op.add_column('patients', sa.Column('hausnummer', sa.String(20), nullable=True))
    op.add_column('patients', sa.Column('plz', sa.String(10), nullable=True))
    op.add_column('patients', sa.Column('ort', sa.String(100), nullable=True))
    op.add_column('patients', sa.Column('bundesland', sa.String(50), nullable=True))

    # Add care_type field (HOME_CARE or INPATIENT)
    op.add_column('patients', sa.Column('care_type', sa.String(30), nullable=False, server_default='HOME_CARE'))


def downgrade():
    op.drop_column('patients', 'care_type')
    op.drop_column('patients', 'bundesland')
    op.drop_column('patients', 'ort')
    op.drop_column('patients', 'plz')
    op.drop_column('patients', 'hausnummer')
    op.drop_column('patients', 'strasse')
