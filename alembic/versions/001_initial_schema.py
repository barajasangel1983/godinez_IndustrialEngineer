"""empty message

Revision ID: 001
Revises:
Create Date: 2026-07-30

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial schema: sessions, queries, results tables."""

    # ── Sessions table ──────────────────────────────────────
    op.create_table(
        'sessions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.String(64), nullable=False, unique=True),
        sa.Column('user_id', sa.String(128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_sessions_session_id'), 'sessions', ['session_id'], unique=False)

    # ── Queries table ───────────────────────────────────────
    op.create_table(
        'queries',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.String(64), sa.ForeignKey('sessions.session_id', ondelete='CASCADE'), nullable=False),
        sa.Column('query_text', sa.Text(), nullable=False),
        sa.Column('intent', sa.String(64), nullable=True),
        sa.Column('confidence', sa.Integer(), nullable=True),  # 0-100 stored as int
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_queries_session_id'), 'queries', ['session_id'], unique=False)
    op.create_index(op.f('ix_queries_intent'), 'queries', ['intent'], unique=False)
    op.create_index('ix_queries_session_timestamp', 'queries', ['session_id', 'timestamp'], unique=False)

    # ── Results table ───────────────────────────────────────
    op.create_table(
        'results',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('query_id', sa.Integer(), sa.ForeignKey('queries.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('intent', sa.String(64), nullable=True),
        sa.Column('response', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('charts', sa.JSON(), nullable=True),
        sa.Column('errors', sa.JSON(), nullable=True),
    )
    op.create_index(op.f('ix_results_intent'), 'results', ['intent'], unique=False)


def downgrade() -> None:
    """Drop all tables in reverse order (cascade-safe)."""
    op.drop_table('results')
    op.drop_table('queries')
    op.drop_table('sessions')
