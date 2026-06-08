"""
EditionMetadata Database Model
Tracks every unique biblical or scholarly edition/translation.
"""

import os
import sys
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ARRAY
import enum

# Add backend directory to path for database imports
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
sys.path.insert(0, backend_path)

try:
    from database import Base
except ImportError:
    # Fallback Base if import fails
    Base = declarative_base()


class IngestStatusEnum(enum.Enum):
    """Enumeration for ingest status tracking"""
    queued = "queued"
    parsed = "parsed" 
    aligned = "aligned"
    verified = "verified"


class EditionMetadata(Base):
    """
    Database model for tracking every unique biblical or scholarly edition/translation.
    
    This model tracks comprehensive metadata about different editions, translations,
    and versions of biblical and scholarly texts to support multi-canonical and 
    multi-language biblical study.
    """
    __tablename__ = "edition_metadata"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Core identification
    work_id = Column(String(100), nullable=False, index=True)  # e.g., "Genesis", "1 Enoch"
    language_script = Column(String(50), nullable=False, index=True)  # e.g., "hbo/Hebrew", "grc/Greek", "en/English"
    
    # Canonical tradition support
    canon_tags = Column(ARRAY(String), nullable=False, default=[])  # ["protestant", "catholic", "orthodox", "ethiopian", etc.]
    
    # Publication metadata
    source_title = Column(String(500), nullable=False)  # Full title of the source/edition
    editor_translator = Column(String(300))  # Name(s) of editor(s)/translator(s)
    publisher = Column(String(200))  # Publishing organization or individual
    
    # Legal and access information
    license = Column(String(100), nullable=False)  # "PD", "CC BY 4.0", etc.
    provenance_url = Column(Text)  # Download/landing page link
    
    # Technical metadata
    has_morph = Column(Boolean, default=False, nullable=False)  # Has morphological analysis
    ingest_status = Column(Enum(IngestStatusEnum), default=IngestStatusEnum.queued, nullable=False)
    
    # Tracking metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<EditionMetadata(work_id='{self.work_id}', language_script='{self.language_script}', canon_tags={self.canon_tags})>"
    
    @property
    def canonical_traditions(self):
        """Get list of canonical traditions this edition belongs to"""
        return self.canon_tags if self.canon_tags else []
    
    def has_canonical_tradition(self, tradition: str) -> bool:
        """Check if this edition belongs to a specific canonical tradition"""
        return tradition.lower() in [tag.lower() for tag in (self.canon_tags or [])]
    
    def is_original_language(self) -> bool:
        """Check if this is an original language text (Hebrew/Greek/Aramaic)"""
        original_languages = ["hbo", "hebrew", "grc", "greek", "aramaic", "arc"]
        return any(lang in self.language_script.lower() for lang in original_languages)
    
    def is_public_domain(self) -> bool:
        """Check if this edition is in the public domain"""
        pd_indicators = ["pd", "public domain", "cc0", "cc by"]
        return any(indicator in self.license.lower() for indicator in pd_indicators)


# Example usage and validation
def create_sample_editions():
    """
    Create sample EditionMetadata entries for testing and demonstration.
    This function shows proper usage of the model.
    """
    sample_editions = [
        EditionMetadata(
            work_id="Genesis",
            language_script="hbo/Hebrew",
            canon_tags=["protestant", "catholic", "orthodox", "ethiopian"],
            source_title="Open Scriptures Hebrew Bible (OSHB)",
            editor_translator="Open Scriptures Community",
            publisher="Open Scriptures",
            license="CC BY 4.0",
            provenance_url="https://github.com/openscriptures/morphhb",
            has_morph=True,
            ingest_status=IngestStatusEnum.verified
        ),
        EditionMetadata(
            work_id="1 Enoch",
            language_script="gez/Geez",
            canon_tags=["ethiopian"],
            source_title="Book of Enoch in Ethiopic",
            editor_translator="R.H. Charles",
            publisher="Ethiopian Orthodox Tewahedo Church",
            license="PD",
            provenance_url="https://archive.org/details/ethiopic-enoch",
            has_morph=False,
            ingest_status=IngestStatusEnum.parsed
        ),
        EditionMetadata(
            work_id="Matthew",
            language_script="grc/Greek",
            canon_tags=["protestant", "catholic", "orthodox", "ethiopian"],
            source_title="SBL Greek New Testament (SBLGNT)",
            editor_translator="Michael W. Holmes",
            publisher="Society of Biblical Literature",
            license="CC BY-SA",
            provenance_url="https://www.sbl-site.org/educational/BiblicalFonts_SBLGreek.aspx",
            has_morph=True,
            ingest_status=IngestStatusEnum.verified
        ),
        EditionMetadata(
            work_id="Jubilees",
            language_script="gez/Geez",
            canon_tags=["ethiopian"],
            source_title="Book of Jubilees - Ethiopian Orthodox Canon",
            editor_translator="Ethiopian Orthodox Translators",
            publisher="Ethiopian Orthodox Tewahedo Church",
            license="CC BY 4.0",
            provenance_url="https://ethiopianorthodox.org/english/canonical/jubilees.html",
            has_morph=False,
            ingest_status=IngestStatusEnum.queued
        )
    ]
    
    return sample_editions


if __name__ == "__main__":
    print("EditionMetadata Model Definition")
    print("================================")
    print()
    print("Table: edition_metadata")
    print("Fields:")
    print("- work_id: String(100) - Work identifier (e.g., 'Genesis', '1 Enoch')")
    print("- language_script: String(50) - Language/script (e.g., 'hbo/Hebrew', 'grc/Greek')")  
    print("- canon_tags: ARRAY(String) - Canonical traditions ['protestant', 'catholic', 'orthodox', 'ethiopian']")
    print("- source_title: String(500) - Full title of source/edition")
    print("- editor_translator: String(300) - Editor(s)/translator(s)")
    print("- publisher: String(200) - Publishing organization")
    print("- license: String(100) - License type ('PD', 'CC BY 4.0', etc.)")
    print("- provenance_url: Text - Download/landing page URL") 
    print("- has_morph: Boolean - Has morphological analysis")
    print("- ingest_status: Enum - Status (queued | parsed | aligned | verified)")
    print("- created_at/updated_at: DateTime - Tracking timestamps")
    print()
    print("Sample entries:")
    for edition in create_sample_editions():
        print(f"  {edition}")