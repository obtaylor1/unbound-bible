"""Create unified community tables with legacy ID mapping fields."""
from alembic import op
import sqlalchemy as sa

revision = '0005_community_migration'
down_revision = '0004_notifications'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('community_posts', sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('legacy_id', sa.Integer(), unique=True), sa.Column('title', sa.String(180), nullable=False), sa.Column('content', sa.Text(), nullable=False), sa.Column('author_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('ix_community_posts_author_id', 'community_posts', ['author_id'])
    op.create_table('community_comments', sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('legacy_id', sa.Integer(), unique=True), sa.Column('content', sa.Text(), nullable=False), sa.Column('post_id', sa.Uuid(), sa.ForeignKey('community_posts.id', ondelete='CASCADE'), nullable=False), sa.Column('author_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('ix_community_comments_post_id', 'community_comments', ['post_id']); op.create_index('ix_community_comments_author_id', 'community_comments', ['author_id'])


def downgrade() -> None:
    op.drop_table('community_comments'); op.drop_table('community_posts')
