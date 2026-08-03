"""Create scripture library metadata tables."""

from alembic import op
import sqlalchemy as sa


revision = '0006_ethiopian_library_foundation'
down_revision = '0005_community_migration'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'library_works',
        sa.Column('id', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'canon_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('canon_code', sa.String(length=64), nullable=False),
        sa.Column('testament', sa.String(length=8), nullable=False),
        sa.Column('canonical_order', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'canon_code',
            'testament',
            'canonical_order',
            name='uq_canon_entries_canon_testament_order',
        ),
    )
    op.create_table(
        'text_editions',
        sa.Column('edition_code', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('reading_language', sa.String(length=64), nullable=False),
        sa.Column('source_language', sa.String(length=64), nullable=False),
        sa.Column('script', sa.String(length=64), nullable=False),
        sa.Column('translator', sa.String(length=200), nullable=True),
        sa.Column('publisher', sa.String(length=200), nullable=True),
        sa.Column('published_year', sa.Integer(), nullable=True),
        sa.Column('license_spdx', sa.String(length=100), nullable=True),
        sa.Column('attribution', sa.Text(), nullable=True),
        sa.Column('provenance_url', sa.String(length=2048), nullable=True),
        sa.Column('source_tradition', sa.String(length=200), nullable=True),
        sa.Column('relationship', sa.String(length=32), nullable=False),
        sa.Column('versification', sa.String(length=100), nullable=True),
        sa.Column('expected_coverage', sa.JSON(), nullable=False),
        sa.Column('verification_status', sa.String(length=16), nullable=False),
        sa.Column('source_checksum', sa.String(length=128), nullable=True),
        sa.CheckConstraint(
            "relationship IN ('exact_ethiopian', 'related_recension', 'general_reading')",
            name='ck_text_editions_relationship',
        ),
        sa.CheckConstraint(
            "verification_status IN ('queued', 'staged', 'verified', 'withdrawn')",
            name='ck_text_editions_verification_status',
        ),
        sa.PrimaryKeyConstraint('edition_code'),
    )
    op.create_table(
        'library_work_aliases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alias', sa.String(length=200), nullable=False),
        sa.Column('work_id', sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(['work_id'], ['library_works.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('alias'),
    )
    op.create_index('ix_library_work_aliases_work_id', 'library_work_aliases', ['work_id'])
    op.create_table(
        'canon_entry_works',
        sa.Column('canon_entry_id', sa.Integer(), nullable=False),
        sa.Column('work_id', sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(['canon_entry_id'], ['canon_entries.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['work_id'], ['library_works.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('canon_entry_id', 'work_id'),
    )
    op.create_index('ix_canon_entry_works_work_id', 'canon_entry_works', ['work_id'])
    op.create_table(
        'edition_coverage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('edition_code', sa.String(length=100), nullable=False),
        sa.Column('work_id', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('chapter_count', sa.Integer(), nullable=True),
        sa.Column('verse_count', sa.Integer(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('verified_english', 'verified_original', 'related_recension', 'translation_needed')",
            name='ck_edition_coverage_status',
        ),
        sa.ForeignKeyConstraint(['edition_code'], ['text_editions.edition_code'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['work_id'], ['library_works.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('edition_code', 'work_id', name='uq_edition_coverage_edition_work'),
    )
    op.create_index('ix_edition_coverage_work_id', 'edition_coverage', ['work_id'])
    op.create_index('ix_text_editions_verification_status', 'text_editions', ['verification_status'])


def downgrade() -> None:
    op.drop_index('ix_edition_coverage_work_id', table_name='edition_coverage')
    op.drop_table('edition_coverage')
    op.drop_index('ix_canon_entry_works_work_id', table_name='canon_entry_works')
    op.drop_table('canon_entry_works')
    op.drop_index('ix_library_work_aliases_work_id', table_name='library_work_aliases')
    op.drop_table('library_work_aliases')
    op.drop_index('ix_text_editions_verification_status', table_name='text_editions')
    op.drop_table('text_editions')
    op.drop_table('canon_entries')
    op.drop_table('library_works')
