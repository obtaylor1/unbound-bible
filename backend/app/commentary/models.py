from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    column,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


ENTRY_TYPES = "'book_intro', 'chapter_intro', 'verse', 'verse_range'"


def _entry_constraints(table: str, owner: str) -> tuple:
    return (
        CheckConstraint(
            f"entry_type IN ({ENTRY_TYPES})", name=f'ck_{table}_entry_type',
        ),
        CheckConstraint(
            'chapter IS NULL OR chapter > 0', name=f'ck_{table}_chapter_positive',
        ),
        CheckConstraint(
            'verse_start IS NULL OR verse_start > 0', name=f'ck_{table}_verse_start_positive',
        ),
        CheckConstraint(
            'verse_end IS NULL OR verse_end > 0', name=f'ck_{table}_verse_end_positive',
        ),
        CheckConstraint(
            'position >= 0', name=f'ck_{table}_position_nonnegative',
        ),
        CheckConstraint(
            'length(row_checksum) = 64', name=f'ck_{table}_row_checksum_length',
        ),
        CheckConstraint(
            "entry_type != 'book_intro' OR "
            '(chapter IS NULL AND verse_start IS NULL AND verse_end IS NULL)',
            name=f'ck_{table}_book_intro_coordinates',
        ),
        CheckConstraint(
            "entry_type != 'chapter_intro' OR "
            '(chapter IS NOT NULL AND verse_start IS NULL AND verse_end IS NULL)',
            name=f'ck_{table}_chapter_intro_coordinates',
        ),
        CheckConstraint(
            "entry_type NOT IN ('verse', 'verse_range') OR "
            '(chapter IS NOT NULL AND verse_start IS NOT NULL AND verse_end IS NOT NULL)',
            name=f'ck_{table}_verse_coordinates',
        ),
        CheckConstraint(
            "entry_type != 'verse' OR verse_start = verse_end",
            name=f'ck_{table}_verse_single_coordinate',
        ),
        CheckConstraint(
            'verse_start IS NULL OR verse_end IS NULL OR verse_end >= verse_start',
            name=f'ck_{table}_verse_range_order',
        ),
        Index(
            f'uq_{table}_{owner}_identity',
            owner,
            'work_id',
            func.coalesce(column('chapter'), -1),
            func.coalesce(column('verse_start'), -1),
            func.coalesce(column('verse_end'), -1),
            'entry_type',
            'position',
            unique=True,
        ),
    )


class CommentarySource(Base):
    __tablename__ = 'commentary_sources'

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    abbreviation: Mapped[str] = mapped_column(String(16), nullable=False)
    author: Mapped[str] = mapped_column(String(200), nullable=False)
    publication_period: Mapped[str] = mapped_column(String(100), nullable=False)
    tradition: Mapped[str] = mapped_column(String(120), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default='eng', server_default='eng')
    license_spdx: Mapped[str] = mapped_column(String(64), nullable=False)
    license_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    attribution: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_url: Mapped[str] = mapped_column(String(2048), nullable=False)


class CommentaryEdition(Base):
    __tablename__ = 'commentary_editions'
    __table_args__ = (
        UniqueConstraint('source_id', 'dataset_version', name='uq_commentary_editions_source_dataset_version'),
        CheckConstraint(
            "status IN ('staged', 'verified', 'published', 'superseded', 'rejected')",
            name='ck_commentary_editions_status',
        ),
        CheckConstraint('length(source_checksum) = 64', name='ck_commentary_editions_source_checksum_length'),
        CheckConstraint('record_count >= 0', name='ck_commentary_editions_record_count_nonnegative'),
        Index('ix_commentary_editions_source_status', 'source_id', 'status'),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_id: Mapped[str] = mapped_column(
        ForeignKey('commentary_sources.id', ondelete='CASCADE'), nullable=False
    )
    dataset_version: Mapped[str] = mapped_column(String(100), nullable=False)
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='staged', server_default='staged')
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    coverage: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default='{}')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CommentaryEntry(Base):
    __tablename__ = 'commentary_entries'
    __table_args__ = (
        *_entry_constraints('commentary_entries', 'edition_id'),
        Index(
            'ix_commentary_entries_edition_reference',
            'edition_id', 'work_id', 'chapter', 'verse_start', 'verse_end',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    edition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('commentary_editions.id', ondelete='CASCADE'), nullable=False
    )
    work_id: Mapped[str] = mapped_column(ForeignKey('library_works.id', ondelete='CASCADE'), nullable=False)
    chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verse_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verse_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entry_type: Mapped[str] = mapped_column(String(24), nullable=False)
    heading: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source_locator: Mapped[str] = mapped_column(String(2048), nullable=False)
    row_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')


class CommentaryImportRun(Base):
    __tablename__ = 'commentary_import_runs'
    __table_args__ = (
        CheckConstraint(
            "status IN ('staged', 'validated', 'verified', 'published', 'failed', 'rolled_back')",
            name='ck_commentary_import_runs_status',
        ),
        CheckConstraint(
            'length(source_checksum) = 64', name='ck_commentary_import_runs_source_checksum_length'
        ),
        CheckConstraint('staged_count >= 0', name='ck_commentary_import_runs_staged_count_nonnegative'),
        CheckConstraint('error_count >= 0', name='ck_commentary_import_runs_error_count_nonnegative'),
        CheckConstraint('warning_count >= 0', name='ck_commentary_import_runs_warning_count_nonnegative'),
        Index('ix_commentary_import_runs_source_status', 'source_id', 'status'),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_id: Mapped[str] = mapped_column(
        ForeignKey('commentary_sources.id', ondelete='CASCADE'), nullable=False
    )
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='staged', server_default='staged')
    staged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class StagedCommentaryEntry(Base):
    __tablename__ = 'staged_commentary_entries'
    __table_args__ = (
        *_entry_constraints('staged_commentary_entries', 'run_id'),
        Index(
            'ix_staged_commentary_entries_run_reference',
            'run_id', 'work_id', 'chapter', 'verse_start', 'verse_end',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('commentary_import_runs.id', ondelete='CASCADE'), nullable=False
    )
    work_id: Mapped[str] = mapped_column(ForeignKey('library_works.id', ondelete='CASCADE'), nullable=False)
    chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verse_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verse_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entry_type: Mapped[str] = mapped_column(String(24), nullable=False)
    heading: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source_locator: Mapped[str] = mapped_column(String(2048), nullable=False)
    row_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')


class CommentaryValidationFinding(Base):
    __tablename__ = 'commentary_validation_findings'
    __table_args__ = (
        CheckConstraint("severity IN ('error', 'warning')", name='ck_commentary_validation_findings_severity'),
        CheckConstraint(
            'chapter IS NULL OR chapter > 0', name='ck_commentary_validation_findings_chapter_positive'
        ),
        CheckConstraint(
            'verse IS NULL OR verse > 0', name='ck_commentary_validation_findings_verse_positive'
        ),
        Index('ix_commentary_validation_findings_run_severity', 'run_id', 'severity'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('commentary_import_runs.id', ondelete='CASCADE'), nullable=False
    )
    severity: Mapped[str] = mapped_column(String(7), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    work_id: Mapped[str | None] = mapped_column(
        ForeignKey('library_works.id', ondelete='SET NULL'), nullable=True
    )
    chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verse: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CommentaryPublication(Base):
    __tablename__ = 'commentary_publications'
    __table_args__ = (
        UniqueConstraint('source_id', 'version', name='uq_commentary_publications_source_version'),
        CheckConstraint('version > 0', name='ck_commentary_publications_version_positive'),
        Index(
            'uq_commentary_publications_active_source',
            'source_id',
            unique=True,
            sqlite_where=column('active').is_(True),
            postgresql_where=column('active').is_(True),
        ),
        Index('ix_commentary_publications_active', 'active'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey('commentary_sources.id', ondelete='CASCADE'), nullable=False
    )
    edition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('commentary_editions.id', ondelete='RESTRICT'), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True), nullable=False, default=True, server_default='1'
    )
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
