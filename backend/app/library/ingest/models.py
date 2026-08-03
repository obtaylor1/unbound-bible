from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
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


class ScriptureIngestRun(Base):
    __tablename__ = 'scripture_ingest_runs'
    __table_args__ = (
        CheckConstraint(
            "status IN ('staged', 'validated', 'verified', 'published', 'failed', 'rolled_back')",
            name='ck_scripture_ingest_runs_status',
        ),
        CheckConstraint('length(source_checksum) = 64', name='ck_scripture_ingest_runs_source_checksum_length'),
        CheckConstraint('staged_count >= 0', name='ck_scripture_ingest_runs_staged_count_nonnegative'),
        CheckConstraint('error_count >= 0', name='ck_scripture_ingest_runs_error_count_nonnegative'),
        CheckConstraint('warning_count >= 0', name='ck_scripture_ingest_runs_warning_count_nonnegative'),
        CheckConstraint('published_count >= 0', name='ck_scripture_ingest_runs_published_count_nonnegative'),
        UniqueConstraint('id', 'edition_code', name='uq_scripture_ingest_runs_id_edition'),
        Index('ix_scripture_ingest_runs_edition_status', 'edition_code', 'status'),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    edition_code: Mapped[str] = mapped_column(
        ForeignKey('text_editions.edition_code', ondelete='CASCADE'), nullable=False
    )
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='staged')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    staged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    published_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')


class StagedScriptureVerse(Base):
    __tablename__ = 'staged_scripture_verses'
    __table_args__ = (
        UniqueConstraint('run_id', 'work_id', 'chapter', 'verse', name='uq_staged_scripture_verses_run_work_chapter_verse'),
        CheckConstraint('chapter > 0', name='ck_staged_scripture_verses_chapter_positive'),
        CheckConstraint('verse > 0', name='ck_staged_scripture_verses_verse_positive'),
        CheckConstraint('length(row_checksum) = 64', name='ck_staged_scripture_verses_row_checksum_length'),
        Index('ix_staged_scripture_verses_run_id', 'run_id'),
        Index('ix_staged_scripture_verses_work_id', 'work_id'),
        Index('ix_staged_scripture_verses_row_checksum', 'row_checksum'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('scripture_ingest_runs.id', ondelete='CASCADE'), nullable=False
    )
    work_id: Mapped[str] = mapped_column(
        ForeignKey('library_works.id', ondelete='CASCADE'), nullable=False
    )
    source_book: Mapped[str] = mapped_column(String(100), nullable=False)
    chapter: Mapped[int] = mapped_column(Integer, nullable=False)
    verse: Mapped[int] = mapped_column(Integer, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_locator: Mapped[str] = mapped_column(String(2048), nullable=False)
    row_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ScriptureValidationFinding(Base):
    __tablename__ = 'scripture_validation_findings'
    __table_args__ = (
        CheckConstraint("severity IN ('error', 'warning')", name='ck_scripture_validation_findings_severity'),
        CheckConstraint(
            'chapter IS NULL OR chapter > 0', name='ck_scripture_validation_findings_chapter_positive'
        ),
        CheckConstraint(
            'verse IS NULL OR verse > 0', name='ck_scripture_validation_findings_verse_positive'
        ),
        Index('ix_scripture_validation_findings_run_severity', 'run_id', 'severity'),
        Index('ix_scripture_validation_findings_code', 'code'),
        Index('ix_scripture_validation_findings_work_position', 'work_id', 'chapter', 'verse'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey('scripture_ingest_runs.id', ondelete='CASCADE'), nullable=False
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


class ScripturePublication(Base):
    __tablename__ = 'scripture_publications'
    __table_args__ = (
        UniqueConstraint('edition_code', 'publication_version', name='uq_scripture_publications_edition_version'),
        CheckConstraint('publication_version > 0', name='ck_scripture_publications_version_positive'),
        ForeignKeyConstraint(
            ['run_id', 'edition_code'],
            ['scripture_ingest_runs.id', 'scripture_ingest_runs.edition_code'],
            name='fk_scripture_publications_run_edition',
            ondelete='CASCADE',
        ),
        ForeignKeyConstraint(
            ['previous_run_id', 'edition_code'],
            ['scripture_ingest_runs.id', 'scripture_ingest_runs.edition_code'],
            name='fk_scripture_publications_previous_run_edition',
            ondelete='RESTRICT',
        ),
        Index(
            'uq_scripture_publications_active_edition',
            'edition_code',
            unique=True,
            sqlite_where=column('active').is_(True),
            postgresql_where=column('active').is_(True),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    edition_code: Mapped[str] = mapped_column(
        ForeignKey('text_editions.edition_code', ondelete='CASCADE'), nullable=False
    )
    run_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    previous_run_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    publication_version: Mapped[int] = mapped_column(Integer, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    active: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True), nullable=False, default=True, server_default='1'
    )
