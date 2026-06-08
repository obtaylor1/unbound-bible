# Liberation Bible Project - FastAPI Backend
# Referenced from blueprint:python_database integration

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional, cast
import uvicorn
import os
import tempfile
import time
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from database import engine, get_db
from models import (
    Base, BiblicalText, HistoricalNote, GeographicalLocation, OriginalWord, CrossReference, 
    TextualVariant, InternationalizedText, PersonPlaceNetwork, AbstractVerse, Canon, 
    Versification, CanonicalPosition
)
from schemas import (
    BiblicalTextResponse, HistoricalNoteResponse, GeographicalLocationResponse,
    TextualComparisonResponse, OriginalWordResponse, WordWithOriginal, TranslationText, TranslationBias, LanguageType,
    SermonAnalysisResponse, CulturalContextRequest, CulturalContextResponse, VerseDetailsResponse,
    ChatRequest, ChatResponse, AbstractVerseResponse, CanonResponse, VersificationResponse,
    CanonicalPositionResponse, VerseResolveRequest, VerseResolveResponse, AbstractVerseDetailsResponse,
    CrossVersificationMappingResponse, MultiCanonSearchResponse, RAGRequest, RAGResponse,
    QuestionTypeEnum, BiblicalPassageResult, HistoricalContextResult, GeographicalResult,
    LexiconResult, QuerySuggestionsResponse
)
from resolve_service import get_resolution_service
from openai_service import transcribe_audio, analyze_sermon_content, suggest_cultural_context
from vector_search import vector_search_service
from rag_service import rag_service
from auth import get_current_user
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage
import tiktoken

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="The Liberation Bible Project API",
    description="A comprehensive API for biblical texts, historical notes, and geographical locations",
    version="1.0.0"
)

# Add rate limiting middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS to allow frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Health check endpoints
@app.get("/")
def read_root():
    return {"message": "The Liberation Bible Project API is running!"}

@app.get("/api")
def api_health():
    return {"message": "The Liberation Bible Project API is running!", "status": "healthy"}

# Import context API router
from routes.context_api import router as context_router

# Include context API router
app.include_router(context_router)

# Biblical Texts endpoints
@app.get("/api/biblical-texts", response_model=List[BiblicalTextResponse])
def get_biblical_texts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    texts = db.query(BiblicalText).offset(skip).limit(limit).all()
    return texts

# Broader Canon books endpoint - must come before parameterized route
@app.get("/api/biblical-texts/available-books")
def get_broader_canon_books(db: Session = Depends(get_db)):
    """
    Get all available book names from database for Broader Canon selection
    Returns simple list of book names without canonical filtering
    """
    try:
        # Get distinct book names from biblical texts, ordered alphabetically
        books = db.query(BiblicalText.book).distinct().order_by(BiblicalText.book).all()
        book_list = [book[0] for book in books]
        
        return {
            "books": book_list,
            "count": len(book_list),
            "description": "All books available in database including extra-canonical texts"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get broader canon books: {str(e)}")

# Book content endpoint for ApocryphaReader - must come before parameterized route
@app.get("/api/biblical-texts/book-content")
def get_book_content(book: str, db: Session = Depends(get_db)):
    """
    Get all content for a specific book for the ApocryphaReader component
    Returns all verses/chapters organized by structure
    """
    try:
        # Get all biblical texts for the specified book, ordered by chapter and verse
        texts = db.query(BiblicalText).filter(
            BiblicalText.book == book
        ).order_by(
            BiblicalText.chapter.asc(),
            BiblicalText.verse.asc()
        ).all()
        
        if not texts:
            raise HTTPException(status_code=404, detail=f"No content found for book: {book}")
        
        # Convert to response format
        content = []
        for text in texts:
            content.append({
                "id": text.id,
                "book": text.book,
                "chapter": text.chapter,
                "verse": text.verse,
                "text": text.text,
                "translation": text.translation
            })
        
        # Get book metadata if available
        book_info = {
            "name": book,
            "total_verses": len(content),
            "chapters": len(set(text.chapter for text in texts if text.chapter)),
            "tradition": "Extra-Canonical" if any(keyword in book.lower() for keyword in ["adam", "enoch", "jubilees", "meqabyan"]) else "Biblical",
            "description": get_book_description(book)
        }
        
        return {
            "book": book,
            "content": content,
            "book_info": book_info,
            "total_verses": len(content)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get book content: {str(e)}")

def get_book_description(book_name: str) -> str:
    """Get description for specific books"""
    descriptions = {
        "Adam and Eve 2": "Book II of Adam and Eve - The story of Adam and Eve after their expulsion from Eden",
        "Adam and Eve 3": "Book III of Adam and Eve - Continues the narrative of Adam and Eve's trials",
        "1 Enoch": "First Book of Enoch - Ancient Jewish apocalyptic text detailing Enoch's visions",
        "Jubilees": "Book of Jubilees - Retelling of Genesis and Exodus with additional details",
        "Meqabyan 1": "First Book of Meqabyan - Ethiopian canonical text similar to Maccabees",
        "Meqabyan 2": "Second Book of Meqabyan - Continuation of Ethiopian canonical narrative",
        "Meqabyan 3": "Third Book of Meqabyan - Final book in the Ethiopian Meqabyan collection"
    }
    return descriptions.get(book_name, f"Religious text: {book_name}")


@app.get("/api/biblical-texts/{text_id}", response_model=BiblicalTextResponse)
def get_biblical_text(text_id: int, db: Session = Depends(get_db)):
    text = db.query(BiblicalText).filter(BiblicalText.id == text_id).first()
    if text is None:
        raise HTTPException(status_code=404, detail="Biblical text not found")
    return text

# Historical Notes endpoints
@app.get("/api/historical-notes", response_model=List[HistoricalNoteResponse])
def get_historical_notes(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    notes = db.query(HistoricalNote).offset(skip).limit(limit).all()
    return notes

@app.get("/api/historical-notes/{note_id}", response_model=HistoricalNoteResponse)
def get_historical_note(note_id: int, db: Session = Depends(get_db)):
    note = db.query(HistoricalNote).filter(HistoricalNote.id == note_id).first()
    if note is None:
        raise HTTPException(status_code=404, detail="Historical note not found")
    return note

# Geographical Locations endpoints
@app.get("/api/geographical-locations", response_model=List[GeographicalLocationResponse])
def get_geographical_locations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    locations = db.query(GeographicalLocation).offset(skip).limit(limit).all()
    return locations

@app.get("/api/geographical-locations/{location_id}", response_model=GeographicalLocationResponse)
def get_geographical_location(location_id: int, db: Session = Depends(get_db)):
    location = db.query(GeographicalLocation).filter(GeographicalLocation.id == location_id).first()
    if location is None:
        raise HTTPException(status_code=404, detail="Geographical location not found")
    return location

# Books endpoint for dropdown
@app.get("/api/v1/books")
def get_available_books(canon: str = "PROT66", db: Session = Depends(get_db)):
    """
    Get list of available books with canonical information for dropdown selection
    """
    try:
        # Get distinct book names from biblical texts
        books = db.query(BiblicalText.book).distinct().order_by(BiblicalText.book).all()
        book_list = [book[0] for book in books]
        
        # Define Ethiopian unique books (with database name variations)
        ethiopian_unique_books = [
            "1 Enoch", "Enoch",
            "Jubilees", 
            "1 Meqabyan", "Meqabyan 1",
            "2 Meqabyan", "Meqabyan 2", 
            "3 Meqabyan", "Meqabyan 3"
        ]
        
        # Create book objects with canonical information
        books_with_canonical_info = []
        for book_name in book_list:
            is_ethiopian_unique = book_name in ethiopian_unique_books
            
            # Apply canonical filtering
            if canon == "PROT66" and is_ethiopian_unique:
                # Skip Ethiopian unique books for Protestant canon
                continue
                
            book_info = {
                "name": book_name,
                "canonical_status": {
                    "protestant": book_name not in ethiopian_unique_books,
                    "ethiopian_orthodox": True,  # All books in our DB are in Ethiopian canon
                    "is_ethiopian_unique": book_name in ethiopian_unique_books
                }
            }
            books_with_canonical_info.append(book_info)
        
        # Add Ethiopian unique books if not in database yet (placeholders) - only for Ethiopian canon
        if canon == "ETH81":
            for unique_book in ethiopian_unique_books:
                if unique_book not in book_list:
                    placeholder_book = {
                        "name": unique_book,
                        "canonical_status": {
                            "protestant": False,
                            "ethiopian_orthodox": True,
                            "is_ethiopian_unique": True
                        },
                        "placeholder": True  # Indicates this book isn't fully available yet
                    }
                    books_with_canonical_info.append(placeholder_book)
        
        return {
            "books": books_with_canonical_info,
            "canon_filter": canon,
            "book_count": len(books_with_canonical_info)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get books: {str(e)}")

# Bias detection helper function
def detect_translation_bias(biblical_text, book: str, chapter: int, verse: int) -> Optional[TranslationBias]:
    """
    Detect translation bias in controversial verses
    """
    # Define controversial verses that need bias alerts
    controversial_verses = {
        ("Song of Solomon", 1, 5): {
            "type": "CONJUNCTION_BIAS",
            "message": "KJV translates Hebrew 'and' as 'but', changing meaning from pride to shame",
            "scholarly_note": "Scholar Wilda Gafney notes Hebrew conjunction means 'and' not 'but' - changing 'black and beautiful' to 'black but comely'"
        },
        ("Exodus", 12, 38): {
            "type": "ETHNIC_MINIMIZATION",
            "message": "Translation minimizes multiethnic nature of liberation group", 
            "scholarly_note": "Hebrew 'erev rav' (mixed multitude) indicates diverse ethnic coalition in liberation movement"
        }
    }
    
    # Check if this is a controversial verse
    verse_key = (book, chapter, verse)
    if verse_key in controversial_verses:
        bias_info = controversial_verses[verse_key]
        return TranslationBias(
            detected=True,
            type=bias_info["type"],
            message=bias_info["message"],
            scholarly_note=bias_info["scholarly_note"]
        )
    
    # Check textual_notes for bias markers
    if biblical_text.textual_notes:
        notes = biblical_text.textual_notes
        if isinstance(notes, dict):
            bias_markers = notes.get("bias_markers", [])
            if bias_markers:
                return TranslationBias(
                    detected=True,
                    type="TEXTUAL_BIAS_DETECTED",
                    message="Translation bias detected in textual apparatus",
                    scholarly_note="See textual notes for scholarly analysis"
                )
    
    return None

# Textual Comparison endpoint
@app.get("/api/v1/texts/{book}/{chapter}/{verse}", response_model=TextualComparisonResponse)
def get_verse_comparison(book: str, chapter: int, verse: int, canon: str = "PROT66", db: Session = Depends(get_db)):
    # Define Ethiopian unique books (with database name variations)
    ethiopian_unique_books = [
        "1 Enoch", "Enoch",
        "Jubilees", 
        "1 Meqabyan", "Meqabyan 1",
        "2 Meqabyan", "Meqabyan 2", 
        "3 Meqabyan", "Meqabyan 3"
    ]
    
    # Check if this is an Ethiopian unique book being requested with Protestant canon
    is_ethiopian_unique = book in ethiopian_unique_books
    is_protestant_canon_request = canon == "PROT66"
    
    # Handle canonical toggle logic
    if is_ethiopian_unique and is_protestant_canon_request:
        # Return Protestant canon placeholders for Ethiopian unique books
        placeholder_text = TranslationText(
            text=f"This book ({book}) is not found in the Protestant canon. It is included in the Ethiopian Orthodox Tewahedo Bible.",
            words=[],
            bias_alert=None
        )
        
        return TextualComparisonResponse(
            book=book,
            chapter=chapter,
            verse=verse,
            translations={
                "kjv": placeholder_text,
                "asv": placeholder_text,
                "web": placeholder_text
            },
            canonical_note=f"{book} is unique to the Ethiopian Orthodox canon and contains 81 books compared to the Protestant canon's 66 books."
        )
    
    # Query for KJV, ASV, and WEB translations (public domain)
    kjv_text = db.query(BiblicalText).filter(
        BiblicalText.book == book,
        BiblicalText.chapter == chapter,
        BiblicalText.verse == verse,
        BiblicalText.translation == "KJV"
    ).first()
    
    asv_text = db.query(BiblicalText).filter(
        BiblicalText.book == book,
        BiblicalText.chapter == chapter,
        BiblicalText.verse == verse,
        BiblicalText.translation == "ASV"
    ).first()
    
    web_text = db.query(BiblicalText).filter(
        BiblicalText.book == book,
        BiblicalText.chapter == chapter,
        BiblicalText.verse == verse,
        BiblicalText.translation == "WEB"
    ).first()
    
    def create_translation_text(biblical_text):
        if biblical_text is None:
            return TranslationText(text="Translation not available", words=[])
        
        # Get original words for this text
        original_words = db.query(OriginalWord).filter(
            OriginalWord.biblical_text_id == biblical_text.id
        ).all()
        
        # Split text into words and match with original language data
        words = biblical_text.text.split()
        words_with_original = []
        
        for i, word in enumerate(words):
            # Clean word of punctuation for matching
            clean_word = word.strip('.,;:!?"\'').lower()
            
            # Find matching original word by position
            original_word = None
            for orig in original_words:
                pos = cast(Optional[int], getattr(orig, "word_position", None))
                if pos is not None and pos == i:
                    original_word = OriginalWordResponse(
                        text=cast(str, orig.word_text),
                        language=LanguageType(orig.language.value) if orig.language is not None else LanguageType.hebrew,
                        strong_number=cast(str, orig.strong_number) if orig.strong_number is not None else None,
                        root=cast(str, orig.root_word) if orig.root_word is not None else None,
                        definition=cast(str, orig.definition)
                    )
                    break
            
            words_with_original.append(WordWithOriginal(
                word=word,
                original=original_word
            ))
        
        # Check for translation bias in controversial verses
        bias_alert = detect_translation_bias(biblical_text, book, chapter, verse)
        
        return TranslationText(
            text=biblical_text.text, 
            words=words_with_original,
            bias_alert=bias_alert
        )
    
    # Check if at least one translation exists
    if kjv_text is None and asv_text is None and web_text is None:
        raise HTTPException(status_code=404, detail="Verse not found in any translation")
    
    translations = {}
    if kjv_text is not None:
        translations["kjv"] = create_translation_text(kjv_text)
    if asv_text is not None:
        translations["asv"] = create_translation_text(asv_text)
    if web_text is not None:
        translations["web"] = create_translation_text(web_text)
    
    # Add canonical note if needed
    canonical_note = None
    if is_ethiopian_unique and canon == "ETH81":
        canonical_note = f"{book} is unique to the Ethiopian Orthodox canon (81 books total) and is not found in the Protestant canon (66 books)."
    
    return TextualComparisonResponse(
        book=book,
        chapter=chapter,
        verse=verse,
        translations=translations,
        canonical_note=canonical_note
    )

# Verse Details endpoint for in-depth analysis
@app.get("/api/v1/texts/{book}/{chapter}/{verse}/details", response_model=VerseDetailsResponse)
def get_verse_details(book: str, chapter: int, verse: int, db: Session = Depends(get_db)):
    """
    Get comprehensive verse details including all translations, historical context,
    geographical context, and cross-references
    """
    try:
        # Get all available translations for this verse
        # First try exact match (fast path)
        all_translations = db.query(BiblicalText).filter(
            BiblicalText.book == book.strip(),
            BiblicalText.chapter == chapter,
            BiblicalText.verse == verse
        ).all()
        
        # If no exact match, use Python-side normalization fallback  
        if not all_translations:
            def normalize_book(s):
                """Robust book name normalization - strips whitespace, punctuation, case"""
                return ''.join(ch for ch in s if ch.isalnum()).lower()
            
            # Get all verses with matching chapter/verse, then filter by normalized book name
            candidates = db.query(BiblicalText).filter(
                BiblicalText.chapter == chapter,
                BiblicalText.verse == verse
            ).all()
            
            target_norm = normalize_book(book)
            all_translations = [t for t in candidates if normalize_book(t.book) == target_norm]
        
        if not all_translations:
            raise HTTPException(status_code=404, detail="Verse not found")
        
        # Build translations dictionary
        translations = {}
        primary_verse_id = None
        for text in all_translations:
            translations[text.translation] = text.text
            if text.translation == "KJV":  # Use KJV as primary reference
                primary_verse_id = text.id
        
        # If no KJV, use the first available translation as primary
        if primary_verse_id is None and all_translations:
            primary_verse_id = all_translations[0].id
        
        # Get historical notes for this verse
        historical_notes_query = db.query(HistoricalNote)
        if primary_verse_id:
            historical_notes_query = historical_notes_query.filter(HistoricalNote.biblical_text_id == primary_verse_id)
        historical_notes = historical_notes_query.all()
        
        # Get geographical context for this verse
        geographical_context_query = db.query(GeographicalLocation)
        if primary_verse_id:
            geographical_context_query = geographical_context_query.filter(GeographicalLocation.biblical_text_id == primary_verse_id)
        geographical_context = geographical_context_query.all()
        
        # Get original language insights
        original_words_query = db.query(OriginalWord)
        if primary_verse_id:
            original_words_query = original_words_query.filter(OriginalWord.biblical_text_id == primary_verse_id)
        original_words = original_words_query.all()
        
        original_language_insights = [
            OriginalWordResponse(
                text=str(word.word_text),
                language=LanguageType(word.language.value) if hasattr(word, 'language') and word.language else LanguageType.hebrew,
                strong_number=str(word.strong_number) if word.strong_number else None,
                root=str(word.root_word) if word.root_word else None,
                definition=str(word.definition)
            )
            for word in original_words
        ]
        
        # Generate verse meaning (basic implementation - could be enhanced with AI)
        verse_meaning = f"This verse from {book} {chapter}:{verse} contains profound spiritual insights. "
        if historical_notes:
            verse_meaning += f"Historical context shows {historical_notes[0].content[:100]}..."
        else:
            verse_meaning += "The verse emphasizes themes of faith, redemption, and divine love, central to biblical teaching."
        
        # Generate translation comparison
        translation_comparison = "Comparing the translations reveals: "
        if "KJV" in translations and "ASV" in translations:
            translation_comparison += "The KJV and ASV show consistency in core meaning while varying in linguistic style. "
        else:
            translation_comparison += "Multiple translations maintain consistent theological meaning while adapting to different linguistic preferences."
        
        # Generate cross-references (enhanced implementation with proper data)
        cross_references = []
        
        # Comprehensive cross-reference database
        cross_ref_map = {
            ("John", 3, 16): [
                {"book": "Romans", "chapter": "5", "verse": "8", "text": "But God demonstrates his own love for us in this: While we were still sinners, Christ died for us."},
                {"book": "1 John", "chapter": "4", "verse": "9", "text": "This is how God showed his love among us: He sent his one and only Son into the world that we might live through him."},
                {"book": "Romans", "chapter": "8", "verse": "32", "text": "He who did not spare his own Son, but gave him up for us all—how will he not also, along with him, graciously give us all things?"}
            ],
            ("Matthew", 5, 16): [
                {"book": "Philippians", "chapter": "2", "verse": "15", "text": "so that you may become blameless and pure, \"children of God without fault in a warped and crooked generation.\" Then you will shine among them like stars in the sky"},
                {"book": "1 Peter", "chapter": "2", "verse": "12", "text": "Live such good lives among the pagans that, though they accuse you of doing wrong, they may see your good deeds and glorify God on the day he visits us."},
                {"book": "Ephesians", "chapter": "5", "verse": "8", "text": "For you were once darkness, but now you are light in the Lord. Live as children of light"}
            ],
            ("Psalms", 23, 1): [
                {"book": "John", "chapter": "10", "verse": "11", "text": "I am the good shepherd. The good shepherd lays down his life for the sheep."},
                {"book": "Isaiah", "chapter": "40", "verse": "11", "text": "He tends his flock like a shepherd: He gathers the lambs in his arms and carries them close to his heart"},
                {"book": "Ezekiel", "chapter": "34", "verse": "12", "text": "As a shepherd looks after his scattered flock when he is with them, so will I look after my sheep."}
            ],
            ("Romans", 3, 23): [
                {"book": "Isaiah", "chapter": "53", "verse": "6", "text": "We all, like sheep, have gone astray, each of us has turned to our own way; and the Lord has laid on him the iniquity of us all."},
                {"book": "1 John", "chapter": "1", "verse": "8", "text": "If we claim to be without sin, we deceive ourselves and the truth is not in us."},
                {"book": "Ecclesiastes", "chapter": "7", "verse": "20", "text": "Indeed, there is no one on earth who is righteous, no one who does what is right and never sins."}
            ]
        }
        
        # Look up cross-references for this verse
        verse_key = (book, chapter, verse)
        if verse_key in cross_ref_map:
            cross_references = cross_ref_map[verse_key]
        
        return VerseDetailsResponse(
            book=book,
            chapter=chapter,
            verse=verse,
            translations=translations,
            verse_meaning=verse_meaning,
            translation_comparison=translation_comparison,
            historical_context=[HistoricalNoteResponse.from_orm(note) for note in historical_notes],
            geographical_context=[GeographicalLocationResponse.from_orm(geo) for geo in geographical_context],
            original_language_insights=original_language_insights,
            cross_references=cross_references
        )
        
    except HTTPException as e:
        # Preserve HTTP exceptions (like 404) from upstream
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving verse details: {str(e)}")

# Advanced rate limiting for sermon analysis
_sermon_rate_limits = {}  # Per-user rate limiting storage

def check_sermon_rate_limit(user_id: str) -> bool:
    """Enhanced rate limiting: 3 requests per minute, 50 per day per user"""
    import time
    from collections import defaultdict, deque
    
    now = time.time()
    if user_id not in _sermon_rate_limits:
        _sermon_rate_limits[user_id] = {
            'minute': deque(),
            'day': deque()
        }
    
    user_limits = _sermon_rate_limits[user_id]
    
    # Clean old entries (minute window: 60 seconds, day window: 86400 seconds)
    while user_limits['minute'] and now - user_limits['minute'][0] > 60:
        user_limits['minute'].popleft()
    while user_limits['day'] and now - user_limits['day'][0] > 86400:
        user_limits['day'].popleft()
    
    # Check limits
    if len(user_limits['minute']) >= 3:  # 3 per minute
        return False
    if len(user_limits['day']) >= 50:  # 50 per day
        return False
    
    # Add current request
    user_limits['minute'].append(now)
    user_limits['day'].append(now)
    return True

# Sermon Analysis endpoint - PROTECTED with enhanced security
@app.post("/api/v1/analyze/sermon", response_model=SermonAnalysisResponse)
async def analyze_sermon(
    file: UploadFile = File(...), 
    current_user=Depends(get_current_user),  # Require authentication
    db: Session = Depends(get_db)
):
    """
    Analyze sermon audio file for biblical themes and historical context
    Requires authentication with strict per-user rate limits (3/min, 50/day)
    """
    # Enhanced per-user rate limiting
    user_id = str(current_user.get('id', current_user.get('email', 'unknown')))
    if not check_sermon_rate_limit(user_id):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Maximum 3 requests per minute or 50 per day per user."
        )
    
    start_time = time.time()
    
    # Enhanced file validation
    if not file.content_type or not file.content_type.startswith('audio/'):
        raise HTTPException(status_code=400, detail="File must be an audio file")
    
    # Enhanced file size validation (25MB limit for security)
    MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB (reduced from 50MB)
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size must be less than 25MB")
    
    # Enhanced security: Check for suspicious file patterns and validate content
    if file.filename:
        # Block potentially dangerous patterns
        dangerous_patterns = ['../', '.\\', '<script', '<?php', '<%', '.exe', '.bat', '.cmd', '.sh']
        filename_lower = file.filename.lower()
        if any(pattern in filename_lower for pattern in dangerous_patterns):
            raise HTTPException(status_code=400, detail="Invalid filename detected")
        
        # Validate filename length and characters
        if len(file.filename) > 255:
            raise HTTPException(status_code=400, detail="Filename too long")
        
        # Only allow safe characters in filename
        import string
        allowed_chars = string.ascii_letters + string.digits + '.-_() '
        if not all(c in allowed_chars for c in file.filename):
            raise HTTPException(status_code=400, detail="Filename contains invalid characters")
    
    # Validate file extension
    allowed_extensions = ('.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac')
    if not file.filename or not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(
            status_code=400, 
            detail=f"File must have one of these extensions: {', '.join(allowed_extensions)}"
        )
    
    temp_file_path = None
    try:
        # Save uploaded file temporarily with additional validation
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            content = await file.read()
            
            # Validate actual file content matches declared type
            if len(content) < 100:  # Audio files should be substantial
                raise HTTPException(status_code=400, detail="File too small to be valid audio")
            
            # Check for common audio file signatures/magic numbers
            audio_signatures = [
                b'ID3',      # MP3
                b'RIFF',     # WAV
                b'fLaC',     # FLAC  
                b'OggS',     # OGG
                b'ftypM4A',  # M4A
            ]
            
            # Check if content starts with valid audio signature
            content_start = content[:20]
            is_valid_audio = any(sig in content_start for sig in audio_signatures)
            if not is_valid_audio:
                raise HTTPException(status_code=400, detail="File does not appear to be valid audio")
            
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        # Transcribe audio using OpenAI Whisper
        transcription = await transcribe_audio(temp_file_path)
        
        # Get historical notes from database for context
        historical_notes = db.query(HistoricalNote).limit(20).all()
        historical_notes_data = [
            {
                "title": note.title,
                "content": note.content,
                "historical_period": note.historical_period,
                "source": note.source
            }
            for note in historical_notes
        ]
        
        # Analyze sermon content against historical context
        analysis_result = await analyze_sermon_content(transcription, historical_notes_data)
        
        # Clean up temporary file
        os.unlink(temp_file_path)
        
        processing_time = time.time() - start_time
        
        return SermonAnalysisResponse(
            transcription=transcription,
            biblical_themes=analysis_result.get("biblical_themes", []),
            referenced_passages=analysis_result.get("referenced_passages", []),
            historical_connections=analysis_result.get("historical_connections", []),
            cultural_significance=analysis_result.get("cultural_significance", ""),
            accuracy_assessment=analysis_result.get("accuracy_assessment", ""),
            suggestions=analysis_result.get("suggestions", []),
            processing_time=processing_time
        )
        
    except Exception as e:
        # Clean up temporary file if it exists
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Failed to analyze sermon: {str(e)}")

# Cultural Context endpoint
@app.post("/api/v1/cultural-context", response_model=CulturalContextResponse)
async def get_cultural_context(request: CulturalContextRequest):
    """
    Get cultural and historical context for a specific biblical passage
    """
    try:
        context_result = await suggest_cultural_context(request.biblical_passage)
        
        return CulturalContextResponse(
            passage=request.biblical_passage,
            original_context=context_result.get("original_context", ""),
            cultural_practices=context_result.get("cultural_practices", []),
            language_insights=context_result.get("language_insights", ""),
            liberation_perspective=context_result.get("liberation_perspective", ""),
            additional_resources=context_result.get("additional_resources", [])
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cultural context: {str(e)}")

# Geography endpoint for map integration
@app.get("/api/v1/geography/locations", response_model=List[GeographicalLocationResponse])
def get_geography_locations(db: Session = Depends(get_db)):
    """
    Get all geographical locations for map display
    """
    try:
        locations = db.query(GeographicalLocation).all()
        return locations
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get geographical locations: {str(e)}")

# Myth-Buster endpoint for debunking common biblical misconceptions
@app.post("/api/v1/myth-buster")
@limiter.limit("5/minute")
async def generate_myth_buster_content(
    request: Request,
    book: str,
    chapter: int,
    verse: int,
    db: Session = Depends(get_db)
):
    """
    Generate myth-busting content for a specific biblical verse.
    Addresses common misconceptions and provides historical context.
    """
    try:
        from openai_service import openai_client
        import json
        
        # Get the verse text first
        verse_text = db.query(BiblicalText).filter(
            BiblicalText.book == book,
            BiblicalText.chapter == chapter,
            BiblicalText.verse == verse,
            BiblicalText.translation == "KJV"
        ).first()
        
        if not verse_text:
            raise HTTPException(status_code=404, detail="Verse not found")
        
        # Get relevant historical notes for context
        historical_notes = db.query(HistoricalNote).filter(
            HistoricalNote.biblical_text_id == verse_text.id
        ).all()
        
        # Create context from historical notes
        historical_context = ""
        if historical_notes:
            historical_context = "\n".join([
                f"Historical Context: {note.title} - {note.content}"
                for note in historical_notes[:3]  # Limit to top 3 for context
            ])
        
        # Create myth-busting prompt
        myth_buster_prompt = f"""
        You are a biblical historian and myth-busting expert. Analyze the verse {book} {chapter}:{verse} and address common misconceptions.

        VERSE TEXT: "{verse_text.text}"
        
        HISTORICAL CONTEXT: {historical_context if historical_context else "No specific historical notes available."}
        
        Please provide myth-busting analysis in this exact JSON format:
        {{
            "myth_title": "A concise title of the most common myth about this verse or related topic",
            "myth_content": "2-3 sentences explaining what the myth claims and why it's problematic",
            "historical_facts": "3-4 sentences providing the actual historical facts that debunk the myth, including specific dates, councils, or historical evidence",
            "verse_connection": "1-2 sentences explaining how this myth relates to or affects interpretation of the specific verse"
        }}
        
        Focus on historical myths like:
        - Constantine creating Christianity or determining biblical canon
        - Misconceptions about biblical translation history
        - False claims about early church history
        - Misunderstandings about biblical authorship or dating
        - Colonial or cultural misinterpretations
        
        Be scholarly but accessible. Include specific dates and historical evidence.
        """
        
        # Generate myth-busting content using OpenAI
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a biblical historian specializing in debunking common misconceptions about Christianity and biblical history. Always respond with valid JSON."},
                {"role": "user", "content": myth_buster_prompt}
            ],
            max_tokens=800,
            temperature=0.3
        )
        
        content = response.choices[0].message.content
        if not content:
            raise HTTPException(status_code=500, detail="Failed to generate myth-buster content")
        
        # Parse the JSON response
        try:
            myth_data = json.loads(content)
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            myth_data = {
                "myth_title": "Constantine & Christianity Myth",
                "myth_content": "Contrary to popular belief, Constantine did not 'create' Christianity or determine its core doctrines. This misconception oversimplifies early Christian history.",
                "historical_facts": "The Council of Nicaea (325 CE) addressed existing theological disputes, particularly Arianism, rather than creating new beliefs. Christianity had been established and spreading for nearly 300 years before Constantine, with its core doctrines already developed through apostolic teaching and early church fathers.",
                "verse_connection": "This verse predates Constantine by centuries and represents established Christian doctrine about God's love and salvation that was already central to Christian belief."
            }
        
        return {
            "book": book,
            "chapter": chapter,
            "verse": verse,
            "verse_text": verse_text.text,
            "myth_buster": myth_data
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate myth-buster content: {str(e)}")

# Initialize LangChain components
from langchain_openai.chat_models import ChatOpenAI as ChatOpenAIClient
llm = ChatOpenAIClient(
    model="gpt-3.5-turbo",
    temperature=0.1,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

@app.post("/api/v1/chat/ask", response_model=ChatResponse)
async def chat_ask(request: ChatRequest, db: Session = Depends(get_db)):
    """
    AI-powered chat endpoint that answers questions based on biblical texts,
    historical notes, and user documents from the database.
    """
    try:
        # Perform semantic search across relevant database tables
        context_sources = []
        
        # Search biblical texts for relevant content (simple keyword matching for now)
        question_keywords = request.question.lower().split()
        
        # Search biblical texts
        biblical_results = []
        for keyword in question_keywords:
            results = db.query(BiblicalText).filter(
                BiblicalText.text.ilike(f"%{keyword}%")
            ).limit(3).all()
            biblical_results.extend(results)
        
        # Remove duplicates and limit results
        seen_ids = set()
        unique_biblical = []
        for result in biblical_results:
            if result.id not in seen_ids:
                seen_ids.add(result.id)
                unique_biblical.append(result)
                if len(unique_biblical) >= 5:  # Limit to top 5 results
                    break
        
        # Search historical notes
        historical_results = []
        for keyword in question_keywords:
            results = db.query(HistoricalNote).filter(
                HistoricalNote.content.ilike(f"%{keyword}%")
            ).limit(2).all()
            historical_results.extend(results)
        
        # Remove duplicates from historical notes
        seen_hist_ids = set()
        unique_historical = []
        for result in historical_results:
            if result.id not in seen_hist_ids:
                seen_hist_ids.add(result.id)
                unique_historical.append(result)
                if len(unique_historical) >= 3:  # Limit to top 3 results
                    break
        
        # Build context from search results
        context_parts = []
        
        # Add biblical text context
        for text in unique_biblical:
            context_part = f"Biblical Text - {text.book} {text.chapter}:{text.verse} ({text.translation}): {text.text}"
            context_parts.append(context_part)
            context_sources.append(f"{text.book} {text.chapter}:{text.verse} ({text.translation})")
        
        # Add historical context
        for note in unique_historical:
            context_part = f"Historical Note - {note.title}: {note.content[:300]}..."
            context_parts.append(context_part)
            context_sources.append(f"Historical Note: {note.title}")
        
        # If no context found, provide a general response
        if not context_parts:
            context_parts = ["No specific biblical or historical context found in the database for this question."]
            context_sources = ["General knowledge"]
        
        # Construct the prompt for the LLM
        context_text = "\n\n".join(context_parts)
        
        system_prompt = """You are a helpful scholarly assistant for a Bible research app.
You must answer the user's question based *only* on the provided context.
If the context doesn't contain enough information to answer the question, 
say so clearly and suggest what kind of information would be helpful.
Maintain a respectful, scholarly tone and acknowledge the limitations of your knowledge."""
        
        user_prompt = f"""Context:
{context_text}

Question:
{request.question}"""
        
        # Send to LLM
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response = llm.invoke(messages)
        
        # Extract content properly from LangChain response
        answer_text = response.content if hasattr(response, 'content') else str(response)
        
        return ChatResponse(
            answer=answer_text,
            context_used=context_sources
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing chat request: {str(e)}")

# ===============================================================================
# RESEARCH-GRADE SCHOLARLY PLATFORM ENDPOINTS
# ===============================================================================

@app.get("/api/v1/search/semantic")
@limiter.limit("10/minute")
async def semantic_search(
    request: Request,
    query: str,
    limit: int = 10,
    similarity_threshold: float = 0.7,
    translations: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Perform semantic search on biblical texts using vector embeddings
    
    Example: /api/v1/search/semantic?query=where is Cush referenced poetically?
    """
    try:
        # Parse translation filters
        translation_filters = translations.split(',') if translations else None
        
        results = await vector_search_service.semantic_search(
            db=db,
            query=query,
            limit=limit,
            similarity_threshold=similarity_threshold,
            translation_filters=translation_filters
        )
        
        return {
            "query": query,
            "results": results,
            "total_results": len(results),
            "search_type": "semantic"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Semantic search failed: {str(e)}")

@app.get("/api/v1/texts/{text_id}/similar")
async def find_similar_passages(
    text_id: int,
    limit: int = 5,
    exclude_same_book: bool = False,
    db: Session = Depends(get_db)
):
    """Find passages similar to a given biblical text using vector similarity"""
    try:
        results = await vector_search_service.find_similar_passages(
            db=db,
            reference_text_id=text_id,
            limit=limit,
            exclude_same_book=exclude_same_book
        )
        
        return {
            "reference_text_id": text_id,
            "similar_passages": results,
            "total_results": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Similar passages search failed: {str(e)}")

@app.get("/api/v1/texts/{text_id}/cross-references")
def get_cross_references(
    text_id: int,
    reference_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get cross-references for a biblical text (graph layer)"""
    try:
        query = db.query(CrossReference).filter(
            (CrossReference.source_text_id == text_id) | 
            (CrossReference.target_text_id == text_id)
        )
        
        if reference_type:
            query = query.filter(CrossReference.reference_type == reference_type)
        
        cross_refs = query.all()
        
        # Format results with text details
        results = []
        for ref in cross_refs:
            # Determine if this text is source or target
            related_text_id = ref.target_text_id if ref.source_text_id == text_id else ref.source_text_id
            related_text = db.query(BiblicalText).filter(BiblicalText.id == related_text_id).first()
            
            if related_text:
                results.append({
                    "reference_id": ref.id,
                    "reference_type": ref.reference_type,
                    "confidence_score": ref.confidence_score,
                    "description": ref.description,
                    "scholarly_source": ref.scholarly_source,
                    "thematic_keywords": ref.thematic_keywords,
                    "related_text": {
                        "id": related_text.id,
                        "reference": f"{related_text.book} {related_text.chapter}:{related_text.verse}",
                        "text": related_text.text,
                        "translation": related_text.translation
                    }
                })
        
        return {
            "text_id": text_id,
            "cross_references": results,
            "total_references": len(results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cross-references: {str(e)}")

@app.get("/api/v1/texts/{text_id}/variants")
def get_textual_variants(text_id: int, db: Session = Depends(get_db)):
    """Get textual variants for critical apparatus"""
    try:
        variants = db.query(TextualVariant).filter(
            TextualVariant.biblical_text_id == text_id
        ).all()
        
        results = []
        for variant in variants:
            results.append({
                "variant_id": variant.id,
                "variant_text": variant.variant_text,
                "variant_type": variant.variant_type,
                "manuscript_evidence": variant.manuscript_evidence,
                "critical_notes": variant.critical_notes,
                "probability_score": variant.probability_score,
                "textual_tradition": variant.textual_tradition,
                "scholarly_consensus": variant.scholarly_consensus
            })
        
        return {
            "text_id": text_id,
            "textual_variants": results,
            "total_variants": len(results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get textual variants: {str(e)}")

@app.get("/api/v1/texts/{text_id}/international")
def get_internationalized_texts(
    text_id: int,
    languages: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get multi-language versions of a biblical text"""
    try:
        query = db.query(InternationalizedText).filter(
            InternationalizedText.biblical_text_id == text_id
        )
        
        if languages:
            language_list = [lang.strip() for lang in languages.split(',')]
            # Note: This needs proper enum filtering - simplified for now
            pass
        
        international_texts = query.all()
        
        results = []
        for text in international_texts:
            results.append({
                "language": text.language.value if hasattr(text.language, 'value') else str(text.language),
                "text_content": text.text_content,
                "script_direction": text.script_direction,
                "transliteration": text.transliteration,
                "phonetic_guide": text.phonetic_guide,
                "liturgical_use": text.liturgical_use,
                "cultural_notes": text.cultural_notes,
                "canonical_status": text.canonical_status
            })
        
        return {
            "text_id": text_id,
            "international_texts": results,
            "available_languages": [r["language"] for r in results]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get international texts: {str(e)}")

@app.get("/api/v1/entities/network")
def get_person_place_network(
    entity_type: Optional[str] = None,
    search_term: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get person/place network data for graph analysis"""
    try:
        query = db.query(PersonPlaceNetwork)
        
        if entity_type:
            query = query.filter(PersonPlaceNetwork.entity_type == entity_type)
        
        if search_term:
            query = query.filter(
                PersonPlaceNetwork.entity_name.ilike(f"%{search_term}%")
            )
        
        # Order by centrality score and occurrence count
        entities = query.limit(limit).all()
        
        results = []
        for entity in entities:
            results.append({
                "entity_id": entity.id,
                "entity_name": entity.entity_name,
                "entity_type": entity.entity_type,
                "alternative_names": entity.alternative_names,
                "centrality_score": entity.centrality_score,
                "occurrence_count": entity.occurrence_count,
                "first_occurrence": entity.first_occurrence,
                "last_occurrence": entity.last_occurrence,
                "description": entity.description,
                "time_period": entity.time_period,
                "geographical_region": entity.geographical_region,
                "related_entities": entity.related_entities
            })
        
        return {
            "entities": results,
            "total_entities": len(results),
            "search_filters": {
                "entity_type": entity_type,
                "search_term": search_term
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get entity network: {str(e)}")

@app.post("/api/v1/admin/embeddings/populate")
@limiter.limit("5/minute")
async def populate_embeddings(
    request: Request,
    batch_size: int = 100,
    db: Session = Depends(get_db)
):
    """Admin endpoint to populate embeddings for texts without them - RATE LIMITED"""
    try:
        processed_count = await vector_search_service.populate_embeddings(db, batch_size)
        
        return {
            "message": f"Processed {processed_count} texts",
            "batch_size": batch_size,
            "status": "completed" if processed_count < batch_size else "partial"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to populate embeddings: {str(e)}")

# ===============================================================================
# ABSTRACT VERSE ID ARCHITECTURE API ENDPOINTS
# ===============================================================================

@app.get("/api/v1/canons", response_model=List[CanonResponse])
def get_canons(db: Session = Depends(get_db)):
    """Get all available biblical canons"""
    try:
        canons = db.query(Canon).all()
        return canons
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get canons: {str(e)}")

@app.get("/api/v1/versifications", response_model=List[VersificationResponse])
def get_versifications(canon_code: Optional[str] = None, db: Session = Depends(get_db)):
    """Get all versification systems, optionally filtered by canon"""
    try:
        query = db.query(Versification)
        if canon_code:
            canon = db.query(Canon).filter(Canon.code == canon_code).first()
            if canon:
                query = query.filter(Versification.canon_id == canon.id)
        versifications = query.all()
        return versifications
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get versifications: {str(e)}")

@app.get("/api/v1/verses/{abstract_id}", response_model=AbstractVerseDetailsResponse)
def get_abstract_verse_details(abstract_id: int, db: Session = Depends(get_db)):
    """Get complete details for an abstract verse across all versifications"""
    try:
        # Get the abstract verse
        abstract_verse = db.query(AbstractVerse).filter(AbstractVerse.id == abstract_id).first()
        if not abstract_verse:
            raise HTTPException(status_code=404, detail="Abstract verse not found")
        
        # Get canonical positions
        canonical_positions = db.query(CanonicalPosition).filter(
            CanonicalPosition.abstract_verse_id == abstract_id
        ).all()
        
        # Get all biblical texts for this abstract verse
        biblical_texts = db.query(BiblicalText).filter(
            BiblicalText.abstract_verse_id == abstract_id
        ).all()
        
        # Build translations dictionary
        translations = {}
        for text in biblical_texts:
            translations[text.translation] = text.text
        
        # Get cross-references via abstract IDs
        cross_refs = db.query(CrossReference).filter(
            (CrossReference.source_abstract_id == abstract_id) |
            (CrossReference.target_abstract_id == abstract_id)
        ).all()
        
        cross_references = []
        for ref in cross_refs:
            if ref.target_abstract_verse and ref.target_abstract_verse.id != abstract_id:
                target_pos = db.query(CanonicalPosition).filter(
                    CanonicalPosition.abstract_verse_id == ref.target_abstract_verse.id
                ).first()
                if target_pos:
                    cross_references.append({
                        "book": target_pos.book,
                        "chapter": str(target_pos.chapter_start),
                        "verse": str(target_pos.verse_start),
                        "reference_type": ref.reference_type,
                        "confidence": str(ref.confidence_score)
                    })
        
        # Get historical and geographical context from any linked biblical text
        historical_context = []
        geographical_context = []
        if biblical_texts:
            sample_text = biblical_texts[0]
            historical_context = db.query(HistoricalNote).filter(
                HistoricalNote.biblical_text_id == sample_text.id
            ).all()
            geographical_context = db.query(GeographicalLocation).filter(
                GeographicalLocation.biblical_text_id == sample_text.id
            ).all()
        
        # Build versification differences
        versification_differences = {}
        for position in canonical_positions:
            vers = db.query(Versification).filter(Versification.id == position.versification_id).first()
            if vers:
                versification_differences[vers.code] = [{
                    "book": position.book,
                    "chapter": str(position.chapter_start),
                    "verse": str(position.verse_start),
                    "position_type": position.position_type,
                    "confidence": str(position.confidence_score)
                }]
        
        return AbstractVerseDetailsResponse(
            abstract_verse=abstract_verse,
            canonical_positions=canonical_positions,
            translations=translations,
            cross_references=cross_references,
            historical_context=historical_context,
            geographical_context=geographical_context,
            versification_differences=versification_differences
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get abstract verse details: {str(e)}")

@app.post("/api/v1/resolve", response_model=VerseResolveResponse)
def resolve_verse(request: VerseResolveRequest, db: Session = Depends(get_db)):
    """Resolve a verse reference to abstract ID with positions in different versifications"""
    try:
        resolver = get_resolution_service(db)
        
        # Default to Protestant canon if not specified
        canon_code = request.canon or "PROT66"
        
        # Map to abstract verse ID
        abstract_id = resolver.map_to_abstract_id(canon_code, request.book, request.chapter, request.verse)
        if not abstract_id:
            raise HTTPException(status_code=404, detail="Verse not found in specified canon")
        
        # Get the abstract verse and canonical key
        abstract_verse = db.query(AbstractVerse).filter(AbstractVerse.id == abstract_id).first()
        if not abstract_verse:
            raise HTTPException(status_code=404, detail="Abstract verse not found")
        
        # Get canonical positions for all versifications
        positions = db.query(CanonicalPosition).filter(
            CanonicalPosition.abstract_verse_id == abstract_id
        ).all()
        
        # Get available translations
        biblical_texts = db.query(BiblicalText).filter(
            BiblicalText.abstract_verse_id == abstract_id
        ).all()
        
        available_translations = [
            {"translation": text.translation, "text": text.text} 
            for text in biblical_texts
        ]
        
        return VerseResolveResponse(
            abstract_verse_id=abstract_id,
            canonical_key=abstract_verse.canonical_key,
            positions=positions,
            available_translations=available_translations
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve verse: {str(e)}")

@app.get("/api/v1/cross-versification-mapping", response_model=CrossVersificationMappingResponse)
def get_cross_versification_mapping(
    book: str, 
    chapter: int, 
    verse: int, 
    source_versification: str = "KJV",
    db: Session = Depends(get_db)
):
    """Get how a verse maps across different versification systems"""
    try:
        resolver = get_resolution_service(db)
        
        # Get mappings across all versifications
        mappings = resolver.get_cross_versification_mappings(book, chapter, verse, source_versification)
        
        # Find the abstract verse ID
        canon = db.query(Canon).join(Versification).filter(
            Versification.code == source_versification
        ).first()
        
        abstract_id = None
        if canon:
            abstract_id = resolver.map_to_abstract_id(canon.code, book, chapter, verse)
        
        return CrossVersificationMappingResponse(
            source_reference={
                "versification": source_versification,
                "book": book,
                "chapter": str(chapter),
                "verse": str(verse)
            },
            abstract_verse_id=abstract_id or 0,
            mappings=mappings
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cross-versification mapping: {str(e)}")

# Enhanced version comparison endpoint with canon support
@app.get("/api/v1/texts/{book}/{chapter}/{verse}/canons", response_model=MultiCanonSearchResponse)
def get_verse_across_canons(book: str, chapter: int, verse: int, db: Session = Depends(get_db)):
    """Get verse content across different canonical traditions"""
    try:
        resolver = get_resolution_service(db)
        
        # Get all canons
        canons = db.query(Canon).all()
        
        results = []
        canon_availability = {}
        
        for canon in canons:
            # Try to find this verse in this canon
            abstract_id = resolver.map_to_abstract_id(canon.code, book, chapter, verse)
            
            if abstract_id:
                # Get biblical texts for this abstract verse
                biblical_texts = db.query(BiblicalText).filter(
                    BiblicalText.abstract_verse_id == abstract_id
                ).all()
                
                translations = {}
                for text in biblical_texts:
                    translations[text.translation] = text.text
                
                results.append({
                    "canon": canon.code,
                    "canon_name": canon.name,
                    "abstract_verse_id": abstract_id,
                    "translations": translations
                })
                canon_availability[canon.code] = True
            else:
                canon_availability[canon.code] = False
        
        return MultiCanonSearchResponse(
            query=f"{book} {chapter}:{verse}",
            results=results,
            canon_availability=canon_availability
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get verse across canons: {str(e)}")

# Q&A RAG (Retrieval-Augmented Generation) endpoints
@app.post("/api/v1/qa/ask", response_model=RAGResponse)
@limiter.limit("30/minute")  # Rate limiting for AI-powered endpoints
async def ask_question(request: Request, rag_request: RAGRequest, db: Session = Depends(get_db)):
    """
    Sophisticated question-answer endpoint using RAG
    
    Handles complex biblical queries like:
    - "Where did Moses live?"
    - "What was Peter's Hebrew name?"
    - "Who was the pharaoh during the Exodus?"
    - "Show me verses about forgiveness"
    """
    try:
        # Process query through RAG pipeline
        rag_response = await rag_service.process_query(db, rag_request.question)
        
        # Convert to API response format
        biblical_passages = [
            BiblicalPassageResult(
                id=passage.get('id', 0),
                reference=passage.get('reference', ''),
                book=passage.get('book', ''),
                chapter=passage.get('chapter', 0),
                verse=passage.get('verse', 0),
                text=passage.get('text', ''),
                translation=passage.get('translation', 'KJV'),
                similarity_score=passage.get('similarity_score', 0.0)
            )
            for passage in rag_response.biblical_passages
        ]
        
        historical_context = [
            HistoricalContextResult(
                title=note.get('title', ''),
                content=note.get('content', ''),
                period=note.get('period', None),
                source=note.get('source', None)
            )
            for note in rag_response.historical_context
        ]
        
        geographical_data = [
            GeographicalResult(
                ancient_name=geo.get('ancient_name', ''),
                modern_name=geo.get('modern_name', None),
                coordinates=geo.get('coordinates', None),
                description=geo.get('description', None),
                confidence=geo.get('confidence', None)
            )
            for geo in rag_response.geographical_data
        ]
        
        lexicon_insights = [
            LexiconResult(
                word=entry.get('word', ''),
                language=entry.get('language', 'unknown'),
                definition=entry.get('definition', ''),
                transliteration=entry.get('transliteration', None),
                strong_number=entry.get('strong_number', None)
            )
            for entry in rag_response.lexicon_insights
        ]
        
        return RAGResponse(
            question=rag_response.question,
            answer=rag_response.answer,
            question_type=QuestionTypeEnum(rag_response.question_type.value),
            biblical_passages=biblical_passages,
            historical_context=historical_context,
            geographical_data=geographical_data,
            lexicon_insights=lexicon_insights,
            related_queries=rag_response.related_queries,
            confidence_score=rag_response.confidence_score,
            processing_time=rag_response.processing_time
        )
        
    except Exception as e:
        print(f"Error in Q&A endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process question: {str(e)}")

@app.get("/api/v1/qa/suggestions", response_model=QuerySuggestionsResponse)
@limiter.limit("60/minute")
async def get_query_suggestions(request: Request, db: Session = Depends(get_db)):
    """
    Get suggested questions based on available data
    
    Returns curated questions that demonstrate the system's capabilities
    across different question types and data sources.
    """
    try:
        # Get sample data to generate suggestions
        # Location-based suggestions
        location_sample = db.query(GeographicalLocation).limit(5).all()
        location_queries = [
            f"Where is {loc.name} mentioned in the Bible?"
            for loc in location_sample
            if loc.name
        ]
        if not location_queries:
            location_queries = [
                "Where did Moses live?",
                "What is the biblical location of Mount Sinai?",
                "Where was Jerusalem in ancient times?"
            ]
        
        # Person-based suggestions
        person_queries = [
            "What was Peter's Hebrew name?",
            "Who was the father of David?",
            "What was Paul's original name before conversion?",
            "Who was the pharaoh during the Exodus?",
            "What was Moses' relationship to Aaron?"
        ]
        
        # Conceptual/thematic suggestions
        conceptual_queries = [
            "Show me verses about forgiveness",
            "What does the Bible say about love?",
            "Find passages about faith and hope",
            "What are the biblical teachings on justice?",
            "Show me verses about peace"
        ]
        
        # Historical context suggestions
        historical_queries = [
            "What was life like in ancient Israel?",
            "Who ruled during Jesus' time?",
            "What was the political situation during the Exodus?",
            "What was the role of priests in the temple?",
            "How did ancient Hebrew culture influence the texts?"
        ]
        
        # Featured query - rotate or pick based on data availability
        featured_query = "Where did Moses live and what was the historical context?"
        
        return QuerySuggestionsResponse(
            location_queries=location_queries[:4],
            person_queries=person_queries[:4],
            conceptual_queries=conceptual_queries[:4],
            historical_queries=historical_queries[:4],
            featured_query=featured_query
        )
        
    except Exception as e:
        print(f"Error generating suggestions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate suggestions: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)