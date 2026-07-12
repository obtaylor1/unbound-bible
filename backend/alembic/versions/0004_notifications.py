"""Create notification inbox and preferences."""
from alembic import op
import sqlalchemy as sa

revision = '0004_notifications'
down_revision = '0003_shared_studies'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('notification_preferences', sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True), sa.Column('disabled_event_types', sa.JSON(), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table('notifications', sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('recipient_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False), sa.Column('actor_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL')), sa.Column('event_type', sa.String(50), nullable=False), sa.Column('target_type', sa.String(50), nullable=False), sa.Column('target_id', sa.String(100), nullable=False), sa.Column('message', sa.Text(), nullable=False), sa.Column('deduplication_key', sa.String(200), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column('read_at', sa.DateTime(timezone=True)))
    op.create_index('ux_notifications_recipient_dedup', 'notifications', ['recipient_id', 'deduplication_key'], unique=True)
    op.create_index('ix_notifications_recipient_read_created', 'notifications', ['recipient_id', 'read_at', 'created_at'])


def downgrade() -> None:
    op.drop_table('notifications'); op.drop_table('notification_preferences')
