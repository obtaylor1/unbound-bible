# Liberation Bible Project - Pydantic Schemas

from pydantic import BaseModel
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

class SermonAnalysisResponse(BaseModel):
    """Response schema for sermon analysis results"""
    transcription: str
    biblical_themes: List[str]
    referenced_passages: List[str]
    historical_connections: List[str]
    cultural_significance: str
    accuracy_assessment: str
    suggestions: List[str]
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

class VerseDetailsResponse(BaseModel):
    """Complete verse details with all translations, historical context, and cross-references"""
    book: str
    chapter: int
    verse: int
    translations: Dict[str, str]  # translation_name -> verse_text
    verse_meaning: str
    translation_comparison: str
    historical_context: List[HistoricalNoteResponse]
    geographical_context: List[GeographicalLocationResponse]
    original_language_insights: List[OriginalWordResponse]
    cross_references: List[Dict[str, str]]  # [{"book": "Matthew", "chapter": "5", "verse": "16", "text": "..."}]
    
    class Config:
        from_attributes = True

# Chat request and response schemas
class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer: str
    context_used: List[str]

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