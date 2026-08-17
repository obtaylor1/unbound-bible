"""Create the frozen research-library catalog and immutable snapshot boundary."""

from alembic import op
import sqlalchemy as sa


revision = "0014_research_library_core"
down_revision = "0013_scripture_compatibility"
branch_labels = None
depends_on = None

TABLE_ORDER = (
    "research_work_profiles", "work_divisions", "source_editions",
    "source_edition_works", "license_records", "source_publications",
    "content_units", "citation_anchors", "research_chunks",
    "legacy_source_links", "legacy_content_links", "source_audit_events",
)
IMMUTABLE_TABLES = (
    "source_publications", "content_units", "citation_anchors",
    "research_chunks", "source_audit_events",
)
ACTIVE_POINTER_FK = "fk_source_editions_active_publication_same_edition"
POSTGRES_FUNCTION = "research_library_reject_immutable_dml"

CLASSIFICATIONS = (
    "'canonical_scripture', 'ethiopian_canon', 'deuterocanonical_scripture', "
    "'ancient_biblical_translation', 'ancient_jewish_literature', "
    "'dead_sea_scroll_manuscript', 'ancient_historical_source', "
    "'early_christian_writing', 'jewish_tradition', 'church_tradition', "
    "'archaeology', 'modern_scholarship'"
)


def _create_tables(dialect_name: str) -> None:
    op.create_table(
        "research_work_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.String(100), nullable=False),
        sa.Column("short_title", sa.String(200), nullable=True),
        sa.Column("short_description", sa.Text(), nullable=True),
        sa.Column("source_classification", sa.String(100), nullable=False),
        sa.Column("hierarchy_level", sa.String(100), nullable=False),
        sa.Column("traditions", sa.JSON(), nullable=False),
        sa.Column("canonical_statuses", sa.JSON(), nullable=False),
        sa.Column("original_languages", sa.JSON(), nullable=False),
        sa.Column("attributed_authorship", sa.Text(), nullable=True),
        sa.Column("date_era", sa.String(200), nullable=True),
        sa.Column("historical_classification", sa.String(100), nullable=True),
        sa.Column("literary_classification", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"source_classification IN ({CLASSIFICATIONS})", name="ck_research_work_profiles_source_classification"),
        sa.CheckConstraint("length(trim(hierarchy_level)) > 0", name="ck_research_work_profiles_hierarchy_level_nonblank"),
        sa.CheckConstraint("length(trim(source_classification)) > 0", name="ck_research_work_profiles_source_classification_nonblank"),
        sa.ForeignKeyConstraint(["work_id"], ["library_works.id"], name="fk_research_work_profiles_work_id_library_works", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_id", name="uq_research_work_profiles_work_id"),
    )
    op.create_table(
        "work_divisions",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("work_id", sa.String(100), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True), sa.Column("division_type", sa.String(32), nullable=False),
        sa.Column("label", sa.String(500), nullable=False), sa.Column("normalized_locator", sa.String(500), nullable=False),
        sa.Column("canonical_key", sa.String(500), nullable=False), sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("display_metadata", sa.JSON(), nullable=True),
        sa.CheckConstraint("division_type IN ('book', 'section', 'chapter', 'verse', 'paragraph', 'fragment', 'column', 'line')", name="ck_work_divisions_division_type"),
        sa.CheckConstraint("length(trim(canonical_key)) > 0", name="ck_work_divisions_key_nonblank"),
        sa.CheckConstraint("length(trim(normalized_locator)) > 0", name="ck_work_divisions_locator_nonblank"),
        sa.CheckConstraint("ordinal > 0", name="ck_work_divisions_ordinal_positive"),
        sa.ForeignKeyConstraint(["parent_id", "work_id"], ["work_divisions.id", "work_divisions.work_id"], name="fk_work_divisions_parent_same_work", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["work_id"], ["library_works.id"], name="fk_work_divisions_work_id_library_works", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("id", "work_id", name="uq_work_divisions_id_work"),
        sa.UniqueConstraint("work_id", "canonical_key", name="uq_work_divisions_work_key"),
        sa.UniqueConstraint("work_id", "normalized_locator", name="uq_work_divisions_work_locator"),
    )
    op.create_index("ix_work_divisions_parent_id", "work_divisions", ["parent_id"])
    op.create_index("ix_work_divisions_work_type", "work_divisions", ["work_id", "division_type"])
    op.create_index("uq_work_divisions_child_ordinal", "work_divisions", ["work_id", "parent_id", "ordinal"], unique=True, sqlite_where=sa.text("parent_id IS NOT NULL"), postgresql_where=sa.text("parent_id IS NOT NULL"))
    op.create_index("uq_work_divisions_root_ordinal", "work_divisions", ["work_id", "ordinal"], unique=True, sqlite_where=sa.text("parent_id IS NULL"), postgresql_where=sa.text("parent_id IS NULL"))
    active_pointer = sa.ForeignKeyConstraint(
        ["active_publication_id", "id"], ["source_publications.id", "source_publications.source_edition_id"],
        name=ACTIVE_POINTER_FK, ondelete="RESTRICT", use_alter=dialect_name == "postgresql",
    )
    op.create_table(
        "source_editions",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("active_publication_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(500), nullable=False), sa.Column("edition_label", sa.String(500), nullable=False),
        sa.Column("translator", sa.String(500), nullable=True), sa.Column("editor", sa.String(500), nullable=True),
        sa.Column("publisher", sa.String(500), nullable=True), sa.Column("publication_year", sa.Integer(), nullable=True),
        sa.Column("original_publication", sa.String(500), nullable=True), sa.Column("language", sa.String(64), nullable=False),
        sa.Column("script", sa.String(64), nullable=True), sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("acquisition_source", sa.String(500), nullable=True), sa.Column("checksum", sa.String(128), nullable=False),
        sa.Column("locator_scheme", sa.String(200), nullable=False), sa.Column("attribution", sa.Text(), nullable=True),
        sa.Column("verification_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(edition_label)) > 0", name="ck_source_editions_label_nonblank"),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_source_editions_title_nonblank"),
        sa.CheckConstraint("publication_year IS NULL OR publication_year > 0", name="ck_source_editions_publication_year_positive"),
        active_pointer, sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_editions_checksum", "source_editions", ["checksum"])
    op.create_index("ix_source_editions_language", "source_editions", ["language"])
    op.create_table(
        "source_edition_works",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("source_edition_id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.String(100), nullable=False), sa.Column("source_label", sa.String(500), nullable=False),
        sa.Column("locator_scheme", sa.String(200), nullable=True), sa.Column("attribution_override", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["source_edition_id"], ["source_editions.id"], name="fk_source_edition_works_edition_id_source_editions", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["work_id"], ["library_works.id"], name="fk_source_edition_works_work_id_library_works", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("source_edition_id", "work_id", name="uq_source_edition_works_edition_work"),
    )
    op.create_index("ix_source_edition_works_work_id", "source_edition_works", ["work_id"])
    op.create_table(
        "license_records",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("source_edition_id", sa.Uuid(), nullable=False),
        sa.Column("license_name", sa.String(500), nullable=False), sa.Column("license_url", sa.String(2048), nullable=True),
        sa.Column("is_public_domain", sa.Boolean(), nullable=True), sa.Column("commercial_use_allowed", sa.Boolean(), nullable=True),
        sa.Column("display_allowed", sa.Boolean(), nullable=True), sa.Column("redistribution_allowed", sa.Boolean(), nullable=True),
        sa.Column("modification_allowed", sa.Boolean(), nullable=True), sa.Column("attribution_required", sa.Boolean(), nullable=True),
        sa.Column("required_attribution_text", sa.Text(), nullable=True), sa.Column("source_text_rights", sa.Text(), nullable=True),
        sa.Column("translation_rights", sa.Text(), nullable=True), sa.Column("image_rights", sa.Text(), nullable=True),
        sa.Column("reviewed_source_urls", sa.JSON(), nullable=False), sa.Column("reviewer_id", sa.Uuid(), nullable=True),
        sa.Column("verification_date", sa.DateTime(timezone=True), nullable=True), sa.Column("explanatory_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(license_name)) > 0", name="ck_license_records_name_nonblank"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], name="fk_license_records_reviewer_id_users", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_edition_id"], ["source_editions.id"], name="fk_license_records_edition_id_source_editions", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("id", "source_edition_id", name="uq_license_records_id_edition"),
    )
    op.create_index("ix_license_records_source_edition_id", "license_records", ["source_edition_id"])
    op.create_index("ix_license_records_verification_date", "license_records", ["verification_date"])
    op.create_table(
        "source_publications",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("source_edition_id", sa.Uuid(), nullable=False),
        sa.Column("license_record_id", sa.Uuid(), nullable=True), sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("ingest_run_id", sa.Uuid(), nullable=True), sa.Column("status", sa.String(32), nullable=False),
        sa.Column("validation_approved", sa.Boolean(), nullable=False), sa.Column("public_visibility", sa.Boolean(), nullable=False),
        sa.Column("source_checksum", sa.String(128), nullable=False), sa.Column("content_checksum", sa.String(128), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("published_by_user_id", sa.Uuid(), nullable=True), sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("status IN ('needs_rights_review', 'importing', 'verified', 'active', 'disabled', 'restricted', 'internal_research_only')", name="ck_source_publications_status"),
        sa.CheckConstraint("version > 0", name="ck_source_publications_version_positive"),
        sa.ForeignKeyConstraint(["license_record_id", "source_edition_id"], ["license_records.id", "license_records.source_edition_id"], name="fk_source_publications_license_same_edition", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"], name="fk_source_publications_publisher_id_users", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], name="fk_source_publications_reviewer_id_users", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_edition_id"], ["source_editions.id"], name="fk_source_publications_edition_id_source_editions", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("id", "source_edition_id", name="uq_source_publications_id_edition"),
        sa.UniqueConstraint("source_edition_id", "version", name="uq_source_publications_edition_version"),
    )
    op.create_index("ix_source_publications_edition_status", "source_publications", ["source_edition_id", "status"])
    op.create_index("ix_source_publications_ingest_run_id", "source_publications", ["ingest_run_id"])
    op.create_index("ix_source_publications_license_record_id", "source_publications", ["license_record_id"])
    if dialect_name == "postgresql":
        op.create_foreign_key(ACTIVE_POINTER_FK, "source_editions", "source_publications", ["active_publication_id", "id"], ["id", "source_edition_id"], ondelete="RESTRICT")
    op.create_table(
        "content_units",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("source_publication_id", sa.Uuid(), nullable=False),
        sa.Column("source_edition_id", sa.Uuid(), nullable=False), sa.Column("work_id", sa.String(100), nullable=False),
        sa.Column("work_division_id", sa.Uuid(), nullable=False), sa.Column("language", sa.String(64), nullable=False),
        sa.Column("script", sa.String(64), nullable=True), sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False), sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("source_locator", sa.String(500), nullable=False), sa.Column("textual_certainty", sa.String(32), nullable=False),
        sa.Column("checksum", sa.String(128), nullable=False),
        sa.CheckConstraint("direction IN ('ltr', 'rtl', 'auto')", name="ck_content_units_direction"),
        sa.CheckConstraint("textual_certainty IN ('visible_text', 'reconstructed_text', 'supplied_text', 'translation', 'editorial_note')", name="ck_content_units_textual_certainty"),
        sa.CheckConstraint("length(trim(source_locator)) > 0", name="ck_content_units_locator_nonblank"),
        sa.CheckConstraint("ordinal > 0", name="ck_content_units_ordinal_positive"),
        sa.ForeignKeyConstraint(["source_edition_id", "work_id"], ["source_edition_works.source_edition_id", "source_edition_works.work_id"], name="fk_content_units_edition_covers_work", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_publication_id", "source_edition_id"], ["source_publications.id", "source_publications.source_edition_id"], name="fk_content_units_publication_same_edition", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["work_division_id", "work_id"], ["work_divisions.id", "work_divisions.work_id"], name="fk_content_units_division_same_work", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("id", "source_publication_id", "work_division_id", name="uq_content_units_id_publication_division"),
        sa.UniqueConstraint("source_publication_id", "work_division_id", "ordinal", name="uq_content_units_publication_division_ordinal"),
    )
    op.create_index("ix_content_units_division_id", "content_units", ["work_division_id"])
    op.create_index("ix_content_units_publication_checksum", "content_units", ["source_publication_id", "checksum"])
    op.create_index("ix_content_units_source_locator", "content_units", ["source_publication_id", "source_locator"])
    op.create_table(
        "citation_anchors",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("source_publication_id", sa.Uuid(), nullable=False),
        sa.Column("content_unit_id", sa.Uuid(), nullable=False), sa.Column("work_division_id", sa.Uuid(), nullable=False),
        sa.Column("anchor_key", sa.String(500), nullable=False), sa.Column("human_locator", sa.String(500), nullable=False),
        sa.Column("inspector_route", sa.String(2048), nullable=False), sa.Column("open_target", sa.JSON(), nullable=False),
        sa.CheckConstraint("length(trim(anchor_key)) > 0", name="ck_citation_anchors_key_nonblank"),
        sa.CheckConstraint("length(trim(human_locator)) > 0", name="ck_citation_anchors_locator_nonblank"),
        sa.ForeignKeyConstraint(["content_unit_id", "source_publication_id", "work_division_id"], ["content_units.id", "content_units.source_publication_id", "content_units.work_division_id"], name="fk_citation_anchors_content_same_scope", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("id", "source_publication_id", "work_division_id", name="uq_citation_anchors_id_publication_division"),
        sa.UniqueConstraint("source_publication_id", "anchor_key", name="uq_citation_anchors_publication_key"),
        sa.UniqueConstraint("source_publication_id", "content_unit_id", "human_locator", name="uq_citation_anchors_publication_unit_locator"),
    )
    op.create_index("ix_citation_anchors_content_unit_id", "citation_anchors", ["content_unit_id"])
    op.create_table(
        "research_chunks",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("source_edition_id", sa.Uuid(), nullable=False),
        sa.Column("source_publication_id", sa.Uuid(), nullable=False), sa.Column("work_id", sa.String(100), nullable=False),
        sa.Column("work_division_id", sa.Uuid(), nullable=False), sa.Column("citation_anchor_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False), sa.Column("boundary_type", sa.String(64), nullable=False),
        sa.Column("classification", sa.String(100), nullable=False), sa.Column("hierarchy_level", sa.String(100), nullable=False),
        sa.Column("language", sa.String(64), nullable=False), sa.Column("content_digest", sa.String(128), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=False), sa.Column("search_document", sa.Text(), nullable=True),
        sa.CheckConstraint(f"classification IN ({CLASSIFICATIONS})", name="ck_research_chunks_classification"),
        sa.CheckConstraint("length(trim(boundary_type)) > 0", name="ck_research_chunks_boundary_nonblank"),
        sa.CheckConstraint("ordinal > 0", name="ck_research_chunks_ordinal_positive"),
        sa.ForeignKeyConstraint(["citation_anchor_id", "source_publication_id", "work_division_id"], ["citation_anchors.id", "citation_anchors.source_publication_id", "citation_anchors.work_division_id"], name="fk_research_chunks_citation_same_scope", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_edition_id", "work_id"], ["source_edition_works.source_edition_id", "source_edition_works.work_id"], name="fk_research_chunks_edition_covers_work", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_publication_id", "source_edition_id"], ["source_publications.id", "source_publications.source_edition_id"], name="fk_research_chunks_publication_same_edition", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["work_division_id", "work_id"], ["work_divisions.id", "work_divisions.work_id"], name="fk_research_chunks_division_same_work", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("source_edition_id", "source_publication_id", "work_division_id", "boundary_type", "content_digest", name="uq_research_chunks_deduplication"),
        sa.UniqueConstraint("source_publication_id", "ordinal", name="uq_research_chunks_publication_ordinal"),
    )
    op.create_index("ix_research_chunks_citation_anchor_id", "research_chunks", ["citation_anchor_id"])
    op.create_index("ix_research_chunks_content_digest", "research_chunks", ["content_digest"])
    op.create_index("ix_research_chunks_work_division", "research_chunks", ["work_id", "work_division_id"])
    op.create_table(
        "legacy_source_links", sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("legacy_type", sa.String(200), nullable=False), sa.Column("legacy_key", sa.String(500), nullable=False),
        sa.Column("source_edition_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("length(trim(legacy_key)) > 0", name="ck_legacy_source_links_key_nonblank"),
        sa.CheckConstraint("length(trim(legacy_type)) > 0", name="ck_legacy_source_links_type_nonblank"),
        sa.ForeignKeyConstraint(["source_edition_id"], ["source_editions.id"], name="fk_legacy_source_links_edition_id_source_editions", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("legacy_type", "legacy_key", name="uq_legacy_source_links_type_key"),
    )
    op.create_index("ix_legacy_source_links_source_edition_id", "legacy_source_links", ["source_edition_id"])
    op.create_table(
        "legacy_content_links", sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("legacy_type", sa.String(200), nullable=False), sa.Column("legacy_key", sa.String(500), nullable=False),
        sa.Column("content_unit_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("length(trim(legacy_key)) > 0", name="ck_legacy_content_links_key_nonblank"),
        sa.CheckConstraint("length(trim(legacy_type)) > 0", name="ck_legacy_content_links_type_nonblank"),
        sa.ForeignKeyConstraint(["content_unit_id"], ["content_units.id"], name="fk_legacy_content_links_content_unit_id_content_units", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("legacy_type", "legacy_key", name="uq_legacy_content_links_type_key"),
    )
    op.create_index("ix_legacy_content_links_content_unit_id", "legacy_content_links", ["content_unit_id"])
    op.create_table(
        "source_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("source_edition_id", sa.Uuid(), nullable=True), sa.Column("source_publication_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(200), nullable=False), sa.Column("prior_state", sa.JSON(), nullable=True),
        sa.Column("resulting_state", sa.JSON(), nullable=False), sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("validation_run_id", sa.String(200), nullable=True), sa.Column("checksum_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(action)) > 0", name="ck_source_audit_events_action_nonblank"),
        sa.CheckConstraint("source_publication_id IS NULL OR source_edition_id IS NOT NULL", name="ck_source_audit_events_publication_requires_edition"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name="fk_source_audit_events_actor_id_users", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_edition_id"], ["source_editions.id"], name="fk_source_audit_events_edition_id_source_editions", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_publication_id", "source_edition_id"], ["source_publications.id", "source_publications.source_edition_id"], name="fk_source_audit_events_publication_same_edition", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_audit_events_actor_id", "source_audit_events", ["actor_id"])
    op.create_index("ix_source_audit_events_edition_created", "source_audit_events", ["source_edition_id", "created_at"])
    op.create_index("ix_source_audit_events_publication_created", "source_audit_events", ["source_publication_id", "created_at"])


def _sqlite_trigger_name(table_name: str, verb: str) -> str:
    return f"trg_rl_immutable_{table_name}_{verb.lower()}"


def _postgres_trigger_name(table_name: str) -> str:
    return f"trg_rl_immutable_{table_name}"


def _sqlite_create_triggers() -> None:
    for table_name in IMMUTABLE_TABLES:
        for verb in ("UPDATE", "DELETE"):
            op.execute(f'CREATE TRIGGER "{_sqlite_trigger_name(table_name, verb)}" BEFORE {verb} ON "{table_name}" BEGIN SELECT RAISE(ABORT, \'{table_name} records are immutable\'); END')


def _postgres_create_triggers() -> None:
    op.execute(f"CREATE FUNCTION {POSTGRES_FUNCTION}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION '% records are immutable', TG_TABLE_NAME USING ERRCODE = '55000'; END; $$")
    for table_name in IMMUTABLE_TABLES:
        op.execute(f'CREATE TRIGGER "{_postgres_trigger_name(table_name)}" BEFORE UPDATE OR DELETE ON "{table_name}" FOR EACH ROW EXECUTE FUNCTION {POSTGRES_FUNCTION}()')


def upgrade() -> None:
    dialect_name = op.get_bind().dialect.name
    _create_tables(dialect_name)
    if dialect_name == "postgresql":
        _postgres_create_triggers()
    elif dialect_name == "sqlite":
        _sqlite_create_triggers()
    else:
        raise RuntimeError(f"Unsupported research-library migration dialect: {dialect_name}")


def downgrade() -> None:
    dialect_name = op.get_bind().dialect.name
    if dialect_name == "postgresql":
        for table_name in IMMUTABLE_TABLES:
            op.execute(f'DROP TRIGGER IF EXISTS "{_postgres_trigger_name(table_name)}" ON "{table_name}"')
        op.execute(f"DROP FUNCTION IF EXISTS {POSTGRES_FUNCTION}()")
        op.drop_constraint(ACTIVE_POINTER_FK, "source_editions", type_="foreignkey")
    elif dialect_name == "sqlite":
        for table_name in IMMUTABLE_TABLES:
            for verb in ("UPDATE", "DELETE"):
                op.execute(f'DROP TRIGGER IF EXISTS "{_sqlite_trigger_name(table_name, verb)}"')
    else:
        raise RuntimeError(f"Unsupported research-library migration dialect: {dialect_name}")
    for table_name in reversed(TABLE_ORDER):
        op.drop_table(table_name)
