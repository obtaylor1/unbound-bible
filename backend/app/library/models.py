from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    false,
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
            "verification_status IN ('provisional', 'verified')",
            name='ck_edition_work_sources_verification_status',
        ),
        CheckConstraint(
            "canon_scope IN ('ethio81', 'supplemental')",
            name='ck_edition_work_sources_canon_scope',
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
    verification_status: Mapped[str] = mapped_column(String(16))
    canon_scope: Mapped[str] = mapped_column(String(16))


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
