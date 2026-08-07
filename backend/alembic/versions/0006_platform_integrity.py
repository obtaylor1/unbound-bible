"""Add AI provenance records and legacy forum identity mapping."""
from alembic import op
import sqlalchemy as sa

revision = '0006_platform_integrity'
down_revision = '0007_verified_ingest'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('legacy_forum_user_id', sa.Integer(), nullable=True))
    op.create_index('ux_users_legacy_forum_user_id', 'users', ['legacy_forum_user_id'], unique=True)
    op.create_table('ai_operations', sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL')), sa.Column('question_hash', sa.String(64), nullable=False), sa.Column('provider', sa.String(50), nullable=False), sa.Column('model', sa.String(100), nullable=False), sa.Column('grounding_status', sa.String(30), nullable=False), sa.Column('source_ids', sa.JSON(), nullable=False), sa.Column('validation_errors', sa.JSON(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('ix_ai_operations_user_id', 'ai_operations', ['user_id']); op.create_index('ix_ai_operations_question_hash', 'ai_operations', ['question_hash'])


def downgrade() -> None:
    op.drop_table('ai_operations'); op.drop_index('ux_users_legacy_forum_user_id', table_name='users'); op.drop_column('users', 'legacy_forum_user_id')
