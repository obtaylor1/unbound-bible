"""Create the legacy scripture compatibility table on fresh deployments.

The verified ingestion pipeline and read APIs intentionally share the small
six-column ``biblical_texts`` contract. Older SQLite databases already have
that table, while a new PostgreSQL database previously did not.
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_scripture_compatibility"
down_revision = "0012_research_control_values"
branch_labels = None
depends_on = None


TABLE_NAME = "biblical_texts"
INDEX_NAME = "uq_biblical_texts_translation_book_chapter_verse"
REQUIRED_COLUMNS = {"id", "book", "chapter", "verse", "text", "translation"}


def _identity_index() -> sa.Index:
    table = sa.Table(
        TABLE_NAME,
        sa.MetaData(),
        sa.Column("translation", sa.String(length=100)),
        sa.Column("book", sa.String(length=100)),
        sa.Column("chapter", sa.Integer()),
        sa.Column("verse", sa.Integer()),
    )
    return sa.Index(
        INDEX_NAME,
        sa.func.coalesce(table.c.translation, ""),
        table.c.book,
        table.c.chapter,
        table.c.verse,
        unique=True,
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table(TABLE_NAME):
        columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}
        missing = sorted(REQUIRED_COLUMNS - columns)
        if missing:
            raise RuntimeError(
                "Existing biblical_texts table is missing required columns: "
                + ", ".join(missing)
            )
        return

    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("book", sa.String(length=100), nullable=False),
        sa.Column("chapter", sa.Integer(), nullable=False),
        sa.Column("verse", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("translation", sa.String(length=100), nullable=True),
        sa.CheckConstraint("chapter > 0", name="ck_biblical_texts_chapter_positive"),
        sa.CheckConstraint("verse > 0", name="ck_biblical_texts_verse_positive"),
    )
    _identity_index().create(bind)


def downgrade() -> None:
    # Scripture content is user-visible library data. Keep the compatibility
    # table across a code rollback instead of destructively dropping it.
    pass
