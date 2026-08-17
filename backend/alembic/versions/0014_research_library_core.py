"""Create the research-library catalog and immutable snapshot boundary."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import AddConstraint, CreateIndex, CreateTable, DropTable

from app.database import Base
from app.research_library import models as research_library_models  # noqa: F401


revision = "0014_research_library_core"
down_revision = "0013_scripture_compatibility"
branch_labels = None
depends_on = None


TABLE_ORDER = (
    "research_work_profiles",
    "work_divisions",
    "source_editions",
    "source_edition_works",
    "license_records",
    "source_publications",
    "content_units",
    "citation_anchors",
    "research_chunks",
    "legacy_source_links",
    "legacy_content_links",
    "source_audit_events",
)
IMMUTABLE_TABLES = (
    "source_publications",
    "content_units",
    "citation_anchors",
    "research_chunks",
    "source_audit_events",
)
ACTIVE_POINTER_FK = "fk_source_editions_active_publication_same_edition"
POSTGRES_FUNCTION = "research_library_reject_immutable_dml"


def _table(name: str) -> sa.Table:
    return Base.metadata.tables[name]


def _active_pointer_constraint() -> sa.ForeignKeyConstraint:
    return next(
        constraint
        for constraint in _table("source_editions").constraints
        if constraint.name == ACTIVE_POINTER_FK
    )


def _sqlite_trigger_name(table_name: str, verb: str) -> str:
    return f"trg_rl_immutable_{table_name}_{verb.lower()}"


def _postgres_trigger_name(table_name: str) -> str:
    return f"trg_rl_immutable_{table_name}"


def _sqlite_create_triggers() -> None:
    for table_name in IMMUTABLE_TABLES:
        for verb in ("UPDATE", "DELETE"):
            op.execute(
                f'CREATE TRIGGER "{_sqlite_trigger_name(table_name, verb)}" '
                f'BEFORE {verb} ON "{table_name}" BEGIN '
                f"SELECT RAISE(ABORT, '{table_name} records are immutable'); END"
            )


def _sqlite_drop_triggers() -> None:
    for table_name in IMMUTABLE_TABLES:
        for verb in ("UPDATE", "DELETE"):
            op.execute(f'DROP TRIGGER IF EXISTS "{_sqlite_trigger_name(table_name, verb)}"')


def _postgres_create_triggers() -> None:
    op.execute(
        f"CREATE FUNCTION {POSTGRES_FUNCTION}() RETURNS trigger LANGUAGE plpgsql AS $$ "
        "BEGIN RAISE EXCEPTION '% records are immutable', TG_TABLE_NAME "
        "USING ERRCODE = '55000'; END; $$"
    )
    for table_name in IMMUTABLE_TABLES:
        op.execute(
            f'CREATE TRIGGER "{_postgres_trigger_name(table_name)}" '
            f'BEFORE UPDATE OR DELETE ON "{table_name}" FOR EACH ROW '
            f"EXECUTE FUNCTION {POSTGRES_FUNCTION}()"
        )


def _postgres_drop_triggers() -> None:
    for table_name in IMMUTABLE_TABLES:
        op.execute(
            f'DROP TRIGGER IF EXISTS "{_postgres_trigger_name(table_name)}" '
            f'ON "{table_name}"'
        )
    op.execute(f"DROP FUNCTION IF EXISTS {POSTGRES_FUNCTION}()")


def _postgresql_upgrade_sql() -> str:
    """Compile the PostgreSQL-specific path without requiring a live server."""
    dialect = postgresql.dialect()
    statements: list[str] = []
    for table_name in TABLE_ORDER:
        table = _table(table_name)
        statements.append(str(CreateTable(table).compile(dialect=dialect)))
        statements.extend(str(CreateIndex(index).compile(dialect=dialect)) for index in table.indexes)
    statements.append(str(AddConstraint(_active_pointer_constraint()).compile(dialect=dialect)))
    statements.append(
        f"CREATE FUNCTION {POSTGRES_FUNCTION}() RETURNS trigger LANGUAGE plpgsql AS $$ "
        "BEGIN RAISE EXCEPTION '% records are immutable', TG_TABLE_NAME; END; $$"
    )
    statements.extend(
        f'CREATE TRIGGER "{_postgres_trigger_name(table_name)}" BEFORE UPDATE OR DELETE '
        f'ON "{table_name}" FOR EACH ROW EXECUTE FUNCTION {POSTGRES_FUNCTION}()'
        for table_name in IMMUTABLE_TABLES
    )
    return ";\n".join(statements)


def _postgresql_downgrade_sql() -> str:
    dialect = postgresql.dialect()
    statements = [
        f'DROP TRIGGER IF EXISTS "{_postgres_trigger_name(table_name)}" ON "{table_name}"'
        for table_name in IMMUTABLE_TABLES
    ]
    statements.append(f"DROP FUNCTION IF EXISTS {POSTGRES_FUNCTION}()")
    statements.append(
        f'ALTER TABLE "source_editions" DROP CONSTRAINT "{ACTIVE_POINTER_FK}"'
    )
    statements.extend(
        str(DropTable(_table(table_name)).compile(dialect=dialect))
        for table_name in reversed(TABLE_ORDER)
    )
    return ";\n".join(statements)


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    for table_name in TABLE_ORDER:
        _table(table_name).create(bind)
    if dialect_name == "postgresql":
        op.create_foreign_key(
            ACTIVE_POINTER_FK,
            "source_editions",
            "source_publications",
            ["active_publication_id", "id"],
            ["id", "source_edition_id"],
            ondelete="RESTRICT",
        )
        _postgres_create_triggers()
    elif dialect_name == "sqlite":
        _sqlite_create_triggers()
    else:
        raise RuntimeError(f"Unsupported research-library migration dialect: {dialect_name}")


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    if dialect_name == "postgresql":
        _postgres_drop_triggers()
        op.drop_constraint(ACTIVE_POINTER_FK, "source_editions", type_="foreignkey")
    elif dialect_name == "sqlite":
        _sqlite_drop_triggers()
    else:
        raise RuntimeError(f"Unsupported research-library migration dialect: {dialect_name}")
    for table_name in reversed(TABLE_ORDER):
        _table(table_name).drop(bind)
