from datetime import datetime

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
    false,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LibraryWork(Base):
    __tablename__ = 'library_works'

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))


class LibraryWorkAlias(Base):
    __tablename__ = 'library_work_aliases'
    __table_args__ = (Index('ix_library_work_aliases_work_id', 'work_id'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alias: Mapped[str] = mapped_column(String(200), unique=True)
    work_id: Mapped[str] = mapped_column(ForeignKey('library_works.id', ondelete='CASCADE'))


class CanonEntry(Base):
    __tablename__ = 'canon_entries'
    __table_args__ = (
        UniqueConstraint(
            'canon_code',
            'testament',
            'canonical_order',
            name='uq_canon_entries_canon_testament_order',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canon_code: Mapped[str] = mapped_column(String(64))
    testament: Mapped[str] = mapped_column(String(8))
    canonical_order: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))


class CanonEntryWork(Base):
    __tablename__ = 'canon_entry_works'
    __table_args__ = (Index('ix_canon_entry_works_work_id', 'work_id'),)

    canon_entry_id: Mapped[int] = mapped_column(
        ForeignKey('canon_entries.id', ondelete='CASCADE'), primary_key=True
    )
    work_id: Mapped[str] = mapped_column(
        ForeignKey('library_works.id', ondelete='CASCADE'), primary_key=True
    )


class TextEdition(Base):
    __tablename__ = 'text_editions'
    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('queued', 'staged', 'provisional', 'verified', 'withdrawn')",
            name='ck_text_editions_verification_status',
        ),
        CheckConstraint(
            "relationship IN ('exact_ethiopian', 'related_recension', 'general_reading')",
            name='ck_text_editions_relationship',
        ),
        Index('ix_text_editions_verification_status', 'verification_status'),
    )

    edition_code: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    reading_language: Mapped[str] = mapped_column(String(64))
    source_language: Mapped[str] = mapped_column(String(64))
    script: Mapped[str] = mapped_column(String(64))
    translator: Mapped[str | None] = mapped_column(String(200), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(200), nullable=True)
    published_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    license_spdx: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attribution: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_tradition: Mapped[str | None] = mapped_column(String(200), nullable=True)
    relationship: Mapped[str] = mapped_column(String(32))
    versification: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expected_coverage: Mapped[dict] = mapped_column(JSON)
    verification_status: Mapped[str] = mapped_column(String(16))
    source_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)


class EditionWorkSource(Base):
    __tablename__ = 'edition_work_sources'
    __table_args__ = (
        UniqueConstraint(
            'edition_code',
            'work_id',
            name='uq_edition_work_sources_edition_work',
        ),
        CheckConstraint(
            "verification_status IN ('in_progress', 'verified_exact', "
            "'verified_formatting', 'verified_rebuilt', 'review_required')",
            name='ck_edition_work_sources_verification_status',
        ),
        CheckConstraint(
            "canon_scope IN ('ethio81', 'supplemental')",
            name='ck_edition_work_sources_canon_scope',
        ),
        CheckConstraint(
            'comparison_exact >= 0',
            name='ck_edition_work_sources_comparison_exact_nonnegative',
        ),
        CheckConstraint(
            'comparison_formatting >= 0',
            name='ck_edition_work_sources_comparison_formatting_nonnegative',
        ),
        CheckConstraint(
            'comparison_missing >= 0',
            name='ck_edition_work_sources_comparison_missing_nonnegative',
        ),
        CheckConstraint(
            'comparison_extra >= 0',
            name='ck_edition_work_sources_comparison_extra_nonnegative',
        ),
        CheckConstraint(
            'comparison_wording >= 0',
            name='ck_edition_work_sources_comparison_wording_nonnegative',
        ),
        CheckConstraint(
            'artifact_size IS NULL OR artifact_size >= 0',
            name='ck_edition_work_sources_artifact_size_nonnegative',
        ),
        CheckConstraint(
            'artifact_sha256 IS NULL OR length(artifact_sha256) = 64',
            name='ck_edition_work_sources_artifact_sha256_length',
        ),
        CheckConstraint(
            'comparison_report_sha256 IS NULL OR length(comparison_report_sha256) = 64',
            name='ck_edition_work_sources_comparison_report_sha256_length',
        ),
        Index('ix_edition_work_sources_work_id', 'work_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    edition_code: Mapped[str] = mapped_column(
        ForeignKey('text_editions.edition_code', ondelete='CASCADE')
    )
    work_id: Mapped[str] = mapped_column(ForeignKey('library_works.id', ondelete='CASCADE'))
    source_key: Mapped[str] = mapped_column(String(100))
    source_label: Mapped[str] = mapped_column(String(200))
    translator: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_language: Mapped[str] = mapped_column(String(100))
    source_tradition: Mapped[str] = mapped_column(String(200))
    published_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    license_spdx: Mapped[str] = mapped_column(String(100))
    attribution: Mapped[str] = mapped_column(Text)
    provenance_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    fallback: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    modified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    modification_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(32))
    canon_scope: Mapped[str] = mapped_column(String(16))
    source_edition: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_revision: Mapped[str | None] = mapped_column(String(200), nullable=True)
    rights_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    rights_jurisdiction: Mapped[str | None] = mapped_column(String(100), nullable=True)
    artifact_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    artifact_retrieved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    artifact_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transformations: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )
    comparison_exact: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text('0')
    )
    comparison_formatting: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text('0')
    )
    comparison_missing: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text('0')
    )
    comparison_extra: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text('0')
    )
    comparison_wording: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text('0')
    )
    comparison_report_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class EditionCoverage(Base):
    __tablename__ = 'edition_coverage'
    __table_args__ = (
        UniqueConstraint('edition_code', 'work_id', name='uq_edition_coverage_edition_work'),
        CheckConstraint(
            "status IN ('verified_english', 'verified_original', 'related_recension', 'translation_needed')",
            name='ck_edition_coverage_status',
        ),
        Index('ix_edition_coverage_work_id', 'work_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    edition_code: Mapped[str] = mapped_column(
        ForeignKey('text_editions.edition_code', ondelete='CASCADE')
    )
    work_id: Mapped[str] = mapped_column(ForeignKey('library_works.id', ondelete='CASCADE'))
    status: Mapped[str] = mapped_column(String(32))
    chapter_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verse_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
