from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    event,
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
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.database import Base


PUBLICATION_STATUSES = (
    'needs_rights_review',
    'importing',
    'verified',
    'active',
    'disabled',
    'restricted',
    'internal_research_only',
)

DIVISION_TYPES = (
    'book',
    'section',
    'chapter',
    'verse',
    'paragraph',
    'fragment',
    'column',
    'line',
)

TEXT_DIRECTIONS = ('ltr', 'rtl', 'auto')

TEXTUAL_CERTAINTIES = (
    'visible_text',
    'reconstructed_text',
    'supplied_text',
    'translation',
    'editorial_note',
)

STORED_SOURCE_CLASSIFICATIONS = (
    'canonical_scripture',
    'ethiopian_canon',
    'deuterocanonical_scripture',
    'ancient_biblical_translation',
    'ancient_jewish_literature',
    'dead_sea_scroll_manuscript',
    'ancient_historical_source',
    'early_christian_writing',
    'jewish_tradition',
    'church_tradition',
    'archaeology',
    'modern_scholarship',
)


def _sql_values(values: tuple[str, ...]) -> str:
    return ', '.join(f"'{value}'" for value in values)


class ImmutableResearchLibraryRecord:
    """Marker for publication snapshot and append-only records."""


class ImmutableResearchLibraryRecordError(RuntimeError):
    pass


class ResearchWorkProfile(Base):
    __tablename__ = 'research_work_profiles'
    __table_args__ = (
        UniqueConstraint('work_id', name='uq_research_work_profiles_work_id'),
        CheckConstraint(
            "length(trim(source_classification)) > 0",
            name='ck_research_work_profiles_source_classification_nonblank',
        ),
        CheckConstraint(
            f"source_classification IN ({_sql_values(STORED_SOURCE_CLASSIFICATIONS)})",
            name='ck_research_work_profiles_source_classification',
        ),
        CheckConstraint(
            "length(trim(hierarchy_level)) > 0",
            name='ck_research_work_profiles_hierarchy_level_nonblank',
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    work_id: Mapped[str] = mapped_column(
        ForeignKey(
            'library_works.id',
            name='fk_research_work_profiles_work_id_library_works',
            ondelete='RESTRICT',
        ),
        nullable=False,
    )
    short_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    short_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_classification: Mapped[str] = mapped_column(String(100), nullable=False)
    hierarchy_level: Mapped[str] = mapped_column(String(100), nullable=False)
    traditions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    canonical_statuses: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    original_languages: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    attributed_authorship: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_era: Mapped[str | None] = mapped_column(String(200), nullable=True)
    historical_classification: Mapped[str | None] = mapped_column(String(100), nullable=True)
    literary_classification: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class WorkDivision(Base):
    __tablename__ = 'work_divisions'
    __table_args__ = (
        UniqueConstraint(
            'work_id', 'normalized_locator', name='uq_work_divisions_work_locator'
        ),
        UniqueConstraint('work_id', 'canonical_key', name='uq_work_divisions_work_key'),
        UniqueConstraint('id', 'work_id', name='uq_work_divisions_id_work'),
        ForeignKeyConstraint(
            ['parent_id', 'work_id'],
            ['work_divisions.id', 'work_divisions.work_id'],
            name='fk_work_divisions_parent_same_work',
            ondelete='RESTRICT',
        ),
        Index(
            'uq_work_divisions_root_ordinal',
            'work_id',
            'ordinal',
            unique=True,
            sqlite_where=column('parent_id').is_(None),
            postgresql_where=column('parent_id').is_(None),
        ),
        Index(
            'uq_work_divisions_child_ordinal',
            'work_id',
            'parent_id',
            'ordinal',
            unique=True,
            sqlite_where=column('parent_id').is_not(None),
            postgresql_where=column('parent_id').is_not(None),
        ),
        Index('ix_work_divisions_parent_id', 'parent_id'),
        Index('ix_work_divisions_work_type', 'work_id', 'division_type'),
        CheckConstraint(
            f"division_type IN ({_sql_values(DIVISION_TYPES)})",
            name='ck_work_divisions_division_type',
        ),
        CheckConstraint('ordinal > 0', name='ck_work_divisions_ordinal_positive'),
        CheckConstraint(
            "length(trim(normalized_locator)) > 0",
            name='ck_work_divisions_locator_nonblank',
        ),
        CheckConstraint(
            "length(trim(canonical_key)) > 0", name='ck_work_divisions_key_nonblank'
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    work_id: Mapped[str] = mapped_column(
        ForeignKey(
            'library_works.id', name='fk_work_divisions_work_id_library_works', ondelete='RESTRICT'
        ),
        nullable=False,
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    division_type: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_locator: Mapped[str] = mapped_column(String(500), nullable=False)
    canonical_key: Mapped[str] = mapped_column(String(500), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    display_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parent: Mapped['WorkDivision | None'] = relationship(
        remote_side='WorkDivision.id', foreign_keys=[parent_id]
    )


class SourceEdition(Base):
    __tablename__ = 'source_editions'
    __table_args__ = (
        ForeignKeyConstraint(
            ['active_publication_id', 'id'],
            ['source_publications.id', 'source_publications.source_edition_id'],
            name='fk_source_editions_active_publication_same_edition',
            ondelete='RESTRICT',
            use_alter=True,
        ),
        Index('ix_source_editions_checksum', 'checksum'),
        Index('ix_source_editions_language', 'language'),
        CheckConstraint("length(trim(title)) > 0", name='ck_source_editions_title_nonblank'),
        CheckConstraint(
            "length(trim(edition_label)) > 0", name='ck_source_editions_label_nonblank'
        ),
        CheckConstraint(
            'publication_year IS NULL OR publication_year > 0',
            name='ck_source_editions_publication_year_positive',
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    active_publication_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    edition_label: Mapped[str] = mapped_column(String(500), nullable=False)
    translator: Mapped[str | None] = mapped_column(String(500), nullable=True)
    editor: Mapped[str | None] = mapped_column(String(500), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(500), nullable=True)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_publication: Mapped[str | None] = mapped_column(String(500), nullable=True)
    language: Mapped[str] = mapped_column(String(64), nullable=False)
    script: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    acquisition_source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    locator_scheme: Mapped[str] = mapped_column(String(200), nullable=False)
    attribution: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SourceEditionWork(Base):
    __tablename__ = 'source_edition_works'
    __table_args__ = (
        UniqueConstraint(
            'source_edition_id', 'work_id', name='uq_source_edition_works_edition_work'
        ),
        Index('ix_source_edition_works_work_id', 'work_id'),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_edition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            'source_editions.id',
            name='fk_source_edition_works_edition_id_source_editions',
            ondelete='RESTRICT',
        ),
        nullable=False,
    )
    work_id: Mapped[str] = mapped_column(
        ForeignKey(
            'library_works.id',
            name='fk_source_edition_works_work_id_library_works',
            ondelete='RESTRICT',
        ),
        nullable=False,
    )
    source_label: Mapped[str] = mapped_column(String(500), nullable=False)
    locator_scheme: Mapped[str | None] = mapped_column(String(200), nullable=True)
    attribution_override: Mapped[str | None] = mapped_column(Text, nullable=True)


class LicenseRecord(Base):
    __tablename__ = 'license_records'
    __table_args__ = (
        UniqueConstraint('id', 'source_edition_id', name='uq_license_records_id_edition'),
        Index('ix_license_records_source_edition_id', 'source_edition_id'),
        Index('ix_license_records_verification_date', 'verification_date'),
        CheckConstraint(
            "length(trim(license_name)) > 0", name='ck_license_records_name_nonblank'
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_edition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            'source_editions.id',
            name='fk_license_records_edition_id_source_editions',
            ondelete='RESTRICT',
        ),
        nullable=False,
    )
    license_name: Mapped[str] = mapped_column(String(500), nullable=False)
    license_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    is_public_domain: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    commercial_use_allowed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    display_allowed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    redistribution_allowed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    modification_allowed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    attribution_required: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    required_attribution_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_text_rights: Mapped[str | None] = mapped_column(Text, nullable=True)
    translation_rights: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_rights: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_source_urls: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    reviewer_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            'users.id', name='fk_license_records_reviewer_id_users', ondelete='RESTRICT'
        ),
        nullable=True,
    )
    verification_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    explanatory_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SourcePublication(ImmutableResearchLibraryRecord, Base):
    __tablename__ = 'source_publications'
    __table_args__ = (
        UniqueConstraint(
            'source_edition_id', 'version', name='uq_source_publications_edition_version'
        ),
        UniqueConstraint(
            'id', 'source_edition_id', name='uq_source_publications_id_edition'
        ),
        ForeignKeyConstraint(
            ['license_record_id', 'source_edition_id'],
            ['license_records.id', 'license_records.source_edition_id'],
            name='fk_source_publications_license_same_edition',
            ondelete='RESTRICT',
        ),
        Index('ix_source_publications_edition_status', 'source_edition_id', 'status'),
        Index('ix_source_publications_license_record_id', 'license_record_id'),
        Index('ix_source_publications_ingest_run_id', 'ingest_run_id'),
        CheckConstraint(
            f"status IN ({_sql_values(PUBLICATION_STATUSES)})",
            name='ck_source_publications_status',
        ),
        CheckConstraint('version > 0', name='ck_source_publications_version_positive'),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_edition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            'source_editions.id',
            name='fk_source_publications_edition_id_source_editions',
            ondelete='RESTRICT',
        ),
        nullable=False,
    )
    license_record_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    ingest_run_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    validation_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    public_visibility: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    content_checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            'users.id', name='fk_source_publications_publisher_id_users', ondelete='RESTRICT'
        ),
        nullable=True,
    )
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            'users.id', name='fk_source_publications_reviewer_id_users', ondelete='RESTRICT'
        ),
        nullable=True,
    )


class ContentUnit(ImmutableResearchLibraryRecord, Base):
    __tablename__ = 'content_units'
    __table_args__ = (
        UniqueConstraint(
            'source_publication_id',
            'work_division_id',
            'ordinal',
            name='uq_content_units_publication_division_ordinal',
        ),
        UniqueConstraint(
            'id',
            'source_publication_id',
            'work_division_id',
            name='uq_content_units_id_publication_division',
        ),
        ForeignKeyConstraint(
            ['source_publication_id', 'source_edition_id'],
            ['source_publications.id', 'source_publications.source_edition_id'],
            name='fk_content_units_publication_same_edition',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['work_division_id', 'work_id'],
            ['work_divisions.id', 'work_divisions.work_id'],
            name='fk_content_units_division_same_work',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['source_edition_id', 'work_id'],
            ['source_edition_works.source_edition_id', 'source_edition_works.work_id'],
            name='fk_content_units_edition_covers_work',
            ondelete='RESTRICT',
        ),
        Index('ix_content_units_publication_checksum', 'source_publication_id', 'checksum'),
        Index('ix_content_units_division_id', 'work_division_id'),
        Index('ix_content_units_source_locator', 'source_publication_id', 'source_locator'),
        CheckConstraint(
            f"direction IN ({_sql_values(TEXT_DIRECTIONS)})", name='ck_content_units_direction'
        ),
        CheckConstraint(
            f"textual_certainty IN ({_sql_values(TEXTUAL_CERTAINTIES)})",
            name='ck_content_units_textual_certainty',
        ),
        CheckConstraint('ordinal > 0', name='ck_content_units_ordinal_positive'),
        CheckConstraint(
            "length(trim(source_locator)) > 0", name='ck_content_units_locator_nonblank'
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_publication_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    source_edition_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    work_id: Mapped[str] = mapped_column(String(100), nullable=False)
    work_division_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    language: Mapped[str] = mapped_column(String(64), nullable=False)
    script: Mapped[str | None] = mapped_column(String(64), nullable=True)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_locator: Mapped[str] = mapped_column(String(500), nullable=False)
    textual_certainty: Mapped[str] = mapped_column(String(32), nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)


class CitationAnchor(ImmutableResearchLibraryRecord, Base):
    __tablename__ = 'citation_anchors'
    __table_args__ = (
        UniqueConstraint(
            'source_publication_id', 'anchor_key', name='uq_citation_anchors_publication_key'
        ),
        UniqueConstraint(
            'source_publication_id',
            'content_unit_id',
            'human_locator',
            name='uq_citation_anchors_publication_unit_locator',
        ),
        UniqueConstraint(
            'id',
            'source_publication_id',
            'work_division_id',
            name='uq_citation_anchors_id_publication_division',
        ),
        ForeignKeyConstraint(
            ['content_unit_id', 'source_publication_id', 'work_division_id'],
            [
                'content_units.id',
                'content_units.source_publication_id',
                'content_units.work_division_id',
            ],
            name='fk_citation_anchors_content_same_scope',
            ondelete='RESTRICT',
        ),
        Index('ix_citation_anchors_content_unit_id', 'content_unit_id'),
        CheckConstraint(
            "length(trim(anchor_key)) > 0", name='ck_citation_anchors_key_nonblank'
        ),
        CheckConstraint(
            "length(trim(human_locator)) > 0", name='ck_citation_anchors_locator_nonblank'
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_publication_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    content_unit_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    work_division_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    anchor_key: Mapped[str] = mapped_column(String(500), nullable=False)
    human_locator: Mapped[str] = mapped_column(String(500), nullable=False)
    inspector_route: Mapped[str] = mapped_column(String(2048), nullable=False)
    open_target: Mapped[dict] = mapped_column(JSON, nullable=False)


class ResearchChunk(ImmutableResearchLibraryRecord, Base):
    __tablename__ = 'research_chunks'
    __table_args__ = (
        UniqueConstraint(
            'source_edition_id',
            'source_publication_id',
            'work_division_id',
            'boundary_type',
            'content_digest',
            name='uq_research_chunks_deduplication',
        ),
        UniqueConstraint(
            'source_publication_id', 'ordinal', name='uq_research_chunks_publication_ordinal'
        ),
        ForeignKeyConstraint(
            ['source_publication_id', 'source_edition_id'],
            ['source_publications.id', 'source_publications.source_edition_id'],
            name='fk_research_chunks_publication_same_edition',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['work_division_id', 'work_id'],
            ['work_divisions.id', 'work_divisions.work_id'],
            name='fk_research_chunks_division_same_work',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['source_edition_id', 'work_id'],
            ['source_edition_works.source_edition_id', 'source_edition_works.work_id'],
            name='fk_research_chunks_edition_covers_work',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['citation_anchor_id', 'source_publication_id', 'work_division_id'],
            [
                'citation_anchors.id',
                'citation_anchors.source_publication_id',
                'citation_anchors.work_division_id',
            ],
            name='fk_research_chunks_citation_same_scope',
            ondelete='RESTRICT',
        ),
        Index('ix_research_chunks_work_division', 'work_id', 'work_division_id'),
        Index('ix_research_chunks_citation_anchor_id', 'citation_anchor_id'),
        Index('ix_research_chunks_content_digest', 'content_digest'),
        CheckConstraint('ordinal > 0', name='ck_research_chunks_ordinal_positive'),
        CheckConstraint(
            f"classification IN ({_sql_values(STORED_SOURCE_CLASSIFICATIONS)})",
            name='ck_research_chunks_classification',
        ),
        CheckConstraint(
            "length(trim(boundary_type)) > 0", name='ck_research_chunks_boundary_nonblank'
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_edition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    source_publication_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    work_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    work_division_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    citation_anchor_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    boundary_type: Mapped[str] = mapped_column(String(64), nullable=False)
    classification: Mapped[str] = mapped_column(String(100), nullable=False)
    hierarchy_level: Mapped[str] = mapped_column(String(100), nullable=False)
    language: Mapped[str] = mapped_column(String(64), nullable=False)
    content_digest: Mapped[str] = mapped_column(String(128), nullable=False)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    search_document: Mapped[str | None] = mapped_column(Text, nullable=True)


class LegacySourceLink(Base):
    __tablename__ = 'legacy_source_links'
    __table_args__ = (
        UniqueConstraint(
            'legacy_type', 'legacy_key', name='uq_legacy_source_links_type_key'
        ),
        Index('ix_legacy_source_links_source_edition_id', 'source_edition_id'),
        CheckConstraint(
            "length(trim(legacy_type)) > 0", name='ck_legacy_source_links_type_nonblank'
        ),
        CheckConstraint(
            "length(trim(legacy_key)) > 0", name='ck_legacy_source_links_key_nonblank'
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    legacy_type: Mapped[str] = mapped_column(String(200), nullable=False)
    legacy_key: Mapped[str] = mapped_column(String(500), nullable=False)
    source_edition_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            'source_editions.id',
            name='fk_legacy_source_links_edition_id_source_editions',
            ondelete='RESTRICT',
        ),
        nullable=False,
    )


class LegacyContentLink(Base):
    __tablename__ = 'legacy_content_links'
    __table_args__ = (
        UniqueConstraint(
            'legacy_type', 'legacy_key', name='uq_legacy_content_links_type_key'
        ),
        Index('ix_legacy_content_links_content_unit_id', 'content_unit_id'),
        CheckConstraint(
            "length(trim(legacy_type)) > 0", name='ck_legacy_content_links_type_nonblank'
        ),
        CheckConstraint(
            "length(trim(legacy_key)) > 0", name='ck_legacy_content_links_key_nonblank'
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    legacy_type: Mapped[str] = mapped_column(String(200), nullable=False)
    legacy_key: Mapped[str] = mapped_column(String(500), nullable=False)
    content_unit_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            'content_units.id',
            name='fk_legacy_content_links_content_unit_id_content_units',
            ondelete='RESTRICT',
        ),
        nullable=False,
    )


class SourceAuditEvent(ImmutableResearchLibraryRecord, Base):
    __tablename__ = 'source_audit_events'
    __table_args__ = (
        ForeignKeyConstraint(
            ['source_publication_id', 'source_edition_id'],
            ['source_publications.id', 'source_publications.source_edition_id'],
            name='fk_source_audit_events_publication_same_edition',
            ondelete='RESTRICT',
        ),
        Index('ix_source_audit_events_edition_created', 'source_edition_id', 'created_at'),
        Index(
            'ix_source_audit_events_publication_created', 'source_publication_id', 'created_at'
        ),
        Index('ix_source_audit_events_actor_id', 'actor_id'),
        CheckConstraint(
            "length(trim(action)) > 0", name='ck_source_audit_events_action_nonblank'
        ),
        CheckConstraint(
            'source_publication_id IS NULL OR source_edition_id IS NOT NULL',
            name='ck_source_audit_events_publication_requires_edition',
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            'users.id', name='fk_source_audit_events_actor_id_users', ondelete='RESTRICT'
        ),
        nullable=False,
    )
    source_edition_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            'source_editions.id',
            name='fk_source_audit_events_edition_id_source_editions',
            ondelete='RESTRICT',
        ),
        nullable=True,
    )
    source_publication_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(200), nullable=False)
    prior_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resulting_state: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_run_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    checksum_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


IMMUTABLE_RESEARCH_LIBRARY_TABLES = frozenset({
    'source_publications',
    'content_units',
    'citation_anchors',
    'research_chunks',
    'source_audit_events',
})


@event.listens_for(Session, 'do_orm_execute')
def _protect_immutable_research_library_bulk_dml(orm_execute_state) -> None:
    if not (orm_execute_state.is_update or orm_execute_state.is_delete):
        return
    target_table = getattr(orm_execute_state.statement, 'table', None)
    if target_table is not None and target_table.name in IMMUTABLE_RESEARCH_LIBRARY_TABLES:
        raise ImmutableResearchLibraryRecordError(
            f'{target_table.name} records are immutable and cannot be updated or deleted'
        )


@event.listens_for(Session, 'before_flush')
def _protect_immutable_research_library_records(
    session: Session, _flush_context, _instances
) -> None:
    for record in session.deleted:
        if isinstance(record, ImmutableResearchLibraryRecord):
            raise ImmutableResearchLibraryRecordError(
                f'{type(record).__name__} is immutable and cannot be deleted'
            )
    for record in session.dirty:
        if (
            isinstance(record, ImmutableResearchLibraryRecord)
            and session.is_modified(record, include_collections=True)
        ):
            raise ImmutableResearchLibraryRecordError(
                f'{type(record).__name__} is immutable and cannot be updated'
            )
