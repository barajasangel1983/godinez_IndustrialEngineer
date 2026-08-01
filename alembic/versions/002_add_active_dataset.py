"""add active_dataset column to sessions

Revision ID: 002
Revises: 001
Create Date: 2026-08-01

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add active_dataset column to sessions — tracks the dataset filename
    set via the "Load dataset" command, shared across uvicorn workers."""
    op.add_column('sessions', sa.Column('active_dataset', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('sessions', 'active_dataset')
