"""Add verified scripture ingestion audit tables."""

from alembic import context, op
import sqlalchemy as sa


revision = '0007_verified_ingest'
down_revision = '0006_ethiopian_library'
branch_labels = None
depends_on = None


LEGACY_TABLE = 'biblical_texts'
LEGACY_INDEX = 'uq_biblical_texts_translation_book_chapter_verse'
OFFLINE_REFUSAL = (
    'Offline migration refused for 0007_verified_ingest. Run Alembic online without --sql '
    'so the migration can inspect biblical_texts, preflight duplicate verse identities, and '
    'conditionally manage the functional unique index.'
)


def _require_online_migration() -> None:
    if context.is_offline_mode():
        raise RuntimeError(OFFLINE_REFUSAL)


def _legacy_identity_index() -> sa.Index:
    legacy_table = sa.Table(
        LEGACY_TABLE,
        sa.MetaData(),
        sa.Column('translation', sa.String()),
        sa.Column('book', sa.String()),
        sa.Column('chapter', sa.Integer()),
        sa.Column('verse', sa.Integer()),
    )
    return sa.Index(
        LEGACY_INDEX,
        sa.func.coalesce(legacy_table.c.translation, ''),
        legacy_table.c.book,
        legacy_table.c.chapter,
        legacy_table.c.verse,
        unique=True,
    )


def _preflight_legacy_biblical_texts() -> bool:
    bind = op.get_bind()
    if LEGACY_TABLE not in sa.inspect(bind).get_table_names():
        return False

    duplicates = bind.execute(sa.text("""
        SELECT COALESCE(translation, '') AS translation_identity,
               book, chapter, verse, COUNT(*) AS duplicate_count
        FROM biblical_texts
        GROUP BY COALESCE(translation, ''), book, chapter, verse
        HAVING COUNT(*) > 1
        ORDER BY COALESCE(translation, ''), book, chapter, verse
        LIMIT 10
    """)).mappings().all()
    if duplicates:
        sample = '; '.join(
            f"({row['translation_identity']!r}, {row['book']!r}, {row['chapter']}, {row['verse']}): "
            f"{row['duplicate_count']}"
            for row in duplicates
        )
        raise RuntimeError(
            'Cannot create the biblical_texts verse identity index because duplicate '
            f'(translation, book, chapter, verse) rows exist: {sample}'
        )
    return True


def _legacy_index_exists(bind) -> bool:
    if bind.dialect.name == 'sqlite':
        return bool(bind.scalar(sa.text(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = :index_name"
        ), {'index_name': LEGACY_INDEX}))
    if bind.dialect.name == 'postgresql':
        return bool(bind.scalar(sa.text("""
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND tablename = :table_name
              AND indexname = :index_name
        """), {'table_name': LEGACY_TABLE, 'index_name': LEGACY_INDEX}))
    return LEGACY_INDEX in {
        index['name'] for index in sa.inspect(bind).get_indexes(LEGACY_TABLE)
    }


def upgrade() -> None:
    _require_online_migration()
    # Preflight before creating any new tables so duplicate legacy data leaves this migration untouched.
    legacy_table_present = _preflight_legacy_biblical_texts()

    op.create_table(
        'scripture_ingest_runs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('edition_code', sa.String(length=100), nullable=False),
        sa.Column('source_checksum', sa.String(length=64), nullable=False),
        sa.Column('manifest_snapshot', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('staged_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('warning_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('published_count', sa.Integer(), nullable=False, server_default='0'),
        sa.CheckConstraint(
            "status IN ('staged', 'validated', 'verified', 'published', 'failed', 'rolled_back')",
            name='ck_scripture_ingest_runs_status',
        ),
        sa.CheckConstraint('length(source_checksum) = 64', name='ck_scripture_ingest_runs_source_checksum_length'),
        sa.CheckConstraint('staged_count >= 0', name='ck_scripture_ingest_runs_staged_count_nonnegative'),
        sa.CheckConstraint('error_count >= 0', name='ck_scripture_ingest_runs_error_count_nonnegative'),
        sa.CheckConstraint('warning_count >= 0', name='ck_scripture_ingest_runs_warning_count_nonnegative'),
        sa.CheckConstraint('published_count >= 0', name='ck_scripture_ingest_runs_published_count_nonnegative'),
        sa.ForeignKeyConstraint(['edition_code'], ['text_editions.edition_code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'edition_code', name='uq_scripture_ingest_runs_id_edition'),
    )
    op.create_index('ix_scripture_ingest_runs_edition_status', 'scripture_ingest_runs', ['edition_code', 'status'])

    op.create_table(
        'staged_scripture_verses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.Uuid(), nullable=False),
        sa.Column('work_id', sa.String(length=100), nullable=False),
        sa.Column('source_book', sa.String(length=100), nullable=False),
        sa.Column('chapter', sa.Integer(), nullable=False),
        sa.Column('verse', sa.Integer(), nullable=False),
        sa.Column('normalized_text', sa.Text(), nullable=False),
        sa.Column('source_locator', sa.String(length=2048), nullable=False),
        sa.Column('row_checksum', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('chapter > 0', name='ck_staged_scripture_verses_chapter_positive'),
        sa.CheckConstraint('verse > 0', name='ck_staged_scripture_verses_verse_positive'),
        sa.CheckConstraint('length(row_checksum) = 64', name='ck_staged_scripture_verses_row_checksum_length'),
        sa.ForeignKeyConstraint(['run_id'], ['scripture_ingest_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['work_id'], ['library_works.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_id', 'work_id', 'chapter', 'verse', name='uq_staged_scripture_verses_run_work_chapter_verse'),
    )
    op.create_index('ix_staged_scripture_verses_run_id', 'staged_scripture_verses', ['run_id'])
    op.create_index('ix_staged_scripture_verses_work_id', 'staged_scripture_verses', ['work_id'])
    op.create_index('ix_staged_scripture_verses_row_checksum', 'staged_scripture_verses', ['row_checksum'])

    op.create_table(
        'scripture_validation_findings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.Uuid(), nullable=False),
        sa.Column('severity', sa.String(length=7), nullable=False),
        sa.Column('code', sa.String(length=100), nullable=False),
        sa.Column('work_id', sa.String(length=100), nullable=True),
        sa.Column('chapter', sa.Integer(), nullable=True),
        sa.Column('verse', sa.Integer(), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("severity IN ('error', 'warning')", name='ck_scripture_validation_findings_severity'),
        sa.CheckConstraint('chapter IS NULL OR chapter > 0', name='ck_scripture_validation_findings_chapter_positive'),
        sa.CheckConstraint('verse IS NULL OR verse > 0', name='ck_scripture_validation_findings_verse_positive'),
        sa.ForeignKeyConstraint(['run_id'], ['scripture_ingest_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['work_id'], ['library_works.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_scripture_validation_findings_run_severity', 'scripture_validation_findings', ['run_id', 'severity'])
    op.create_index('ix_scripture_validation_findings_code', 'scripture_validation_findings', ['code'])
    op.create_index('ix_scripture_validation_findings_work_position', 'scripture_validation_findings', ['work_id', 'chapter', 'verse'])

    op.create_table(
        'scripture_publications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('edition_code', sa.String(length=100), nullable=False),
        sa.Column('run_id', sa.Uuid(), nullable=False),
        sa.Column('previous_run_id', sa.Uuid(), nullable=True),
        sa.Column('publication_version', sa.Integer(), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('active', sa.Boolean(create_constraint=True), nullable=False, server_default='1'),
        sa.CheckConstraint('publication_version > 0', name='ck_scripture_publications_version_positive'),
        sa.ForeignKeyConstraint(['edition_code'], ['text_editions.edition_code'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['run_id', 'edition_code'],
            ['scripture_ingest_runs.id', 'scripture_ingest_runs.edition_code'],
            name='fk_scripture_publications_run_edition',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['previous_run_id', 'edition_code'],
            ['scripture_ingest_runs.id', 'scripture_ingest_runs.edition_code'],
            name='fk_scripture_publications_previous_run_edition',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('edition_code', 'publication_version', name='uq_scripture_publications_edition_version'),
    )
    op.create_index(
        'uq_scripture_publications_active_edition',
        'scripture_publications',
        ['edition_code'],
        unique=True,
        sqlite_where=sa.column('active').is_(True),
        postgresql_where=sa.column('active').is_(True),
    )

    if legacy_table_present:
        legacy_index = _legacy_identity_index()
        op.create_index(
            legacy_index.name,
            LEGACY_TABLE,
            legacy_index.expressions,
            unique=True,
        )


def downgrade() -> None:
    _require_online_migration()
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if LEGACY_TABLE in inspector.get_table_names() and _legacy_index_exists(bind):
        op.drop_index(LEGACY_INDEX, table_name=LEGACY_TABLE)

    op.drop_index('uq_scripture_publications_active_edition', table_name='scripture_publications')
    op.drop_table('scripture_publications')
    op.drop_index('ix_scripture_validation_findings_work_position', table_name='scripture_validation_findings')
    op.drop_index('ix_scripture_validation_findings_code', table_name='scripture_validation_findings')
    op.drop_index('ix_scripture_validation_findings_run_severity', table_name='scripture_validation_findings')
    op.drop_table('scripture_validation_findings')
    op.drop_index('ix_staged_scripture_verses_row_checksum', table_name='staged_scripture_verses')
    op.drop_index('ix_staged_scripture_verses_work_id', table_name='staged_scripture_verses')
    op.drop_index('ix_staged_scripture_verses_run_id', table_name='staged_scripture_verses')
    op.drop_table('staged_scripture_verses')
    op.drop_index('ix_scripture_ingest_runs_edition_status', table_name='scripture_ingest_runs')
    op.drop_table('scripture_ingest_runs')
