# Liberation Bible Project - Database Models  
# Research-Grade Library Platform with Vector Search & Graph Relations
# Referenced from blueprint:python_database integration

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, Boolean, Float, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ARRAY
from pgvector.sqlalchemy import Vector
from datetime import datetime
import enum

Base = declarative_base()

class BiblicalText(Base):
    __tablename__ = "biblical_texts"
    
    id = Column(Integer, primary_key=True, index=True)
    book = Column(String(50), nullable=False)
    chapter = Column(Integer, nullable=False)
    verse = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    translation = Column(String(50), default="KJV")
    translation_id = Column(Integer, ForeignKey("translations.id"))
    
    # Abstract Verse ID Architecture - Links to canon-independent verse identity
    abstract_verse_id = Column(Integer, ForeignKey("abstract_verses.id"), nullable=True, index=True)
    
    # Vector search capabilities for semantic search
    text_embedding = Column(Vector(1536))  # OpenAI text-embedding-ada-002 (1536 dimensions)
    
    # Versioning support for immutable revisions
    version = Column(Integer, default=1)
    is_latest = Column(Boolean, default=True)
    previous_version_id = Column(Integer, ForeignKey("biblical_texts.id"), nullable=True)
    
    # Research metadata
    canonical_order = Column(Integer)  # For proper biblical ordering
    textual_notes = Column(JSON)  # Critical apparatus notes
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    abstract_verse = relationship("AbstractVerse", back_populates="biblical_texts")
    historical_notes = relationship("HistoricalNote", back_populates="biblical_text")
    geographical_locations = relationship("GeographicalLocation", back_populates="biblical_text")
    original_words = relationship("OriginalWord", back_populates="biblical_text")
    translation_ref = relationship("Translation", back_populates="biblical_texts")
    
    # Versioning relationships
    previous_version = relationship("BiblicalText", remote_side=[id], foreign_keys=[previous_version_id])
    
    # Cross-references and intertextual links
    source_references = relationship("CrossReference", foreign_keys="CrossReference.source_text_id", back_populates="source_text")
    target_references = relationship("CrossReference", foreign_keys="CrossReference.target_text_id", back_populates="target_text")
    
    # Textual apparatus
    textual_variants = relationship("TextualVariant", back_populates="biblical_text")
    
    # Index for vector similarity search
    __table_args__ = (
        Index("ix_biblical_texts_embedding", text_embedding, postgresql_using="ivfflat", postgresql_with={"lists": 100}),
        Index("ix_biblical_texts_abstract_verse", abstract_verse_id),
    )

class HistoricalNote(Base):
    __tablename__ = "historical_notes"
    
    id = Column(Integer, primary_key=True, index=True)
    biblical_text_id = Column(Integer, ForeignKey("biblical_texts.id"))
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    historical_period = Column(String(100))
    source = Column(String(200))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    biblical_text = relationship("BiblicalText", back_populates="historical_notes")

class GeographicalLocation(Base):
    __tablename__ = "geographical_locations"
    
    id = Column(Integer, primary_key=True, index=True)
    biblical_text_id = Column(Integer, ForeignKey("biblical_texts.id"))
    name = Column(String(200), nullable=False)
    modern_name = Column(String(200))
    latitude = Column(String(50))
    longitude = Column(String(50))
    description = Column(Text)
    
    # Multi-candidate support with confidence scoring
    confidence_score = Column(Float, default=0.5)  # 0.0 to 1.0 confidence level
    identification_source = Column(String(200))  # Academic source for this identification
    alternative_names = Column(ARRAY(String))  # Multiple name possibilities
    archaeological_evidence = Column(Text)  # Supporting archaeological data
    scholarly_debate = Column(Text)  # Notes on academic disagreements
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    biblical_text = relationship("BiblicalText", back_populates="geographical_locations")

class LanguageEnum(enum.Enum):
    hebrew = "hebrew"
    greek = "greek"
    aramaic = "aramaic"
    geez = "geez"          # Ge'ez for Ethiopian Orthodox tradition
    amharic = "amharic"    # Modern Ethiopian language
    english = "english"    # English translations
    latin = "latin"        # Vulgate and other Latin texts

class OriginalWord(Base):
    __tablename__ = "original_words"
    
    id = Column(Integer, primary_key=True, index=True)
    biblical_text_id = Column(Integer, ForeignKey("biblical_texts.id"))
    lexicon_entry_id = Column(Integer, ForeignKey("lexicon_entries.id"))
    word_text = Column(String(100), nullable=False)
    language = Column(Enum(LanguageEnum), nullable=False)
    strong_number = Column(String(10))
    root_word = Column(String(100))
    definition = Column(Text, nullable=False)
    word_position = Column(Integer)  # position in verse for mapping
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    biblical_text = relationship("BiblicalText", back_populates="original_words")
    lexicon_entry = relationship("LexiconEntry", back_populates="word_occurrences")

class LexiconEntry(Base):
    """Strong's Exhaustive Concordance lexicon entries"""
    __tablename__ = "lexicon_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    strong_number = Column(String(10), nullable=False, unique=True, index=True)
    language = Column(Enum(LanguageEnum), nullable=False)
    original_word = Column(String(200), nullable=False)  # Hebrew/Greek text
    transliteration = Column(String(200))  # Romanized pronunciation
    pronunciation = Column(String(200))  # Phonetic guide
    part_of_speech = Column(String(50))  # noun, verb, adjective, etc.
    definition = Column(Text, nullable=False)  # Brief definition
    detailed_definition = Column(Text)  # Extended definition
    root_word = Column(String(200))  # Root or derivative info
    usage_notes = Column(Text)  # Additional usage context
    kjv_translation_count = Column(Integer, default=0)  # How often used in KJV
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    word_occurrences = relationship("OriginalWord", back_populates="lexicon_entry")

class Translation(Base):
    """Bible translation information"""
    __tablename__ = "translations"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(10), nullable=False, unique=True, index=True)  # KJV, MT, TR, etc.
    name = Column(String(200), nullable=False)  # King James Version
    description = Column(Text)
    language = Column(String(50), nullable=False)  # English, Hebrew, Greek
    source_text = Column(String(100))  # Masoretic Text, Textus Receptus, etc.
    year_published = Column(Integer)
    is_original_language = Column(Boolean, default=False)
    is_public_domain = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    biblical_texts = relationship("BiblicalText", back_populates="translation_ref")

class BookEnum(enum.Enum):
    # Old Testament
    genesis = "Genesis"
    exodus = "Exodus" 
    leviticus = "Leviticus"
    numbers = "Numbers"
    deuteronomy = "Deuteronomy"
    joshua = "Joshua"
    judges = "Judges"
    ruth = "Ruth"
    first_samuel = "1 Samuel"
    second_samuel = "2 Samuel"
    first_kings = "1 Kings"
    second_kings = "2 Kings"
    first_chronicles = "1 Chronicles"
    second_chronicles = "2 Chronicles"
    ezra = "Ezra"
    nehemiah = "Nehemiah"
    esther = "Esther"
    job = "Job"
    psalms = "Psalms"
    proverbs = "Proverbs"
    ecclesiastes = "Ecclesiastes"
    song_of_solomon = "Song of Solomon"
    isaiah = "Isaiah"
    jeremiah = "Jeremiah"
    lamentations = "Lamentations"
    ezekiel = "Ezekiel"
    daniel = "Daniel"
    hosea = "Hosea"
    joel = "Joel"
    amos = "Amos"
    obadiah = "Obadiah"
    jonah = "Jonah"
    micah = "Micah"
    nahum = "Nahum"
    habakkuk = "Habakkuk"
    zephaniah = "Zephaniah"
    haggai = "Haggai"
    zechariah = "Zechariah"
    malachi = "Malachi"
    
    # New Testament
    matthew = "Matthew"
    mark = "Mark"
    luke = "Luke"
    john = "John"
    acts = "Acts"
    romans = "Romans"
    first_corinthians = "1 Corinthians"
    second_corinthians = "2 Corinthians"
    galatians = "Galatians"
    ephesians = "Ephesians"
    philippians = "Philippians"
    colossians = "Colossians"
    first_thessalonians = "1 Thessalonians"
    second_thessalonians = "2 Thessalonians"
    first_timothy = "1 Timothy"
    second_timothy = "2 Timothy"
    titus = "Titus"
    philemon = "Philemon"
    hebrews = "Hebrews"
    james = "James"
    first_peter = "1 Peter"
    second_peter = "2 Peter"
    first_john = "1 John"
    second_john = "2 John"
    third_john = "3 John"
    jude = "Jude"
    revelation = "Revelation"

# ===============================================================================
# ABSTRACT VERSE ID ARCHITECTURE - Multi-Canon Support
# ===============================================================================

class AbstractVerse(Base):
    """
    Abstract verse entities that decouple content from versification systems.
    Enables cross-references that survive versification changes and supports
    multiple canonical traditions (Protestant, Catholic, Ethiopian Orthodox).
    """
    __tablename__ = "abstract_verses"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Content identification
    canonical_key = Column(String(200), nullable=False, index=True)  # e.g., "genesis.1.1", "meqabyan1.1.1"
    content_hash = Column(String(64), nullable=True, index=True)  # SHA256 for deduplication
    
    # Metadata
    notes = Column(JSON)  # Additional metadata for research
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    biblical_texts = relationship("BiblicalText", back_populates="abstract_verse")
    canonical_positions = relationship("CanonicalPosition", back_populates="abstract_verse")
    
    # Cross-references using abstract IDs
    source_abstract_references = relationship("CrossReference", foreign_keys="CrossReference.source_abstract_id", back_populates="source_abstract_verse")
    target_abstract_references = relationship("CrossReference", foreign_keys="CrossReference.target_abstract_id", back_populates="target_abstract_verse")
    
    # Indexes for efficient lookup
    __table_args__ = (
        Index("ix_abstract_verses_canonical_key", canonical_key),
        Index("ix_abstract_verses_content_hash", content_hash),
    )

class Canon(Base):
    """
    Biblical canons defining which books are included in different traditions.
    Examples: Protestant (66 books), Catholic (73), Ethiopian Orthodox (81).
    """
    __tablename__ = "canons"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), nullable=False, unique=True, index=True)  # PROT66, CATH73, ETH81
    name = Column(String(200), nullable=False)  # "Protestant Canon", "Ethiopian Orthodox Canon"
    description = Column(Text)
    
    # Canon metadata
    book_count = Column(Integer)  # Total number of books
    language_tradition = Column(String(50))  # Hebrew, Greek, Ge'ez, etc.
    historical_period = Column(String(100))  # "4th century CE", "16th century CE"
    authority = Column(String(200))  # "Council of Trent", "Ethiopian Orthodox Tewahedo Church"
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    versifications = relationship("Versification", back_populates="canon")

class Versification(Base):
    """
    Versification systems defining chapter/verse numbering schemes.
    Different manuscript traditions and editions have different verse numbering.
    """
    __tablename__ = "versifications"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), nullable=False, unique=True, index=True)  # MT, LXX, VUL, KJV, ETH
    name = Column(String(200), nullable=False)  # "Masoretic Text", "Septuagint", "King James"
    canon_id = Column(Integer, ForeignKey("canons.id"), nullable=False)
    description = Column(Text)
    
    # Versification metadata
    source_text = Column(String(100))  # "Masoretic Text", "Textus Receptus"
    manuscript_tradition = Column(String(100))  # "Byzantine", "Alexandrian", "Ethiopian"
    year_established = Column(Integer)  # When this versification was standardized
    is_default = Column(Boolean, default=False)  # Default versification for this canon
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    canon = relationship("Canon", back_populates="versifications")
    canonical_positions = relationship("CanonicalPosition", back_populates="versification")

class CanonicalPosition(Base):
    """
    Maps abstract verses to specific positions in different versifications.
    Handles 1:many and many:1 mappings for verses that are split or merged
    across different manuscript traditions.
    """
    __tablename__ = "canonical_positions"
    
    id = Column(Integer, primary_key=True, index=True)
    abstract_verse_id = Column(Integer, ForeignKey("abstract_verses.id"), nullable=False)
    versification_id = Column(Integer, ForeignKey("versifications.id"), nullable=False)
    
    # Position in this versification
    book = Column(String(50), nullable=False)
    chapter_start = Column(Integer, nullable=False)
    verse_start = Column(Integer, nullable=False)
    chapter_end = Column(Integer, nullable=True)  # For verses spanning multiple chapters
    verse_end = Column(Integer, nullable=True)    # For verses spanning multiple verses
    
    # Mapping metadata
    position_type = Column(String(20), default="exact")  # exact, split, merged, approximate
    confidence_score = Column(Float, default=1.0)  # 0.0 to 1.0 confidence in mapping
    mapping_notes = Column(Text)  # Scholarly notes about this mapping
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    abstract_verse = relationship("AbstractVerse", back_populates="canonical_positions")
    versification = relationship("Versification", back_populates="canonical_positions")
    
    # Indexes for efficient verse lookup
    __table_args__ = (
        Index("ix_canonical_positions_lookup", versification_id, book, chapter_start, verse_start),
        Index("ix_canonical_positions_abstract", abstract_verse_id),
    )

# ===============================================================================
# RESEARCH-GRADE SCHOLARLY PLATFORM MODELS
# ===============================================================================

class CrossReference(Base):
    """Graph layer for cross-references, intertextual links, and person/place networks"""
    __tablename__ = "cross_references"
    
    id = Column(Integer, primary_key=True, index=True)
    source_text_id = Column(Integer, ForeignKey("biblical_texts.id"), nullable=False)
    target_text_id = Column(Integer, ForeignKey("biblical_texts.id"), nullable=False)
    
    # Abstract Verse ID Architecture - Edition-agnostic cross-references
    source_abstract_id = Column(Integer, ForeignKey("abstract_verses.id"), nullable=True, index=True)
    target_abstract_id = Column(Integer, ForeignKey("abstract_verses.id"), nullable=True, index=True)
    
    # Relationship types for graph analysis
    reference_type = Column(String(50), nullable=False)  # quotation, allusion, parallel, thematic, etc.
    confidence_score = Column(Float, default=0.5)  # Scholarly confidence in connection
    scholarly_source = Column(String(200))  # Academic source identifying connection
    
    # Rich metadata for research
    description = Column(Text)  # Explanation of the connection
    linguistic_markers = Column(JSON)  # Language patterns that indicate connection
    thematic_keywords = Column(ARRAY(String))  # Shared themes or concepts
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships - Both text-based (legacy) and abstract (canonical)
    source_text = relationship("BiblicalText", foreign_keys=[source_text_id], back_populates="source_references")
    target_text = relationship("BiblicalText", foreign_keys=[target_text_id], back_populates="target_references")
    source_abstract_verse = relationship("AbstractVerse", foreign_keys=[source_abstract_id], back_populates="source_abstract_references")
    target_abstract_verse = relationship("AbstractVerse", foreign_keys=[target_abstract_id], back_populates="target_abstract_references")

class TextualVariant(Base):
    """Textual apparatus for critical notes and variant readings"""
    __tablename__ = "textual_variants"
    
    id = Column(Integer, primary_key=True, index=True)
    biblical_text_id = Column(Integer, ForeignKey("biblical_texts.id"), nullable=False)
    
    # Variant reading details
    variant_text = Column(Text, nullable=False)  # Alternative reading
    manuscript_evidence = Column(JSON)  # Manuscripts supporting this reading
    variant_type = Column(String(50))  # addition, omission, substitution, transposition
    
    # Critical apparatus information
    critical_notes = Column(Text)  # Scholarly commentary on variant
    probability_score = Column(Float)  # Likelihood this is original reading
    textual_tradition = Column(String(100))  # Byzantine, Alexandrian, Western, etc.
    
    # Source attribution
    editor_notes = Column(Text)  # Editorial commentary
    scholarly_consensus = Column(String(100))  # majority, minority, divided
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    biblical_text = relationship("BiblicalText", back_populates="textual_variants")

class InternationalizedText(Base):
    """Multi-language support for parallel Ge'ez/Amharic/English panes"""
    __tablename__ = "internationalized_texts"
    
    id = Column(Integer, primary_key=True, index=True)
    biblical_text_id = Column(Integer, ForeignKey("biblical_texts.id"), nullable=False)
    
    # Language and translation details
    language = Column(Enum(LanguageEnum), nullable=False)
    text_content = Column(Text, nullable=False)
    script_direction = Column(String(10), default="ltr")  # ltr, rtl for proper display
    
    # Cultural and liturgical context
    liturgical_use = Column(Text)  # How this text is used in worship
    cultural_notes = Column(Text)  # Cultural context and significance
    canonical_status = Column(String(50))  # canonical, deuterocanonical, apocryphal
    
    # Technical metadata
    transliteration = Column(Text)  # Romanized version for ancient languages
    phonetic_guide = Column(Text)  # Pronunciation guide
    encoding_notes = Column(Text)  # Technical notes about character encoding
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships  
    biblical_text = relationship("BiblicalText")

class PersonPlaceNetwork(Base):
    """Graph network for people and places across biblical texts"""
    __tablename__ = "person_place_networks"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Entity identification
    entity_name = Column(String(200), nullable=False)
    entity_type = Column(String(50), nullable=False)  # person, place, nation, tribe, etc.
    alternative_names = Column(ARRAY(String))  # Multiple name forms
    
    # Network properties
    centrality_score = Column(Float)  # Graph centrality measure
    occurrence_count = Column(Integer, default=0)  # How often mentioned
    first_occurrence = Column(String(50))  # First biblical mention
    last_occurrence = Column(String(50))  # Last biblical mention
    
    # Rich contextual data
    description = Column(Text)  # Historical/geographical description
    time_period = Column(String(100))  # Historical period
    geographical_region = Column(String(100))  # Broad geographical area
    
    # Research metadata
    scholarly_notes = Column(Text)  # Academic commentary
    related_entities = Column(JSON)  # Connected people/places with relationship types
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())