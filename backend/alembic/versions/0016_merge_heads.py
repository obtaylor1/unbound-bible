"""Join the scripture-verification and research-library migration branches."""

revision = "0016_merge_heads"
down_revision = (
    "0011_scripture_work_verification",
    "0015_administrator_role",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Both parent branches contain the required schema changes."""


def downgrade() -> None:
    """Downgrading the merge point leaves both parent branches installed."""
