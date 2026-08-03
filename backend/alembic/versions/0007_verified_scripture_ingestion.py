"""Add verified scripture ingestion audit tables."""

from alembic import op
import sqlalchemy as sa


revision = '0007_verified_scripture_ingestion'
down_revision = '0006_ethiopian_library_foundation'
branch_labels = None
depends_on = None


LEGACY_TABLE = 'biblical_texts'
LEGACY_INDEX = 'uq_biblical_texts_translation_book_chapter_verse'


def _preflight_legacy_biblical_texts() -> bool:
    bind = op.get_bind()
    if LEGACY_TABLE not in sa.inspect(bind).get_table_names():
        return False

    duplicates = bind.execute(sa.text("""
        SELECT translation, book, chapter, verse, COUNT(*) AS duplicate_count
        FROM biblical_texts
        GROUP BY translation, book, chapter, verse
        HAVING COUNT(*) > 1
        ORDER BY translation, book, chapter, verse
        LIMIT 10
    """)).mappings().all()
    if duplicates:
        sample = '; '.join(
            f"({row['translation']!r}, {row['book']!r}, {row['chapter']}, {row['verse']}): "
            f"{row['duplicate_count']}"
            for row in duplicates
        )
        raise RuntimeError(
            'Cannot create the biblical_texts verse identity index because duplicate '
            f'(translation, book, chapter, verse) rows exist: {sample}'
        )
    return True


def upgrade() -> None:
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
        sa.ForeignKeyConstraint(['run_id'], ['scripture_ingest_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['previous_run_id'], ['scripture_ingest_runs.id'], ondelete='SET NULL'),
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
        op.create_index(
            LEGACY_INDEX,
            LEGACY_TABLE,
            ['translation', 'book', 'chapter', 'verse'],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if LEGACY_TABLE in inspector.get_table_names() and LEGACY_INDEX in {
        index['name'] for index in inspector.get_indexes(LEGACY_TABLE)
    }:
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
