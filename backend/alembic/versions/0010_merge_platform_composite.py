"""Merge platform-integrity and composite-edition migration branches."""


revision = '0010_merge_platform_composite'
down_revision = ('0006_platform_integrity', '0009_composite_edition_sources')
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Join the two independently developed migration branches."""


def downgrade() -> None:
    """Return to the two branch heads without altering either schema."""
