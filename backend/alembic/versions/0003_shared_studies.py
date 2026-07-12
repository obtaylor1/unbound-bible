"""Create immutable shared study snapshots."""
from alembic import op
import sqlalchemy as sa

revision = '0003_shared_studies'
down_revision = '0002_studies_and_notes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('shared_studies',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('owner_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_study_id', sa.Uuid(), sa.ForeignKey('study_sessions.id', ondelete='SET NULL')),
        sa.Column('public_id_hash', sa.String(64), nullable=False), sa.Column('public_id', sa.String(64), nullable=False, unique=True), sa.Column('title', sa.String(200), nullable=False),
        sa.Column('session_type', sa.String(30), nullable=False, server_default='study'),
        sa.Column('messages_snapshot', sa.JSON(), nullable=False), sa.Column('sources_snapshot', sa.JSON(), nullable=False),
        sa.Column('visibility', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True)))
    op.create_index('ix_shared_studies_owner_id', 'shared_studies', ['owner_id'])
    op.create_index('ux_shared_studies_public_id_hash', 'shared_studies', ['public_id_hash'], unique=True)
    op.create_index('ix_shared_studies_public_listing', 'shared_studies', ['visibility', 'revoked_at', 'created_at'])


def downgrade() -> None:
    op.drop_table('shared_studies')
