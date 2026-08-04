"""Add normalized commentary library tables."""

from alembic import op
import sqlalchemy as sa


revision = '0008_commentary_library'
down_revision = '0007_verified_ingest'
branch_labels = None
depends_on = None


def _create_entry_indexes(table_name: str, owner: str, reference_owner: str) -> None:
    op.create_index(
        f'uq_{table_name}_{owner}_identity',
        table_name,
        [
            owner,
            'work_id',
            sa.func.coalesce(sa.column('chapter'), -1),
            sa.func.coalesce(sa.column('verse_start'), -1),
            sa.func.coalesce(sa.column('verse_end'), -1),
            'entry_type',
            'position',
        ],
        unique=True,
    )
    op.create_index(
        f'ix_{table_name}_{reference_owner}_reference',
        table_name,
        [owner, 'work_id', 'chapter', 'verse_start', 'verse_end'],
    )
def upgrade() -> None:
    op.create_table(
        'commentary_sources',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('abbreviation', sa.String(length=16), nullable=False),
        sa.Column('author', sa.String(length=200), nullable=False),
        sa.Column('publication_period', sa.String(length=100), nullable=False),
        sa.Column('tradition', sa.String(length=120), nullable=False),
        sa.Column('language', sa.String(length=16), nullable=False, server_default='eng'),
        sa.Column('license_spdx', sa.String(length=64), nullable=False),
        sa.Column('license_url', sa.String(length=2048), nullable=False),
        sa.Column('attribution', sa.Text(), nullable=False),
        sa.Column('provenance_url', sa.String(length=2048), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'commentary_editions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('source_id', sa.String(length=64), nullable=False),
        sa.Column('dataset_version', sa.String(length=100), nullable=False),
        sa.Column('source_checksum', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='staged'),
        sa.Column('record_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('coverage', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('staged', 'verified', 'published', 'superseded', 'rejected')",
            name='ck_commentary_editions_status',
        ),
        sa.CheckConstraint('length(source_checksum) = 64', name='ck_commentary_editions_source_checksum_length'),
        sa.CheckConstraint('record_count >= 0', name='ck_commentary_editions_record_count_nonnegative'),
        sa.ForeignKeyConstraint(['source_id'], ['commentary_sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'source_id', name='uq_commentary_editions_id_source'),
        sa.UniqueConstraint('source_id', 'dataset_version', name='uq_commentary_editions_source_dataset_version'),
    )
    op.create_index('ix_commentary_editions_source_status', 'commentary_editions', ['source_id', 'status'])

    op.create_table(
        'commentary_import_runs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('source_id', sa.String(length=64), nullable=False),
        sa.Column('source_checksum', sa.String(length=64), nullable=False),
        sa.Column('metadata_snapshot', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='staged'),
        sa.Column('staged_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('warning_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('staged', 'validated', 'verified', 'published', 'failed', 'rolled_back')",
            name='ck_commentary_import_runs_status',
        ),
        sa.CheckConstraint(
            'length(source_checksum) = 64', name='ck_commentary_import_runs_source_checksum_length'
        ),
        sa.CheckConstraint('staged_count >= 0', name='ck_commentary_import_runs_staged_count_nonnegative'),
        sa.CheckConstraint('error_count >= 0', name='ck_commentary_import_runs_error_count_nonnegative'),
        sa.CheckConstraint('warning_count >= 0', name='ck_commentary_import_runs_warning_count_nonnegative'),
        sa.ForeignKeyConstraint(['source_id'], ['commentary_sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_commentary_import_runs_source_status', 'commentary_import_runs', ['source_id', 'status'])

    op.create_table(
        'commentary_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('edition_id', sa.Uuid(), nullable=False),
        sa.Column('work_id', sa.String(length=100), nullable=False),
        sa.Column('chapter', sa.Integer(), nullable=True),
        sa.Column('verse_start', sa.Integer(), nullable=True),
        sa.Column('verse_end', sa.Integer(), nullable=True),
        sa.Column('entry_type', sa.String(length=24), nullable=False),
        sa.Column('heading', sa.String(length=500), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('source_locator', sa.String(length=2048), nullable=False),
        sa.Column('row_checksum', sa.String(length=64), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.CheckConstraint("entry_type IN ('book_intro', 'chapter_intro', 'verse', 'verse_range')", name='ck_commentary_entries_entry_type'),
        sa.CheckConstraint('chapter IS NULL OR chapter > 0', name='ck_commentary_entries_chapter_positive'),
        sa.CheckConstraint('verse_start IS NULL OR verse_start > 0', name='ck_commentary_entries_verse_start_positive'),
        sa.CheckConstraint('verse_end IS NULL OR verse_end > 0', name='ck_commentary_entries_verse_end_positive'),
        sa.CheckConstraint('position >= 0', name='ck_commentary_entries_position_nonnegative'),
        sa.CheckConstraint('length(row_checksum) = 64', name='ck_commentary_entries_row_checksum_length'),
        sa.CheckConstraint("entry_type != 'book_intro' OR (chapter IS NULL AND verse_start IS NULL AND verse_end IS NULL)", name='ck_commentary_entries_book_intro_coordinates'),
        sa.CheckConstraint("entry_type != 'chapter_intro' OR (chapter IS NOT NULL AND verse_start IS NULL AND verse_end IS NULL)", name='ck_commentary_entries_chapter_intro_coordinates'),
        sa.CheckConstraint("entry_type NOT IN ('verse', 'verse_range') OR (chapter IS NOT NULL AND verse_start IS NOT NULL AND verse_end IS NOT NULL)", name='ck_commentary_entries_verse_coordinates'),
        sa.CheckConstraint("entry_type != 'verse' OR verse_start = verse_end", name='ck_commentary_entries_verse_single_coordinate'),
        sa.CheckConstraint('verse_start IS NULL OR verse_end IS NULL OR verse_end >= verse_start', name='ck_commentary_entries_verse_range_order'),
        sa.ForeignKeyConstraint(['edition_id'], ['commentary_editions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['work_id'], ['library_works.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    _create_entry_indexes('commentary_entries', 'edition_id', 'edition')

    op.create_table(
        'staged_commentary_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.Uuid(), nullable=False),
        sa.Column('work_id', sa.String(length=100), nullable=False),
        sa.Column('chapter', sa.Integer(), nullable=True),
        sa.Column('verse_start', sa.Integer(), nullable=True),
        sa.Column('verse_end', sa.Integer(), nullable=True),
        sa.Column('entry_type', sa.String(length=24), nullable=False),
        sa.Column('heading', sa.String(length=500), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('source_locator', sa.String(length=2048), nullable=False),
        sa.Column('row_checksum', sa.String(length=64), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.CheckConstraint("entry_type IN ('book_intro', 'chapter_intro', 'verse', 'verse_range')", name='ck_staged_commentary_entries_entry_type'),
        sa.CheckConstraint('chapter IS NULL OR chapter > 0', name='ck_staged_commentary_entries_chapter_positive'),
        sa.CheckConstraint('verse_start IS NULL OR verse_start > 0', name='ck_staged_commentary_entries_verse_start_positive'),
        sa.CheckConstraint('verse_end IS NULL OR verse_end > 0', name='ck_staged_commentary_entries_verse_end_positive'),
        sa.CheckConstraint('position >= 0', name='ck_staged_commentary_entries_position_nonnegative'),
        sa.CheckConstraint('length(row_checksum) = 64', name='ck_staged_commentary_entries_row_checksum_length'),
        sa.CheckConstraint("entry_type != 'book_intro' OR (chapter IS NULL AND verse_start IS NULL AND verse_end IS NULL)", name='ck_staged_commentary_entries_book_intro_coordinates'),
        sa.CheckConstraint("entry_type != 'chapter_intro' OR (chapter IS NOT NULL AND verse_start IS NULL AND verse_end IS NULL)", name='ck_staged_commentary_entries_chapter_intro_coordinates'),
        sa.CheckConstraint("entry_type NOT IN ('verse', 'verse_range') OR (chapter IS NOT NULL AND verse_start IS NOT NULL AND verse_end IS NOT NULL)", name='ck_staged_commentary_entries_verse_coordinates'),
        sa.CheckConstraint("entry_type != 'verse' OR verse_start = verse_end", name='ck_staged_commentary_entries_verse_single_coordinate'),
        sa.CheckConstraint('verse_start IS NULL OR verse_end IS NULL OR verse_end >= verse_start', name='ck_staged_commentary_entries_verse_range_order'),
        sa.ForeignKeyConstraint(['run_id'], ['commentary_import_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['work_id'], ['library_works.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    _create_entry_indexes('staged_commentary_entries', 'run_id', 'run')

    op.create_table(
        'commentary_validation_findings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.Uuid(), nullable=False),
        sa.Column('severity', sa.String(length=7), nullable=False),
        sa.Column('code', sa.String(length=100), nullable=False),
        sa.Column('work_id', sa.String(length=100), nullable=True),
        sa.Column('chapter', sa.Integer(), nullable=True),
        sa.Column('verse', sa.Integer(), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("severity IN ('error', 'warning')", name='ck_commentary_validation_findings_severity'),
        sa.CheckConstraint('chapter IS NULL OR chapter > 0', name='ck_commentary_validation_findings_chapter_positive'),
        sa.CheckConstraint('verse IS NULL OR verse > 0', name='ck_commentary_validation_findings_verse_positive'),
        sa.ForeignKeyConstraint(['run_id'], ['commentary_import_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['work_id'], ['library_works.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_commentary_validation_findings_run_severity', 'commentary_validation_findings', ['run_id', 'severity'])

    op.create_table(
        'commentary_publications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.String(length=64), nullable=False),
        sa.Column('edition_id', sa.Uuid(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('active', sa.Boolean(create_constraint=True), nullable=False, server_default='1'),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('version > 0', name='ck_commentary_publications_version_positive'),
        sa.ForeignKeyConstraint(['source_id'], ['commentary_sources.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['edition_id', 'source_id'],
            ['commentary_editions.id', 'commentary_editions.source_id'],
            name='fk_commentary_publications_edition_source',
            ondelete='NO ACTION',
            deferrable=True,
            initially='DEFERRED',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_id', 'version', name='uq_commentary_publications_source_version'),
    )
    op.create_index(
        'uq_commentary_publications_active_source',
        'commentary_publications',
        ['source_id'],
        unique=True,
        sqlite_where=sa.column('active').is_(True),
        postgresql_where=sa.column('active').is_(True),
    )
    op.create_index('ix_commentary_publications_active', 'commentary_publications', ['active'])


def downgrade() -> None:
    op.drop_index('ix_commentary_publications_active', table_name='commentary_publications')
    op.drop_index('uq_commentary_publications_active_source', table_name='commentary_publications')
    op.drop_table('commentary_publications')
    op.drop_index('ix_commentary_validation_findings_run_severity', table_name='commentary_validation_findings')
    op.drop_table('commentary_validation_findings')
    op.drop_index('ix_staged_commentary_entries_run_reference', table_name='staged_commentary_entries')
    op.drop_index('uq_staged_commentary_entries_run_id_identity', table_name='staged_commentary_entries')
    op.drop_table('staged_commentary_entries')
    op.drop_index('ix_commentary_entries_edition_reference', table_name='commentary_entries')
    op.drop_index('uq_commentary_entries_edition_id_identity', table_name='commentary_entries')
    op.drop_table('commentary_entries')
    op.drop_index('ix_commentary_import_runs_source_status', table_name='commentary_import_runs')
    op.drop_table('commentary_import_runs')
    op.drop_index('ix_commentary_editions_source_status', table_name='commentary_editions')
    op.drop_table('commentary_editions')
    op.drop_table('commentary_sources')
