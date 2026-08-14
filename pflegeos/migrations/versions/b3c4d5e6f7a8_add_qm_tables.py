"""add QM tables

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-08-14
"""
from alembic import op
import sqlalchemy as sa

revision = 'b3c4d5e6f7a8'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'qm_pruefungen',
        sa.Column('id',             sa.String(36),  primary_key=True),
        sa.Column('company_id',     sa.String(36),  sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('created_by',     sa.String(36),  sa.ForeignKey('employees.id'), nullable=False),
        sa.Column('typ',            sa.String(30),  nullable=False, server_default='INTERN'),
        sa.Column('titel',          sa.String(255), nullable=False),
        sa.Column('datum',          sa.Date,        nullable=False),
        sa.Column('pruefer',        sa.String(255), nullable=True),
        sa.Column('status',         sa.String(20),  server_default='OFFEN'),
        sa.Column('gesamtergebnis', sa.Text,        nullable=True),
        sa.Column('massnahmen',     sa.Text,        nullable=True),
        sa.Column('created_at',     sa.DateTime,    server_default=sa.func.now()),
        sa.Column('updated_at',     sa.DateTime,    server_default=sa.func.now()),
    )
    op.create_index('ix_qm_pruefungen_company_id', 'qm_pruefungen', ['company_id'])
    op.create_index('ix_qm_pruefungen_datum',      'qm_pruefungen', ['datum'])

    op.create_table(
        'qm_pruefung_items',
        sa.Column('id',          sa.String(36),  primary_key=True),
        sa.Column('pruefung_id', sa.String(36),  sa.ForeignKey('qm_pruefungen.id'), nullable=False),
        sa.Column('kategorie',   sa.String(100), nullable=False),
        sa.Column('kriterium',   sa.Text,        nullable=False),
        sa.Column('ergebnis',    sa.String(20),  server_default='OK'),
        sa.Column('bemerkung',   sa.Text,        nullable=True),
        sa.Column('massnahme',   sa.Text,        nullable=True),
        sa.Column('sort_order',  sa.Integer,     server_default='0'),
        sa.Column('created_at',  sa.DateTime,    server_default=sa.func.now()),
    )
    op.create_index('ix_qm_items_pruefung_id', 'qm_pruefung_items', ['pruefung_id'])


def downgrade():
    op.drop_table('qm_pruefung_items')
    op.drop_table('qm_pruefungen')
