"""Create private notes and durable study sessions."""

from alembic import op
import sqlalchemy as sa

revision = "0002_studies_and_notes"
down_revision = "0001_unified_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("user_notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("passage_reference", sa.String(100)), sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_user_notes_owner_updated", "user_notes", ["owner_id", "updated_at"])
    op.create_table("study_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_study_sessions_owner_updated", "study_sessions", ["owner_id", "updated_at"])
    op.create_table("study_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("study_id", sa.Uuid(), sa.ForeignKey("study_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False), sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_study_messages_study_id", "study_messages", ["study_id"])
    op.create_table("study_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("study_id", sa.Uuid(), sa.ForeignKey("study_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False), sa.Column("url", sa.String(2048)), sa.Column("citation", sa.Text()))
    op.create_index("ix_study_sources_study_id", "study_sources", ["study_id"])


def downgrade() -> None:
    op.drop_table("study_sources")
    op.drop_table("study_messages")
    op.drop_table("study_sessions")
    op.drop_table("user_notes")
