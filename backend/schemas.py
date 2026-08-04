# Liberation Bible Project - Pydantic Schemas

from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

class BiblicalTextResponse(BaseModel):
    id: int
    book: str
    chapter: int
    verse: int
    text: str
    translation: str
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class HistoricalNoteResponse(BaseModel):
    id: int
    biblical_text_id: int
    title: str
    content: str
    historical_period: Optional[str]
    source: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class GeographicalLocationResponse(BaseModel):
    id: int
    biblical_text_id: Optional[int]  # Made optional since our geographical data is standalone
    name: str
    modern_name: Optional[str]
    latitude: Optional[str]
    longitude: Optional[str]
    description: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class LanguageType(str, Enum):
    hebrew = "hebrew"
    greek = "greek"
    aramaic = "aramaic"

class OriginalWordResponse(BaseModel):
    text: str
    language: LanguageType
    strong_number: Optional[str]
    root: Optional[str]
    definition: str

    class Config:
        from_attributes = True

class WordWithOriginal(BaseModel):
    word: str
    original: Optional[OriginalWordResponse]

class TranslationBias(BaseModel):
    """Translation bias alert information"""
    detected: bool
    type: str
    message: str
    scholarly_note: Optional[str]

class TranslationText(BaseModel):
    text: str
    words: List[WordWithOriginal]
    bias_alert: Optional[TranslationBias] = None

class TextualComparisonResponse(BaseModel):
    book: str
    chapter: int
    verse: int
    translations: Dict[str, TranslationText]

# Sermon Analysis Schemas
class SermonAnalysisRequest(BaseModel):
    """Request schema for sermon analysis with audio file"""
    pass  # File will be handled by FastAPI's UploadFile

class TranscriptSegment(BaseModel):
    text: str
    timestamp: Optional[str] = None
    start: Optional[float] = None
    end: Optional[float] = None
    speaker: Optional[str] = None

class SermonSummary(BaseModel):
    topic: str
    theme: Optional[str] = None
    main_theme: Optional[str] = None
    short_summary: Optional[str] = None
    detailed_summary: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)
    conclusion: Optional[str] = None
    theological_framework: Optional[str] = None

class AccuracyClaim(BaseModel):
    statement: Optional[str] = None
    timestamp: Optional[str] = None
    claim_text: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    details: Optional[str] = None
    corrective_notes: Optional[str] = None
    issue_type: str
    severity: str
    explanation: str
    correction: str
    references: List[str] = Field(default_factory=list)

class VisualDashboardMetrics(BaseModel):
    accuracy_score: int
    scripture_usage_score: int
    context_score: int
    theology_consistency_score: int
    confidence_level: int

class SermonAnalysisResponse(BaseModel):
    """Response schema for sermon analysis results"""
    transcription: str
    transcript_segments: List[TranscriptSegment]
    summary: SermonSummary
    metrics: VisualDashboardMetrics
    claims: List[AccuracyClaim]
    further_study: List[str]
    processing_time: float

class CulturalContextRequest(BaseModel):
    """Request schema for cultural context lookup"""
    biblical_passage: str

class CulturalContextResponse(BaseModel):
    """Response schema for cultural context suggestions"""
    passage: str
    original_context: str
    cultural_practices: List[str]
    language_insights: str
    liberation_perspective: str
    additional_resources: List[str]

class TranslationBiasResponse(BaseModel):
    id: int
    book: str
    chapter: int
    verse: int
    severity: str
    title: str
    original: Optional[str] = None
    literal: Optional[str] = None
    target_translation: Optional[str] = None
    target_text: Optional[str] = None
    explanation: str
    scholar: Optional[str] = None

    class Config:
        from_attributes = True

class DynamicBiasAuditRequest(BaseModel):
    book: str
    chapter: int
    verse: int

class DynamicBiasAuditResponse(BaseModel):
    detected: bool
    severity: str
    title: str
    original: Optional[str] = None
    literal: Optional[str] = None
    target_translation: Optional[str] = None
    target_text: Optional[str] = None
    explanation: str
    scholar: Optional[str] = None
    translations: Optional[Dict[str, str]] = None

class VerseDetailsResponse(BaseModel):
    """Complete verse details with all translations, historical context, and cross-references"""
    book: str
    chapter: int
    verse: int
    translations: Dict[str, str]  # translation_name -> verse_text
    verse_meaning: str
    translation_comparison: str
    critical_analysis: Optional[str] = ""
    historical_context: List[HistoricalNoteResponse]
    geographical_context: List[GeographicalLocationResponse]
    original_language_insights: List[OriginalWordResponse]
    cross_references: List[Dict[str, str]]  # [{"book": "Matthew", "chapter": "5", "verse": "16", "text": "..."}]
    translation_bias_alerts: List[TranslationBiasResponse] = Field(default_factory=list)
    race_misuse_records: List[Dict[str, Any]] = Field(default_factory=list)
    
    class Config:
        from_attributes = True

# Chat request and response schemas
class ChatRequest(BaseModel):
    question: str
    history: Optional[List[Dict[str, str]]] = None
    study_mode: Optional[str] = "scholarly"

class ChatResponse(BaseModel):
    answer: str
    context_used: List[str]
    follow_ups: List[str]

# Abstract Verse ID Architecture Schemas
class AbstractVerseResponse(BaseModel):
    """Response model for abstract verse entities"""
    id: int
    canonical_key: str
    content_hash: Optional[str]
    notes: Optional[Dict]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class CanonResponse(BaseModel):
    """Response model for biblical canons"""
    id: int
    code: str
    name: str
    description: Optional[str]
    book_count: Optional[int]
    language_tradition: Optional[str]
    historical_period: Optional[str]
    authority: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class VersificationResponse(BaseModel):
    """Response model for versification systems"""
    id: int
    code: str
    name: str
    canon_id: int
    description: Optional[str]
    source_text: Optional[str]
    manuscript_tradition: Optional[str]
    year_established: Optional[int]
    is_default: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class CanonicalPositionResponse(BaseModel):
    """Response model for canonical positions"""
    id: int
    abstract_verse_id: int
    versification_id: int
    book: str
    chapter_start: int
    verse_start: int
    chapter_end: Optional[int]
    verse_end: Optional[int]
    position_type: str
    confidence_score: float
    mapping_notes: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class VerseResolveRequest(BaseModel):
    """Request schema for verse resolution"""
    canon: Optional[str] = None
    versification: Optional[str] = None
    book: str
    chapter: int
    verse: int

class VerseResolveResponse(BaseModel):
    """Response schema for verse resolution"""
    abstract_verse_id: int
    canonical_key: str
    positions: List[CanonicalPositionResponse]
    available_translations: List[Dict[str, str]]  # [{"translation": "KJV", "text": "..."}]

class AbstractVerseDetailsResponse(BaseModel):
    """Complete details for an abstract verse across all available versifications"""
    abstract_verse: AbstractVerseResponse
    canonical_positions: List[CanonicalPositionResponse]
    translations: Dict[str, str]  # translation_code -> verse_text
    cross_references: List[Dict[str, str]]  # Related verses via abstract IDs
    historical_context: List[HistoricalNoteResponse]
    geographical_context: List[GeographicalLocationResponse]
    versification_differences: Dict[str, List[Dict[str, str]]]  # Differences across versifications

class CrossVersificationMappingResponse(BaseModel):
    """Response showing how a verse maps across different versifications"""
    source_reference: Dict[str, str]  # {"versification": "KJV", "book": "Genesis", "chapter": 1, "verse": 1}
    abstract_verse_id: int
    mappings: Dict[str, List[Dict[str, int]]]  # versification_code -> [{"book": "Genesis", "chapter": 1, "verse": 1}]
    
class MultiCanonSearchResponse(BaseModel):
    """Response for searches across multiple canonical traditions"""
    query: str
    results: List[Dict[str, Any]]  # Results from different canons
    canon_availability: Dict[str, bool]  # Which canons have this content

# RAG (Retrieval-Augmented Generation) Schemas
class QuestionTypeEnum(str, Enum):
    """Types of biblical questions"""
    location = "location"
    person = "person"
    conceptual = "conceptual"
    historical = "historical"
    textual = "textual"
    general = "general"

class RAGRequest(BaseModel):
    """Request schema for Q&A questions"""
    question: str
    context_limit: Optional[int] = 10
    include_related_queries: Optional[bool] = True

class BiblicalPassageResult(BaseModel):
    """Biblical passage in search results"""
    id: int
    reference: str  # "Genesis 1:1"
    book: str
    chapter: int
    verse: int
    text: str
    translation: str
    similarity_score: float

class HistoricalContextResult(BaseModel):
    """Historical context result"""
    title: str
    content: str
    period: Optional[str]
    source: Optional[str]

class GeographicalResult(BaseModel):
    """Geographical location result"""
    ancient_name: str
    modern_name: Optional[str]
    coordinates: Optional[List[float]]  # [latitude, longitude]
    description: Optional[str]
    confidence: Optional[float]

class LexiconResult(BaseModel):
    """Original language lexicon result"""
    word: str
    language: str
    definition: str
    transliteration: Optional[str]
    strong_number: Optional[str]

class RAGResponse(BaseModel):
    """Comprehensive response from RAG system"""
    question: str
    answer: str
    question_type: QuestionTypeEnum
    biblical_passages: List[BiblicalPassageResult]
    historical_context: List[HistoricalContextResult]
    geographical_data: List[GeographicalResult]
    lexicon_insights: List[LexiconResult]
    related_queries: List[str]
    confidence_score: float
    processing_time: float

class QuerySuggestionsResponse(BaseModel):
    """Suggested queries based on available data"""
    location_queries: List[str]
    person_queries: List[str]
    conceptual_queries: List[str]
    historical_queries: List[str]
    featured_query: str

class UserNoteBase(BaseModel):
    book: Optional[str] = None
    chapter: Optional[int] = None
    verse: Optional[int] = None
    text: str
    tags: List[str] = Field(default_factory=list)

class UserNoteCreate(UserNoteBase):
    pass

class UserNoteUpdate(BaseModel):
    text: Optional[str] = None
    tags: Optional[List[str]] = None

class UserNoteResponse(UserNoteBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class CanonCompareItem(BaseModel):
    book_id: str
    name: str
    testament: str
    in_canons: List[str]
    notes: Optional[str] = None
    significance: Optional[str] = None

class CanonCompareResponse(BaseModel):
    books: List[CanonCompareItem]

class BookDetailResponse(BaseModel):
    id: str
    name: str
    testament: str
    description: Optional[str] = None
    geez_name: Optional[str] = None
    canonical_order: int
    canon_inclusions: List[str]

class RaceMisuseRecordResponse(BaseModel):
    id: int
    book: str
    chapter: int
    verse: int
    severity: str
    title: str
    historical_misuse: str
    harm_caused: Optional[str] = None
    corrective_interpretation: str
    decolonial_perspective: Optional[str] = None
    ethiopian_perspective: Optional[str] = None
    study_notes: Optional[str] = None

class FactbookEntrySummary(BaseModel):
    slug: str
    title: str
    summary: str
    geographical_region: Optional[str] = None

class ManuscriptWitnessResponse(BaseModel):
    id: int
    name: str
    type: Optional[str] = None
    date: Optional[str] = None
    language: Optional[str] = None
    significance: Optional[str] = None

class FactbookEntryDetailResponse(BaseModel):
    slug: str
    title: str
    summary: str
    content: Optional[str] = None
    geographical_region: Optional[str] = None
    ethiopian_canon_relevance: Optional[str] = None
    manuscripts_attestations: Optional[str] = None
    western_interpretation: Optional[str] = None
    ethiopian_interpretation: Optional[str] = None
    decolonial_interpretation: Optional[str] = None
    witnesses: List[ManuscriptWitnessResponse] = Field(default_factory=list)

class StudySessionResponse(BaseModel):
    id: int
    title: str
    notes: Optional[str] = None
    meta_data: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class StudySessionCreate(BaseModel):
    title: str
    notes: Optional[str] = None
    meta_data: Optional[Dict[str, Any]] = None
