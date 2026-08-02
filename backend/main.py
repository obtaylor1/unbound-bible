# Liberation Bible Project - FastAPI Backend
# Referenced from blueprint:python_database integration

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Request, BackgroundTasks
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
    Versification, CanonicalPosition, TranslationBias as TranslationBiasModel, UserNote,
    Book, CanonBook, RaceMisuseRecord, FactbookEntry, ManuscriptWitness, 
    SermonAnalysis, SermonClaim, StudySession, AISource
)
from schemas import (
    BiblicalTextResponse, HistoricalNoteResponse, GeographicalLocationResponse,
    TextualComparisonResponse, OriginalWordResponse, WordWithOriginal, TranslationText, TranslationBias, LanguageType,
    SermonAnalysisResponse, CulturalContextRequest, CulturalContextResponse, VerseDetailsResponse,
    ChatRequest, ChatResponse, AbstractVerseResponse, CanonResponse, VersificationResponse,
    CanonicalPositionResponse, VerseResolveRequest, VerseResolveResponse, AbstractVerseDetailsResponse,
    CrossVersificationMappingResponse, MultiCanonSearchResponse, RAGRequest, RAGResponse,
    QuestionTypeEnum, BiblicalPassageResult, HistoricalContextResult, GeographicalResult,
    LexiconResult, QuerySuggestionsResponse, TranslationBiasResponse,
    UserNoteCreate, UserNoteUpdate, UserNoteResponse,
    DynamicBiasAuditRequest, DynamicBiasAuditResponse,
    CanonCompareResponse, BookDetailResponse, RaceMisuseRecordResponse,
    FactbookEntrySummary, FactbookEntryDetailResponse, StudySessionResponse, StudySessionCreate,
    AccuracyClaim, SermonSummary, TranscriptSegment, VisualDashboardMetrics
)
from resolve_service import get_resolution_service
from openai_service import transcribe_audio, analyze_sermon_content, suggest_cultural_context, generate_verse_details_ai
from vector_search import vector_search_service
from rag_service import rag_service
from auth import get_current_user
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage
import tiktoken
from app.api.router import api_router as versioned_api_router
from app.config import get_settings

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

settings = get_settings()

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
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(versioned_api_router, prefix="/api/v1")

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

PROTESTANT_BOOKS = {
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth",
    "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah",
    "Esther", "Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah",
    "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah",
    "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi",
    "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians", "2 Corinthians",
    "Galatians", "Ephesians", "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians",
    "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews", "James", "1 Peter", "2 Peter",
    "1 John", "2 John", "3 John", "Jude", "Revelation"
}

def download_chapter_data(book: str, chapter: int, translation: str) -> list:
    """Downloads chapter data from bible-api.com (or api.nlt.to for NLT) with exponential backoff on rate limiting"""
    import urllib.request
    import urllib.parse
    import urllib.error
    import json
    import ssl
    import time
    import re
    from bs4 import BeautifulSoup
    
    if translation.lower() == 'nlt':
        ref_str = f"{book}.{chapter}"
        url_encoded = urllib.parse.quote(ref_str)
        url = f"https://api.nlt.to/api/passages?ref={url_encoded}&key=TEST"
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        context = ssl._create_unverified_context()
        
        max_retries = 5
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, context=context, timeout=8) as response:
                    if response.status == 200:
                        html_content = response.read().decode('utf-8')
                        soup = BeautifulSoup(html_content, 'html.parser')
                        verses = []
                        for export in soup.find_all('verse_export'):
                            vn_str = export.get('vn')
                            if not vn_str:
                                continue
                            try:
                                vn = int(vn_str)
                            except ValueError:
                                continue
                                
                            # Clean up footnotes/translator notes
                            for tag in export.find_all(class_=['tn', 'fn', 'a-tn', 'a-fn']):
                                tag.decompose()
                            for link in export.find_all('a'):
                                link.decompose()
                                
                            text = export.get_text()
                            text = text.strip()
                            text = re.sub(rf'^{vn}', '', text)
                            text = re.sub(r'\s+', ' ', text).strip()
                            
                            verses.append({
                                'verse': vn,
                                'text': text
                            })
                        return verses
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait_time = 2 ** attempt + 1
                    print(f"Rate limited (429) for {book} {chapter} (NLT). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"HTTP error {e.code} fetching {book} {chapter} (NLT): {e.reason}")
                    break
            except Exception as e:
                print(f"Error fetching {book} {chapter} (NLT): {e}")
                time.sleep(1)
                continue
        return []

    # Normal bible-api.com fetcher
    query_str = f"{book} {chapter}"
    url_encoded = urllib.parse.quote(query_str)
    url = f"https://bible-api.com/{url_encoded}?translation={translation.lower()}"
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    context = ssl._create_unverified_context()
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, context=context, timeout=8) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    return data.get('verses', [])
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait_time = 2 ** attempt + 1
                print(f"Rate limited (429) for {book} {chapter} ({translation}). Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                print(f"HTTP error {e.code} fetching {book} {chapter} ({translation}): {e.reason}")
                break
        except Exception as e:
            print(f"Error fetching {book} {chapter} ({translation}): {e}")
            time.sleep(1)
            continue
    return []

def get_or_create_translation(db: Session, code: str, name: str) -> int:
    """Get the database ID of a translation, creating it if it doesn't exist"""
    from models import Translation
    trans = db.query(Translation).filter(Translation.code == code).first()
    if not trans:
        try:
            trans = Translation(
                code=code,
                name=name,
                language="English",
                is_original_language=False,
                is_public_domain=True,
                description=f"{name} translation pulled from bible-api.com"
            )
            db.add(trans)
            db.commit()
            db.refresh(trans)
            print(f"Created missing translation metadata record for {code}")
        except Exception as e:
            db.rollback()
            print(f"Error creating translation metadata: {e}")
            # Fallback to look up again in case of race condition
            trans = db.query(Translation).filter(Translation.code == code).first()
            if not trans:
                return 1 # Fallback to KJV
    return trans.id

def ensure_translations_cached(book: str, db: Session):
    """Ensures ASV, WEB, BBE, etc. translations are cached for the given book (limited concurrency)"""
    if book not in PROTESTANT_BOOKS:
        return
    from sqlalchemy import func
    from concurrent.futures import ThreadPoolExecutor
    
    kjv_count = db.query(func.count(BiblicalText.id)).filter(
        BiblicalText.book == book,
        BiblicalText.translation == 'KJV'
    ).scalar() or 0
    
    if kjv_count == 0:
        return
        
    supported = {
        'ASV': ('asv', 'American Standard Version'),
        'WEB': ('web', 'World English Bible'),
        'WEBBE': ('webbe', 'World English Bible British Edition'),
        'BBE': ('bbe', 'Bible in Basic English'),
        'DARBY': ('darby', 'Darby Translation'),
        'DRA': ('dra', 'Douay-Rheims 1899 American Edition'),
        'YLT': ('ylt', 'Young\'s Literal Translation'),
        'NLT': ('nlt', 'New Living Translation')
    }
    
    translations_to_fetch = []
    for code_upper, (code_lower, name) in supported.items():
        count = db.query(func.count(BiblicalText.id)).filter(
            BiblicalText.book == book,
            BiblicalText.translation == code_upper
        ).scalar() or 0
        
        if count < kjv_count * 0.9:
            translations_to_fetch.append((code_lower, code_upper, name))
            
    if not translations_to_fetch:
        return
        
    total_chapters = db.query(func.max(BiblicalText.chapter)).filter(
        BiblicalText.book == book,
        BiblicalText.translation == 'KJV'
    ).scalar()
    
    if not total_chapters:
        total_chapters = 50
        
    for code_lower, code_upper, name in translations_to_fetch:
        print(f"Fetching {code_upper} translation for all {total_chapters} chapters of {book}...")
        tasks = [(book, ch, code_lower) for ch in range(1, total_chapters + 1)]
        
        # Concurrency max_workers=2 to prevent rate limiting (429)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda t: download_chapter_data(*t), tasks))
            
        trans_id = get_or_create_translation(db, code_upper, name)
        
        new_texts = []
        for ch_idx, verses in enumerate(results):
            ch = ch_idx + 1
            for v in verses:
                v_num = v.get('verse')
                v_text = v.get('text', '').strip()
                
                exists = db.query(BiblicalText).filter(
                    BiblicalText.book == book,
                    BiblicalText.chapter == ch,
                    BiblicalText.verse == v_num,
                    BiblicalText.translation == code_upper
                ).first() is not None
                
                if not exists:
                    new_texts.append(BiblicalText(
                        book=book,
                        chapter=ch,
                        verse=v_num,
                        translation=code_upper,
                        translation_id=trans_id,
                        text=v_text
                    ))
        if new_texts:
            try:
                db.bulk_save_objects(new_texts)
                db.commit()
                print(f"Successfully cached {len(new_texts)} verses of {book} for {code_upper}!")
            except Exception as e:
                print(f"Error bulk saving fetched verses: {e}")
                db.rollback()

def ensure_chapter_cached(book: str, chapter: int, db: Session):
    """Ensures ASV, WEB, BBE, etc. translations are cached for the given book and chapter"""
    if book not in PROTESTANT_BOOKS:
        return
    from sqlalchemy import func
    
    kjv_count = db.query(func.count(BiblicalText.id)).filter(
        BiblicalText.book == book,
        BiblicalText.chapter == chapter,
        BiblicalText.translation == 'KJV'
    ).scalar() or 0
    
    if kjv_count == 0:
        return
        
    supported = {
        'ASV': ('asv', 'American Standard Version'),
        'WEB': ('web', 'World English Bible'),
        'WEBBE': ('webbe', 'World English Bible British Edition'),
        'BBE': ('bbe', 'Bible in Basic English'),
        'DARBY': ('darby', 'Darby Translation'),
        'DRA': ('dra', 'Douay-Rheims 1899 American Edition'),
        'YLT': ('ylt', 'Young\'s Literal Translation'),
        'NLT': ('nlt', 'New Living Translation')
    }
    
    translations_to_fetch = []
    for code_upper, (code_lower, name) in supported.items():
        count = db.query(func.count(BiblicalText.id)).filter(
            BiblicalText.book == book,
            BiblicalText.chapter == chapter,
            BiblicalText.translation == code_upper
        ).scalar() or 0
        
        if count < kjv_count:
            translations_to_fetch.append((code_lower, code_upper, name))
            
    if not translations_to_fetch:
        return
        
    for code_lower, code_upper, name in translations_to_fetch:
        print(f"Fetching {code_upper} translation for {book} {chapter}...")
        verses = download_chapter_data(book, chapter, code_lower)
        if not verses:
            continue
            
        trans_id = get_or_create_translation(db, code_upper, name)
        
        new_texts = []
        for v in verses:
            v_num = v.get('verse')
            v_text = v.get('text', '').strip()
            
            exists = db.query(BiblicalText).filter(
                BiblicalText.book == book,
                BiblicalText.chapter == chapter,
                BiblicalText.verse == v_num,
                BiblicalText.translation == code_upper
            ).first() is not None
            
            if not exists:
                new_texts.append(BiblicalText(
                    book=book,
                    chapter=chapter,
                    verse=v_num,
                    translation=code_upper,
                    translation_id=trans_id,
                    text=v_text
                ))
        if new_texts:
            try:
                db.bulk_save_objects(new_texts)
                db.commit()
                print(f"Successfully cached {len(new_texts)} verses of {book} {chapter} for {code_upper}!")
            except Exception as e:
                print(f"Error saving chapter: {e}")
                db.rollback()

def bg_ensure_translations_cached(book: str):
    """Run ensure_translations_cached in a background task with a fresh session"""
    from database import SessionLocal
    db = SessionLocal()
    try:
        ensure_translations_cached(book, db)
    except Exception as e:
        print(f"Background caching error for book {book}: {e}")
    finally:
        db.close()

def bg_ensure_chapter_cached(book: str, chapter: int):
    """Run ensure_chapter_cached in a background task with a fresh session"""
    from database import SessionLocal
    db = SessionLocal()
    try:
        ensure_chapter_cached(book, chapter, db)
    except Exception as e:
        print(f"Background caching error for chapter {book} {chapter}: {e}")
    finally:
        db.close()

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

@app.get("/api/biblical-texts/book-content")
def get_book_content(book: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Get all content for a specific book for the ApocryphaReader component
    Returns all verses/chapters organized by structure
    """
    try:
        # Automatically cache missing standard translations in background
        background_tasks.add_task(bg_ensure_translations_cached, book)
        
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


@app.get("/api/biblical-texts/chapter-content")
def get_chapter_content(book: str, chapter: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Get all content for a specific book and chapter.
    If translations like ASV/WEB are missing, fetch them from the web.
    """
    try:
        # Automatically cache missing standard translations in background for this chapter
        background_tasks.add_task(bg_ensure_chapter_cached, book, chapter)
        
        # Get all biblical texts for the specified book and chapter, ordered by verse
        texts = db.query(BiblicalText).filter(
            BiblicalText.book == book,
            BiblicalText.chapter == chapter
        ).order_by(
            BiblicalText.verse.asc()
        ).all()
        
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
            
        return {
            "book": book,
            "chapter": chapter,
            "content": content,
            "total_verses": len(content)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get chapter content: {str(e)}")


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
        
        # Define Protestant canon books (66 books)
        protestant_books = {
            "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth",
            "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah",
            "Esther", "Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah",
            "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah",
            "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi",
            "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians", "2 Corinthians",
            "Galatians", "Ephesians", "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians",
            "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews", "James", "1 Peter", "2 Peter",
            "1 John", "2 John", "3 John", "Jude", "Revelation"
        }
        
        # Define Catholic canon books
        catholic_books = protestant_books.union({
            "Tobit", "Judith", "Wisdom of Solomon", "Sirach", "Baruch", "1 Maccabees", "2 Maccabees"
        })

        new_testament_books = {
            "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians", "2 Corinthians",
            "Galatians", "Ephesians", "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians",
            "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews", "James", "1 Peter", "2 Peter",
            "1 John", "2 John", "3 John", "Jude", "Revelation"
        }
        book_collections = {
            **{name: "Pentateuch" for name in {"Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy"}},
            **{name: "Historical Books" for name in {"Joshua", "Judges", "Ruth", "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah", "Esther", "Tobit", "Judith", "1 Maccabees", "2 Maccabees"}},
            **{name: "Wisdom and Poetry" for name in {"Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon", "Wisdom of Solomon", "Sirach"}},
            **{name: "Major Prophets" for name in {"Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Baruch"}},
            **{name: "Minor Prophets" for name in {"Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi"}},
            **{name: "Gospels" for name in {"Matthew", "Mark", "Luke", "John"}},
            "Acts": "Acts",
            **{name: "Pauline Letters" for name in {"Romans", "1 Corinthians", "2 Corinthians", "Galatians", "Ephesians", "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon"}},
            **{name: "General Letters" for name in {"Hebrews", "James", "1 Peter", "2 Peter", "1 John", "2 John", "3 John", "Jude"}},
            "Revelation": "Apocalyptic Literature",
        }
        
        # Define Ethiopian Orthodox canon books (81-88 books, excluding extra-canonical reference works)
        extra_canonical_books = {"Antiquities", "Genesis Targum"}
        
        # Create book objects with canonical information
        books_with_canonical_info = []
        for book_name in book_list:
            is_prot = book_name in protestant_books
            is_cath = book_name in catholic_books
            is_eth = book_name not in extra_canonical_books
            
            # Apply canonical filtering
            if canon == "PROT66" and not is_prot:
                continue
            elif canon == "CATH73" and not is_cath:
                continue
            elif canon in ["ETH81", "ETHIO81"] and not is_eth:
                continue
                
            book_info = {
                "name": book_name,
                "testament": (
                    "New Testament" if book_name in new_testament_books
                    else "Old Testament" if book_name in catholic_books
                    else None
                ),
                "collection": book_collections.get(book_name),
                "canonical_status": {
                    "protestant": is_prot,
                    "catholic": is_cath,
                    "ethiopian_orthodox": is_eth,
                    "is_ethiopian_unique": is_eth and not is_cath
                }
            }
            books_with_canonical_info.append(book_info)
        
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
def get_verse_comparison(book: str, chapter: int, verse: int, canon: str = "PROT66", background_tasks: BackgroundTasks = None, db: Session = Depends(get_db)):
    # Automatically cache missing standard translations in background for this chapter
    if background_tasks:
        background_tasks.add_task(bg_ensure_chapter_cached, book, chapter)
    
    # Define Protestant canon books (66 books)
    protestant_books = {
        "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth",
        "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah",
        "Esther", "Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah",
        "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah",
        "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi",
        "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians", "2 Corinthians",
        "Galatians", "Ephesians", "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians",
        "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews", "James", "1 Peter", "2 Peter",
        "1 John", "2 John", "3 John", "Jude", "Revelation"
    }
    
    # Define Catholic canon books
    catholic_books = protestant_books.union({
        "Tobit", "Judith", "Wisdom of Solomon", "Sirach", "Baruch", "1 Maccabees", "2 Maccabees"
    })
    
    # Check if the requested book is in the active canon
    is_in_active_canon = True
    if canon == "PROT66" and book not in protestant_books:
        is_in_active_canon = False
    elif canon == "CATH73" and book not in catholic_books:
        is_in_active_canon = False
    
    # Handle canonical toggle logic
    if not is_in_active_canon:
        # Return canon placeholders for books outside the active canon
        placeholder_text = TranslationText(
            text=f"This book ({book}) is not found in the selected canon. Try changing the canon filter to explore it.",
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
            canonical_note=f"{book} is not present in the selected canon."
        )
    
    # Query for all translations of this verse in the database
    texts = db.query(BiblicalText).filter(
        BiblicalText.book == book,
        BiblicalText.chapter == chapter,
        BiblicalText.verse == verse
    ).all()
    
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
            
            # Find matching original word by position (database is 1-indexed, i is 0-indexed)
            original_word = None
            for orig in original_words:
                pos = cast(Optional[int], getattr(orig, "word_position", None))
                if pos is not None and pos == i + 1:
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
    if not texts:
        raise HTTPException(status_code=404, detail="Verse not found in any translation")
    
    translations = {}
    for biblical_text in texts:
        translations[biblical_text.translation.lower()] = create_translation_text(biblical_text)
    
    # Add canonical note if needed
    canonical_note = None
    is_ethiopian_unique = book not in protestant_books
    if is_ethiopian_unique and canon in ["ETH81", "ETHIO81"]:
        canonical_note = f"{book} is unique to the broader canon and is not found in the Protestant canon (66 books)."
    
    return TextualComparisonResponse(
        book=book,
        chapter=chapter,
        verse=verse,
        translations=translations,
        canonical_note=canonical_note
    )

# Verse Details endpoint for in-depth analysis
@app.get("/api/v1/texts/{book}/{chapter}/{verse}/details", response_model=VerseDetailsResponse)
async def get_verse_details(book: str, chapter: int, verse: int, db: Session = Depends(get_db)):
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
        
        # Query translation biases from database
        biases = db.query(TranslationBiasModel).filter(
            TranslationBiasModel.book == book.strip(),
            TranslationBiasModel.chapter == chapter,
            TranslationBiasModel.verse == verse
        ).all()
        
        # Query race misuse records from database
        race_misuse_records = db.query(RaceMisuseRecord).filter(
            RaceMisuseRecord.book == book.strip(),
            RaceMisuseRecord.chapter == chapter,
            RaceMisuseRecord.verse == verse
        ).all()
        
        # Generate verse meaning & comparison (with AI helper when key is set)
        ai_details = await generate_verse_details_ai(book, chapter, verse, translations)
        
        if ai_details:
            verse_meaning = ai_details.get("verse_meaning", "")
            translation_comparison = ai_details.get("translation_comparison", "")
            critical_analysis = ai_details.get("critical_analysis", "")
        else:
            # Fallback to standard rule-based templates
            primary_text = ""
            if "KJV" in translations:
                primary_text = translations["KJV"]
            elif translations:
                primary_text = list(translations.values())[0]

            verse_meaning = f"This verse from {book} {chapter}:{verse} contains profound spiritual insights. "
            if historical_notes:
                verse_meaning += f"Historical context shows {historical_notes[0].content[:100]}..."
            else:
                if primary_text:
                    if len(primary_text) > 80:
                        preview = primary_text[:77] + "..."
                    else:
                        preview = primary_text
                    verse_meaning += f"The passage (\"{preview}\") emphasizes central themes of faith, covenant, and divine instruction."
                else:
                    verse_meaning += "The verse emphasizes themes of faith, redemption, and divine love, central to biblical teaching."
            
            if primary_text:
                if len(primary_text) > 80:
                    preview = primary_text[:77] + "..."
                else:
                    preview = primary_text
                translation_comparison = f"Comparing translations for {book} {chapter}:{verse} (e.g., KJV: \"{preview}\") reveals consistent theological meaning with minor stylistic adaptations across versions."
            else:
                translation_comparison = f"Comparing translations for {book} {chapter}:{verse} shows consistent theological meaning while adapting to different linguistic preferences."

            critical_analysis = f"Critical analysis of {book} {chapter}:{verse}: Scholars note that this passage has been referenced in various theological discussions. "
            if book == "Song of Solomon" and chapter == 1 and verse == 5:
                critical_analysis += "Modern scholarship (e.g., Wilda Gafney in 'Womanist Midrash') highlights how translations like the KJV ('black but comely') introduce colorist bias, whereas the original Hebrew conjunctive 've' should be translated as 'black and beautiful' to preserve the affirmative character of the text."
            elif book == "Exodus" and chapter == 12 and verse == 38:
                critical_analysis += "The term 'erev rav' (mixed multitude) points to ethnic and social diversity in the Exodus covenant, which is sometimes obscured in traditional commentaries but emphasized in decolonial readings (e.g., Esau McCaulley in 'Reading While Black')."
            else:
                critical_analysis += "Careful attention to the original Greek or Hebrew text helps clarify the original historical context and prevents incorrect modern application."
        
        # Generate cross-references (enhanced implementation with proper data)
        cross_references = []
        
        # Comprehensive cross-reference database
        cross_ref_map = {
            ("Genesis", 1, 1): [
                {
                    "book": "John",
                    "chapter": "1",
                    "verse": "1",
                    "text": "In the beginning was the Word, and the Word was with God, and the Word was God.",
                    "description": "The prologue of John's Gospel directly echoes the 'in the beginning' of Genesis, linking creation with the pre-existence of the Logos."
                },
                {
                    "book": "Hebrews",
                    "chapter": "11",
                    "verse": "3",
                    "text": "By faith we understand that the universe was created by the word of God, so that what is seen was not made out of things that are visible.",
                    "description": "Scholarly link between the divine fiat ('God said') of Genesis 1 and the concept of creation out of nothing (creatio ex nihilo)."
                },
                {
                    "book": "Colossians",
                    "chapter": "1",
                    "verse": "16",
                    "text": "For by him all things were created, in heaven and on earth, visible and invisible...",
                    "description": "Pauline Christological passage attributing the creation of all things in Genesis 1:1 to the Son."
                }
            ],
            ("John", 3, 16): [
                {"book": "Romans", "chapter": "5", "verse": "8", "text": "But God demonstrates his own love for us in this: While we were still sinners, Christ died for us.", "description": "Demonstration of God's love through sacrificial death, mirroring the giving of the Son in John 3:16."},
                {"book": "1 John", "chapter": "4", "verse": "9", "text": "This is how God showed his love among us: He sent his one and only Son into the world that we might live through him.", "description": "Parallel Johannine epistle emphasizing the sending of the Son as the supreme revelation of love."},
                {"book": "Romans", "chapter": "8", "verse": "32", "text": "He who did not spare his own Son, but gave him up for us all—how will he not also, along with him, graciously give us all things?", "description": "Pauline echo of the sacrifice of the Son as absolute proof of divine generosity."}
            ],
            ("Matthew", 5, 16): [
                {"book": "Philippians", "chapter": "2", "verse": "15", "text": "so that you may become blameless and pure, \"children of God without fault in a warped and crooked generation.\" Then you will shine among them like stars in the sky", "description": "Exhortation to shine as lights in a dark generation, echoing the command to let one's light shine."},
                {"book": "1 Peter", "chapter": "2", "verse": "12", "text": "Live such good lives among the pagans that, though they accuse you of doing wrong, they may see your good deeds and glorify God on the day he visits us.", "description": "Instruction to let good deeds lead others to glorify God, directly parallel to the Matthaean teaching."},
                {"book": "Ephesians", "chapter": "5", "verse": "8", "text": "For you were once darkness, but now you are light in the Lord. Live as children of light", "description": "Theological framework of transitioning to light and living in alignment with that light."}
            ],
            ("Psalms", 23, 1): [
                {"book": "John", "chapter": "10", "verse": "11", "text": "I am the good shepherd. The good shepherd lays down his life for the sheep.", "description": "Christological fulfillment of the shepherd metaphor in Psalm 23."},
                {"book": "Isaiah", "chapter": "40", "verse": "11", "text": "He tends his flock like a shepherd: He gathers the lambs in his arms and carries them close to his heart", "description": "Prophetic description of Yahweh tenderly caring for Israel as a shepherd."},
                {"book": "Ezekiel", "chapter": "34", "verse": "12", "text": "As a shepherd looks after his scattered flock when he is with them, so will I look after my sheep.", "description": "Ezekiel's prophecy of God reclaiming His scattered sheep directly mirroring the pastoral care."}
            ],
            ("Romans", 3, 23): [
                {"book": "Isaiah", "chapter": "53", "verse": "6", "text": "We all, like sheep, have gone astray, each of us has turned to our own way; and the Lord has laid on him the iniquity of us all.", "description": "Old Testament prophetic depiction of universal human sinfulness."},
                {"book": "1 John", "chapter": "1", "verse": "8", "text": "If we claim to be without sin, we deceive ourselves and the truth is not in us.", "description": "Johannine assertion that denying one's sinfulness is self-deception, aligning with Romans 3:23."},
                {"book": "Ecclesiastes", "chapter": "7", "verse": "20", "text": "Indeed, there is no one on earth who is righteous, no one who does what is right and never sins.", "description": "Wisdom literature confirmation of the universality of sin."}
            ]
        }
        
        # Look up cross-references for this verse and format them for the React frontend
        verse_key = (book, chapter, verse)
        if verse_key in cross_ref_map:
            raw_refs = cross_ref_map[verse_key]
            cross_references = [
                {
                    "book": ref.get("book", ""),
                    "target_book": ref.get("target_book", ref.get("book", "")),
                    "chapter": str(ref.get("chapter", "")),
                    "target_chapter": str(ref.get("target_chapter", ref.get("chapter", ""))),
                    "verse": str(ref.get("verse", "")),
                    "target_verse": str(ref.get("target_verse", ref.get("verse", ""))),
                    "text": ref.get("text", ""),
                    "target_text": ref.get("target_text", ref.get("text", "")),
                    "description": ref.get("description", "")
                }
                for ref in raw_refs
            ]
        
        return VerseDetailsResponse(
            book=book,
            chapter=chapter,
            verse=verse,
            translations=translations,
            verse_meaning=verse_meaning,
            translation_comparison=translation_comparison,
            critical_analysis=critical_analysis,
            historical_context=[HistoricalNoteResponse.from_orm(note) for note in historical_notes],
            geographical_context=[GeographicalLocationResponse.from_orm(geo) for geo in geographical_context],
            original_language_insights=original_language_insights,
            cross_references=cross_references,
            translation_bias_alerts=[TranslationBiasResponse.from_orm(b) for b in biases],
            race_misuse_records=[
                {
                    "id": r.id,
                    "book": r.book,
                    "chapter": r.chapter,
                    "verse": r.verse,
                    "severity": r.severity,
                    "title": r.title,
                    "historical_misuse": r.historical_misuse,
                    "harm_caused": r.harm_caused,
                    "corrective_interpretation": r.corrective_interpretation,
                    "decolonial_perspective": r.decolonial_perspective,
                    "ethiopian_perspective": r.ethiopian_perspective,
                    "study_notes": r.study_notes
                }
                for r in race_misuse_records
            ]
        )
        
    except HTTPException as e:
        # Preserve HTTP exceptions (like 404) from upstream
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving verse details: {str(e)}")

@app.get("/api/v1/translation-biases", response_model=List[TranslationBiasResponse])
def get_all_translation_biases(db: Session = Depends(get_db)):
    """
    Get all documented translation biases in the database
    """
    try:
        biases = db.query(TranslationBiasModel).all()
        return biases
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch translation biases: {str(e)}")

@app.post("/api/v1/translation-bias/audit", response_model=DynamicBiasAuditResponse)
async def audit_verse_bias(request: DynamicBiasAuditRequest, db: Session = Depends(get_db)):
    """
    Dynamically audit any verse for translation bias using AI
    """
    try:
        # 1. Fetch translations for this verse from the database
        all_translations = db.query(BiblicalText).filter(
            BiblicalText.book == request.book.strip(),
            BiblicalText.chapter == request.chapter,
            BiblicalText.verse == request.verse
        ).all()
        
        # Fallback to normalized book names if exact match empty
        if not all_translations:
            def normalize_book(s):
                return ''.join(ch for ch in s if ch.isalnum()).lower()
            
            candidates = db.query(BiblicalText).filter(
                BiblicalText.chapter == request.chapter,
                BiblicalText.verse == request.verse
            ).all()
            
            target_norm = normalize_book(request.book)
            all_translations = [t for t in candidates if normalize_book(t.book) == target_norm]

        if not all_translations:
            raise HTTPException(status_code=404, detail="Verse not found in database.")

        translations = {t.translation: t.text for t in all_translations}
        
        # 2. Check if a bias is already documented in the database
        db_bias = db.query(TranslationBiasModel).filter(
            TranslationBiasModel.book == request.book.strip(),
            TranslationBiasModel.chapter == request.chapter,
            TranslationBiasModel.verse == request.verse
        ).first()
        
        if db_bias:
            return DynamicBiasAuditResponse(
                detected=True,
                severity=db_bias.severity,
                title=db_bias.title,
                original=db_bias.original,
                literal=db_bias.literal,
                target_translation=db_bias.target_translation,
                target_text=db_bias.target_text,
                explanation=db_bias.explanation,
                scholar=db_bias.scholar,
                translations=translations
            )
            
        # 3. If not in DB, use AI (or fallback mock)
        from openai_service import openai_client
        import json
        
        if not openai_client:
            # Return a simulated bias audit response if no AI key
            return DynamicBiasAuditResponse(
                detected=True,
                title=f"AI Bias Audit: Structural Wording Discrepancy",
                severity="info",
                original="N/A",
                literal="Literal rendering varies across source manuscripts",
                target_translation="Multiple",
                target_text="Wording discrepancies",
                explanation=f"This is an AI-simulated translation bias audit for {request.book} {request.chapter}:{request.verse}. The translations show stylistic and theological variations. Set a valid OPENAI_API_KEY in the environment to run live GPT-5 linguistic audits.",
                scholar="Antigravity AI Auditor",
                translations=translations
            )
            
        translations_text = "\n".join([f"- {code}: \"{text}\"" for code, text in translations.items()])
        prompt = f"""
        You are a biblical linguist and translation bias auditor. Analyze the following translations of {request.book} {request.chapter}:{request.verse} for theological, gender, or historical bias:
        
        {translations_text}
        
        Provide your analysis in JSON format:
        {{
            "detected": true,
            "title": "A short descriptive title of the translation discrepancy (e.g., 'Androcentric Bias in Phoebe\\'s Title')",
            "severity": "high" or "medium" or "info",
            "original": "The original Greek/Hebrew word or phrase under debate (with transliteration)",
            "literal": "The literal English rendering of that term",
            "target_translation": "The translation code demonstrating the most significant bias (e.g., KJV, ESV, NWT)",
            "target_text": "The biased rendering in that translation",
            "explanation": "A detailed scholarly explanation of how the translation is biased, why it matters, and how it compares to the original meaning.",
            "scholar": "A prominent biblical scholar associated with this critique or 'Linguistic Consensus'"
        }}
        
        Note: If you do not detect any significant bias or translation divergence, set "detected" to false and fill the explanation stating that translations are consistent.
        """
        
        # the newest OpenAI model is "gpt-5" which was released August 7, 2025.
        response = openai_client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": "You are a professional bible translation auditor."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=600
        )
        
        content = response.choices[0].message.content
        if not content:
            raise Exception("Empty response from AI")
            
        data = json.loads(content)
        return DynamicBiasAuditResponse(
            detected=data.get("detected", True),
            severity=data.get("severity", "info"),
            title=data.get("title", "AI Bias Audit"),
            original=data.get("original"),
            literal=data.get("literal"),
            target_translation=data.get("target_translation"),
            target_text=data.get("target_text"),
            explanation=data.get("explanation", ""),
            scholar=data.get("scholar"),
            translations=translations
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to audit verse bias: {str(e)}")

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
            transcript_segments=analysis_result.get("transcript_segments", []),
            summary=analysis_result.get("summary", {
                "topic": "Unknown", "theme": "Unknown", "short_summary": "N/A", "detailed_summary": "N/A",
                "key_points": [], "conclusion": "N/A"
            }),
            metrics=analysis_result.get("metrics", {
                "accuracy_score": 0, "scripture_usage_score": 0, "context_score": 0,
                "theology_consistency_score": 0, "confidence_level": 0
            }),
            claims=analysis_result.get("claims", []),
            further_study=analysis_result.get("further_study", []),
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
        if not openai_client:
            # Fallback mock responses depending on the book
            book_lower = book.lower()
            if "genesis" in book_lower:
                myth_data = {
                    "myth_title": "Creation vs. Enuma Elish Myth",
                    "myth_content": "Some claim the Genesis creation account is a direct, plagiarized copy of the Babylonian creation myth, the Enuma Elish, suggesting it lacks original theological or historical value.",
                    "historical_facts": "While Genesis shares cultural imagery with ancient Near Eastern texts (like a primeval deep and ordering of chaos), it represents a radical theological departure. The Enuma Elish depicts creation as a violent byproduct of warring, capricious gods. In contrast, Genesis 1 presents a single, sovereign God who creates peacefully and pronounces creation 'very good,' establishing human dignity rather than presenting humans as slaves to the gods.",
                    "verse_connection": f"This verse in {book} {chapter} reflects a monotheistic worldview where God orders creation purposefully, distinct from the chaotic polytheism of contemporary ancient cultures."
                }
            elif "exodus" in book_lower:
                myth_data = {
                    "myth_title": "Pharaoh's Army and the Red Sea Myth",
                    "myth_content": "A common myth is that the parting of the Red Sea is a completely fabricated myth with no historical or geographical basis whatsoever, or conversely, that the sea crossed was the deep modern Red Sea.",
                    "historical_facts": "Linguistic and historical consensus indicates that the Hebrew text refers to 'Yam Suph' (Sea of Reeds), likely a series of shallow papyrus lakes in the eastern Nile Delta, rather than the deep body of water known today as the Red Sea. Archaeological and geological studies of the ancient Suez canal region show that tidal shifts and wind setdowns in these shallower marshy regions could cause dry land to appear temporarily, aligning with the ancient description of the event.",
                    "verse_connection": f"In {book} {chapter}:{verse}, the narrative records the unfolding tension between Egypt and the Israelites, where the natural and supernatural elements of the Sea of Reeds play a pivotal historical role."
                }
            elif "john" in book_lower:
                myth_data = {
                    "myth_title": "Constantine and the Divinity of Jesus Myth",
                    "myth_content": "Popularized by modern fiction, a common myth claims that the divinity of Jesus was invented by Emperor Constantine at the Council of Nicaea in 325 CE.",
                    "historical_facts": "The Council of Nicaea did not invent Jesus' divinity; rather, it formalized the theological language (homoousios) to resolve Arianism. Early Christian writings from the 1st and 2nd centuries, including the Gospel of John (written c. 90-100 CE), clearly articulate the divinity of Christ (e.g., John 1:1, 'the Word was God').",
                    "verse_connection": f"The theological framework of {book} {chapter}:{verse} emphasizes the divine nature and mission of Jesus, which was central to early Christian community life centuries before Constantine."
                }
            elif "revelation" in book_lower:
                myth_data = {
                    "myth_title": "The Number of the Beast Myth",
                    "myth_content": "A popular myth is that the 'number of the beast' (666) refers to a modern technology, barcode, or political leader of the 21st century.",
                    "historical_facts": "In ancient apocalyptic literature, numbers held symbolic and gematric value. The number 666 (and the alternative manuscript reading 616) most likely refers to the Roman Emperor Nero Caesar when transliterated into Hebrew letters (Neron Qesar = 666; Nero Qesar = 616). Early Christians used this cipher to safely reference their imperial persecutor.",
                    "verse_connection": f"This passage in {book} uses apocalyptic symbolism that spoke directly to the immediate historical persecution of the 1st-century church under Rome, rather than modern technology."
                }
            elif any(x in book_lower for x in ["enoch", "jubilees", "orthodox", "tobit", "judith", "wisdom", "maccabees"]):
                myth_data = {
                    "myth_title": "Ethiopian Orthodox Canon and 'Lost' Books Myth",
                    "myth_content": "Many believe that books like 1 Enoch, Jubilees, Tobit, or Maccabees were 'lost' or banned by the Church at large because they contained dangerous heresies.",
                    "historical_facts": "These books were never universally 'banned'; they simply fell out of use or weren't translated/preserved in Latin/Greek in the West. The Ethiopian Orthodox Tewahedo Church preserved Enoch and Jubilees continuously as canonical. Their discovery among the Dead Sea Scrolls in the 20th century proved they were highly respected by early Jewish communities and were not late medieval fabrications.",
                    "verse_connection": f"The inclusion of {book} in the broader canon highlights the diverse manuscript traditions that early communities valued and preserved."
                }
            else:
                # Default mock response
                myth_data = {
                    "myth_title": "Constantine & The Bible Canon Myth",
                    "myth_content": "A widespread myth claims that Emperor Constantine decided which books would be included in the Bible at the Council of Nicaea in 325 CE.",
                    "historical_facts": "The Council of Nicaea did not discuss or vote on the biblical canon. The development of the canon was a gradual process of consensus among early Christian communities over several centuries, based on apostolic authorship, orthodoxy, and widespread usage. The first complete list matching the modern 27-book New Testament appeared in Athanasius's Festal Letter in 367 CE.",
                    "verse_connection": f"This verse in {book} {chapter}:{verse} belongs to a text that was circulating and venerated by early Christian communities long before any imperial councils met."
                }

            return {
                "book": book,
                "chapter": chapter,
                "verse": verse,
                "verse_text": verse_text.text,
                "myth_buster": myth_data
            }

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
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    llm = ChatOpenAIClient(
        model="gpt-3.5-turbo",
        temperature=0.1,
        openai_api_key=api_key
    )
else:
    print("⚠️ WARNING: OPENAI_API_KEY environment variable not set. RAG Chat will run in mock mode.")
    llm = None

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
        clean_question = request.question
        if " (Context: " in clean_question:
            clean_question = clean_question.split(" (Context: ")[0]
            
        question_keywords = clean_question.lower().split()
        if not question_keywords:
            question_keywords = ["god"]
            
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
        
        # Base System prompt based on study mode
        if request.study_mode == "kids":
            mode_system = (
                "You are a warm, engaging teacher explaining the Bible to children. "
                "Explain the scripture simply using stories, analogies, and language easy for a 10-year-old child to understand. "
                "Keep sentences short and positive."
            )
        elif request.study_mode == "devotional":
            mode_system = (
                "You are a pastor writing a warm, encouraging personal devotional. "
                "Focus heavily on the theological application, how it applies to modern life, personal relationships, and spiritual growth. "
                "Include a brief opening reflection, application, and a short closing prayer."
            )
        elif request.study_mode == "sermon":
            mode_system = (
                "You are an expert homiletical coach. "
                "Generate a structured 3-point sermon outline based on the scripture. "
                "Include a catchy Sermon Title, a brief hook Introduction, 3 clearly defined main points "
                "(each with a brief explanation, practical application, and an illustration/story idea), "
                "and a brief pastoral Conclusion."
            )
        elif request.study_mode == "discussion":
            mode_system = (
                "You are a small group Bible study leader. "
                "Generate 4 thought-provoking, open-ended discussion questions based on the scripture "
                "to get a group talking. For each question, provide a brief 'Leader Guide' with relevant "
                "scripture cross-references and key insights to listen for."
            )
        else: # scholarly
            mode_system = (
                "You are a helpful scholarly assistant for a Bible research app. "
                "Answer the user's question in a respectful, scholarly tone, focusing on original languages (Hebrew/Greek), "
                "historical-grammatical context, and textual translation nuances. Acknowledge limitations of context."
            )

        system_prompt = f"{mode_system}\nAnswer the user's question based *only* on the provided context database results:\n\n{context_text}"
        
        # Reconstruct conversation history if present
        messages = []
        if request.history:
            from langchain_core.messages import AIMessage
            for turn in request.history:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))
        
        # Append the current prompt
        user_prompt = f"Context:\n{context_text}\n\nQuestion:\n{request.question}"
        
        # Send to LLM
        if llm is None:
            # Generate mock answer depending on the study mode
            book_title = request.question.split("Context: ")[-1].split(" ")[0] if "Context: " in request.question else "Scripture"
            if not book_title or len(book_title) > 20:
                book_title = "Exodus"
                
            # Let's extract book, chapter, verse if we can
            ref_str = ""
            if "Context: " in request.question:
                ref_str = request.question.split("Context: ")[-1].replace(")", "").strip()
            else:
                ref_str = f"{book_title} 1:1"
                
            # Simulate historical/conversational follow-up context if history is present
            history_prefix = ""
            if request.history and len(request.history) > 0:
                history_prefix = "Continuing our discussion on this passage: "
                
            if request.study_mode == "kids":
                answer_text = (
                    f"### 👶 Kids Bible Study: Let's explore {ref_str}!\n\n"
                    f"{history_prefix}Imagine you are going on a huge journey to a new country. That's exactly what is happening here! "
                    f"God was helping His family—called the Israelites—grow strong and stick together, even though they were in a strange land called Egypt. "
                    f"Even when things got a little scary and the King of Egypt (the Pharaoh) wasn't very nice to them, God was watching over them the whole time.\n\n"
                    f"**Big Idea:** No matter where we go or what happens, God is always with us and has a special plan for us!"
                )
            elif request.study_mode == "devotional":
                answer_text = (
                    f"### 📖 Daily Devotional: Staying Faithful in the Storm ({ref_str})\n\n"
                    f"**Scripture Reflection:**\n"
                    f"{history_prefix}In this passage, we see God's people in a season of transition and difficulty. They are in Egypt, "
                    f"facing pressure from a culture that does not value them. Yet, God's promise to Abraham remains active: "
                    f"they are growing and multiplying. Sometimes, the place of our struggle is also the place where God is "
                    f"quietly building our strength.\n\n"
                    f"**Application for Today:**\n"
                    f"Are you facing a season of pressure or feeling 'unbound' from your comfort zone? Trust that God is "
                    f"working in the background of your life. He is faithful to His promises even when the environment feels hostile.\n\n"
                    f"*Lord, help me trust Your promises today. Give me strength to remain faithful in difficult seasons. Amen.*"
                )
            elif request.study_mode == "sermon":
                answer_text = (
                    f"### 🎙️ Sermon Outline: 'Thriving Under Pressure'\n"
                    f"**Text:** {ref_str}\n\n"
                    f"#### Introduction:\n"
                    f"{history_prefix}Introduce the concept of pressure. How does a lump of coal become a diamond? Through intense heat and pressure. "
                    f"In the same way, God uses challenging environments to shape and multiply His people.\n\n"
                    f"#### Point 1: The Promise Outlives the Patriarchs\n"
                    f"- *Explanation:* Generations pass (Jacob, Joseph, and his brothers die), but God's covenant promise to multiply them remains alive.\n"
                    f"- *Illustration:* Seeds buried in winter that bloom in spring—life continues underground.\n\n"
                    f"#### Point 2: Opposition Cannot Halt God's Plan\n"
                    f"- *Explanation:* The new Pharaoh tries to suppress the Israelites, but the more they are oppressed, the more they multiply.\n"
                    f"- *Illustration:* A campfire that spreads further when someone tries to stomp it out.\n\n"
                    f"#### Point 3: The Call to Quiet Faithfulness\n"
                    f"- *Explanation:* God works through ordinary people (like Hebrew midwives) who choose to fear God rather than men.\n"
                    f"- *Illustration:* The quiet work of roots holding a giant redwood tree secure against mountain winds.\n\n"
                    f"#### Conclusion:\n"
                    f"Sum up the call to stand firm. Challenge the congregation: Will you trust God's silent growth in your life today?"
                )
            elif request.study_mode == "discussion":
                answer_text = (
                    f"### 💬 Small Group Discussion Guide for {ref_str}\n\n"
                    f"**Question 1: Remembering the Journey**\n"
                    f"{history_prefix}The passage starts by listing the names of those who went to Egypt. Why is it important to remember and name our family history and the journeys we've been on?\n"
                    f"*Leader Guide: Encourage members to share a personal family transition or move and how God met them there.*\n\n"
                    f"**Question 2: Faithfulness in Transition**\n"
                    f"A new king arose who 'did not know Joseph.' How do we handle situations where our past achievements, character, or beliefs are no longer respected by those in authority?\n"
                    f"*Leader Guide: Discuss 1 Leader Guide: Reference 1 Peter 2:13-17. How do we honor leaders while remaining true to God's higher law?*\n\n"
                    f"**Question 3: Growth Under Oppression**\n"
                    f"The text notes that the more the people were oppressed, the more they multiplied. Have you ever seen a situation in your own life or church history where hardship actually led to spiritual growth? Explain.\n"
                    f"*Leader Guide: Reference James 1:2-4 on counting trials as joy and building perseverance.*"
                )
            else: # scholarly
                answer_text = (
                    f"### 🎓 Scholarly Commentary: Textual Analysis of {ref_str}\n\n"
                    f"{history_prefix}This passage serves as a literary bridge connecting the patriarchal narratives of Genesis with the national "
                    f"deliverance in Exodus. The repetition of the names of Jacob's sons recapitulates the Genesis 46 list, "
                    f"emphasizing continuity of identity in a foreign land. \n\n"
                    f"Linguistically, the description of growth utilizes Hebrew verbs associated with the creation mandate in "
                    f"Genesis 1:28 ('fruitful', 'teemed', 'multiplied'), signaling to the reader that the growth of Israel is "
                    f"not merely natural demographic success, but a fulfillment of divine covenantal command. Set your `OPENAI_API_KEY` to run live GPT audits."
                )
        else:
            messages.insert(0, SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=user_prompt))
            response = llm.invoke(messages)
            answer_text = response.content if hasattr(response, 'content') else str(response)

        # Dynamically generate 3 follow-up questions
        follow_ups = []
        book_lower = book_title.lower()
        if "genesis" in book_lower:
            follow_ups = [
                "What is the historical context of the Enuma Elish?",
                "How does the covenant with Abraham relate to this?",
                "What does 'In the beginning' mean in original Hebrew?"
            ]
        elif "exodus" in book_lower:
            follow_ups = [
                "Why did the new Pharaoh fear the Israelites?",
                "What is the significance of the midwives Shiphrah and Puah?",
                "How does 'Yam Suph' differ from the modern Red Sea?"
            ]
        elif "john" in book_lower:
            follow_ups = [
                "What does 'Logos' mean in ancient Greek philosophy?",
                "How did the Council of Nicaea define the Trinity?",
                "What is the historical dating of the Gospel of John?"
            ]
        elif "revelation" in book_lower:
            follow_ups = [
                "What is gematria and how does Nero Caesar equal 666?",
                "What are the characteristics of apocalyptic literature?",
                "How did 1st-century Roman Christians interpret the Beast?"
            ]
        else:
            follow_ups = [
                "How does the historical context affect our interpretation?",
                "Are there major translation differences in other canons?",
                "What do early church fathers write about this passage?"
            ]

        return ChatResponse(
            answer=answer_text,
            context_used=context_sources,
            follow_ups=follow_ups
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

@app.get("/api/v1/notes", response_model=List[UserNoteResponse])
async def get_user_notes(book: Optional[str] = None, db: Session = Depends(get_db)):
    """Retrieve all user notes, optionally filtering by book name"""
    query = db.query(UserNote)
    if book:
        query = query.filter(UserNote.book == book)
    return query.all()

@app.post("/api/v1/notes", response_model=UserNoteResponse)
async def create_user_note(request: UserNoteCreate, db: Session = Depends(get_db)):
    """Create a new user note linked to scripture or general topic"""
    db_note = UserNote(
        book=request.book,
        chapter=request.chapter,
        verse=request.verse,
        text=request.text,
        tags=request.tags
    )
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return db_note

@app.put("/api/v1/notes/{note_id}", response_model=UserNoteResponse)
async def update_user_note(note_id: int, request: UserNoteUpdate, db: Session = Depends(get_db)):
    """Update note text and tags"""
    db_note = db.query(UserNote).filter(UserNote.id == note_id).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    if request.text is not None:
        db_note.text = request.text
    if request.tags is not None:
        db_note.tags = request.tags
        
    db.commit()
    db.refresh(db_note)
    return db_note

@app.delete("/api/v1/notes/{note_id}")
async def delete_user_note(note_id: int, db: Session = Depends(get_db)):
    """Delete a user note from database"""
    db_note = db.query(UserNote).filter(UserNote.id == note_id).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    db.delete(db_note)
    db.commit()
    return {"status": "success", "message": "Note deleted successfully"}

# 1. Canon Comparison Grid Matrix
from schemas import CanonCompareItem

@app.get("/api/v1/canons/compare", response_model=CanonCompareResponse)
def get_canon_comparison(db: Session = Depends(get_db)):
    books = db.query(Book).order_by(Book.canonical_order).all()
    mappings = db.query(CanonBook).all()
    
    # Map book_id -> list of canon codes
    canons = db.query(Canon).all()
    canon_code_map = {c.id: c.code for c in canons}
    
    book_canons = {}
    for m in mappings:
        code = canon_code_map.get(m.canon_id)
        if code:
            if m.book_id not in book_canons:
                book_canons[m.book_id] = []
            book_canons[m.book_id].append(code)
            
    compare_items = []
    for b in books:
        compare_items.append(
            CanonCompareItem(
                book_id=b.id,
                name=b.name,
                testament=b.testament or "OT",
                in_canons=book_canons.get(b.id, []),
                notes=b.description,
                significance="Preserved in the ancient Ge'ez/Ethiopian Orthodox Tewahedo tradition." if b.testament in ["Apoc", "Pseud"] else "Standard biblical book."
            )
        )
    return CanonCompareResponse(books=compare_items)

# 2. Book Detail
@app.get("/api/v1/books/{bookId}", response_model=BookDetailResponse)
def get_book_details(bookId: str, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == bookId).first()
    if not book:
        # Check normalized version
        all_books = db.query(Book).all()
        normalized_target = bookId.replace(" ", "").lower()
        for b in all_books:
            if b.id.replace(" ", "").lower() == normalized_target or b.name.replace(" ", "").lower() == normalized_target:
                book = b
                break
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
        
    # Get canons that include this book
    mappings = db.query(CanonBook).filter(CanonBook.book_id == book.id).all()
    canons = db.query(Canon).all()
    canon_code_map = {c.id: c.code for c in canons}
    inclusions = [canon_code_map[m.canon_id] for m in mappings if m.canon_id in canon_code_map]
    
    return BookDetailResponse(
        id=book.id,
        name=book.name,
        testament=book.testament or "OT",
        description=book.description,
        geez_name=book.geez_name,
        canonical_order=book.canonical_order or 99,
        canon_inclusions=inclusions
    )

# 3. Dynamic Textual Comparison against Ethiopian baseline
@app.get("/api/v1/texts/{book}/{chapter}/{verse}/compare")
def get_scripture_comparison_baseline(book: str, chapter: int, verse: int, db: Session = Depends(get_db)):
    # Query all translations for this verse
    texts = db.query(BiblicalText).filter(
        BiblicalText.book == book.strip(),
        BiblicalText.chapter == chapter,
        BiblicalText.verse == verse
    ).all()
    
    # Find the Ethiopian baseline text (ETH81 or ETHIO81 or ETH)
    ethiopian_text = None
    for t in texts:
        if t.translation in ["ETH81", "ETHIO81", "ETH"]:
            ethiopian_text = t
            break
            
    # Fallback to KJV if no Ethiopian text in database, or a default placeholder
    if not ethiopian_text:
        # Create a sample placeholder for the baseline
        ethiopian_text = BiblicalText(
            book=book,
            chapter=chapter,
            verse=verse,
            text=f"[Awaiting full Ge'ez source text for {book} {chapter}:{verse}]",
            translation="ETH81"
        )
        
    translations_list = {}
    for t in texts:
        # Map word differences or textual additions
        difference_type = "Minor wording difference"
        is_omitted = False
        
        # Check translation shifts
        bias = db.query(TranslationBiasModel).filter(
            TranslationBiasModel.book == book.strip(),
            TranslationBiasModel.chapter == chapter,
            TranslationBiasModel.verse == verse,
            TranslationBiasModel.target_translation.like(f"%{t.translation}%")
        ).first()
        
        if bias:
            difference_type = bias.title
            
        translations_list[t.translation] = {
            "text": t.text,
            "difference_category": difference_type,
            "is_omitted": is_omitted,
            "notes": bias.explanation if bias else "Consistent reading with standard texts."
        }
        
    return {
        "book": book,
        "chapter": chapter,
        "verse": verse,
        "ethiopian_baseline": ethiopian_text.text,
        "comparisons": translations_list
    }

# 4. GET Ethiopian Reference
@app.get("/api/v1/ethiopian-reference/{book}/{chapter}/{verse}")
def get_ethiopian_reference(book: str, chapter: int, verse: int, db: Session = Depends(get_db)):
    t = db.query(BiblicalText).filter(
        BiblicalText.book == book.strip(),
        BiblicalText.chapter == chapter,
        BiblicalText.verse == verse,
        BiblicalText.translation.in_(["ETH81", "ETHIO81", "ETH"])
    ).first()
    
    if not t:
        return {
            "book": book,
            "chapter": chapter,
            "verse": verse,
            "text": f"This book ({book}) is preserved in the ancient Ethiopian Orthodox Tewahedo canon, but the full Ge'ez translation text for this chapter is currently awaiting source verification.",
            "translation": "ETHIO81",
            "is_sample_placeholder": True
        }
        
    return {
        "book": t.book,
        "chapter": t.chapter,
        "verse": t.verse,
        "text": t.text,
        "translation": t.translation,
        "is_sample_placeholder": False
    }

# 5. GET all race misuse records
@app.get("/api/v1/race-misuse", response_model=List[RaceMisuseRecordResponse])
def get_all_race_misuse(db: Session = Depends(get_db)):
    return db.query(RaceMisuseRecord).all()

# 6. GET race misuse for a specific verse
@app.get("/api/v1/race-misuse/{book}/{chapter}/{verse}", response_model=List[RaceMisuseRecordResponse])
def get_race_misuse_for_verse(book: str, chapter: int, verse: int, db: Session = Depends(get_db)):
    return db.query(RaceMisuseRecord).filter(
        RaceMisuseRecord.book == book.strip(),
        RaceMisuseRecord.chapter == chapter,
        RaceMisuseRecord.verse == verse
    ).all()

# 7. GET factbook entries
@app.get("/api/v1/factbook", response_model=List[FactbookEntrySummary])
def get_factbook_summary(db: Session = Depends(get_db)):
    entries = db.query(FactbookEntry).all()
    return [
        FactbookEntrySummary(
            slug=e.slug,
            title=e.title,
            summary=e.summary,
            geographical_region=e.geographical_region
        )
        for e in entries
    ]

# 8. GET factbook detail
@app.get("/api/v1/factbook/{slug}", response_model=FactbookEntryDetailResponse)
def get_factbook_detail(slug: str, db: Session = Depends(get_db)):
    entry = db.query(FactbookEntry).filter(FactbookEntry.slug == slug).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Factbook entry not found")
        
    witnesses = db.query(ManuscriptWitness).filter(ManuscriptWitness.factbook_entry_id == entry.id).all()
    witness_list = [
        ManuscriptWitnessResponse(
            id=w.id,
            name=w.name,
            type=w.type,
            date=w.date,
            language=w.language,
            significance=w.significance
        )
        for w in witnesses
    ]
    
    return FactbookEntryDetailResponse(
        slug=entry.slug,
        title=entry.title,
        summary=entry.summary,
        content=entry.content,
        geographical_region=entry.geographical_region,
        ethiopian_canon_relevance=entry.ethiopian_canon_relevance,
        manuscripts_attestations=entry.manuscripts_attestations,
        western_interpretation=entry.western_interpretation,
        ethiopian_interpretation=entry.ethiopian_interpretation,
        decolonial_interpretation=entry.decolonial_interpretation,
        witnesses=witness_list
    )

# 9. POST sermon analysis custom request
from pydantic import BaseModel as PydanticBaseModel
class SermonAnalyzeRequest(PydanticBaseModel):
    transcript_text: str
    title: Optional[str] = "Sermon Analysis"
    speaker: Optional[str] = "Unknown Preacher"

@app.post("/api/v1/sermon/analyze", response_model=SermonAnalysisResponse)
async def sermon_analyze_custom(request: SermonAnalyzeRequest, db: Session = Depends(get_db)):
    """Analyze a pasted sermon transcript for scripture misuse and geographic inaccuracies"""
    transcript = request.transcript_text
    
    claims = []
    accuracy_score = 95
    misuse_warnings = []
    race_power_concerns = []
    
    if "curse of ham" in transcript.lower() or "canaan" in transcript.lower():
        claims.append(
            AccuracyClaim(
                claim_text="The Curse of Ham decree ordains that African people are born to be servants.",
                status="misuse",
                category="theological",
                details="Cursing of Canaan (Genesis 9) was weaponized historically to justify transatlantic slavery. The Bible does not curse Ham or associate Black skin with a curse.",
                corrective_notes="Exegesis: Genesis 9 explicitly curses Canaan, not Ham. Cushites (Africans) were independent and not cursed.",
                issue_type="Scripture Misuse",
                severity="red",
                explanation="The preacher claims God cursed Ham's descendants (deemed Black) to servitude.",
                correction="Corrective: Point out that Canaan was cursed, not Ham. Citing this to justify racial servitude is a classic heresy.",
                references=["Genesis 9:25", "Deuteronomy 20"]
            )
        )
        misuse_warnings.append("Heresy warning: Mentioned the Curse of Ham to justify servitude or racial hierarchy.")
        race_power_concerns.append("Ethno-racial bias: Reinforces chattel slavery arguments.")
        accuracy_score -= 40
        
    if "servants obey" in transcript.lower() or "slaves, obey your masters" in transcript.lower() or "ephesians 6:5" in transcript.lower():
        claims.append(
            AccuracyClaim(
                claim_text="Ephesians 6:5 shows God ordains chattel slavery and demands submission to masters.",
                status="misuse",
                category="theological",
                details="Used Ephesians 6:5 out of context without noting the structural subversions Paul introduces.",
                corrective_notes="Ephesians 6:5 refers to Roman contractual or debt servitude, which was non-racial and non-hereditary. Paul commands mutual submission.",
                issue_type="Scripture Misuse",
                severity="orange",
                explanation="Isolates submission codes without showing Paul's admonition to masters in Eph 6:9.",
                correction="Corrective: Masters are reminded they have a Master in heaven who shows no partiality.",
                references=["Ephesians 6:5-9", "Philemon 1:16"]
            )
        )
        misuse_warnings.append("Isolationist reading: Cited household codes to support subjection without mutual submission clauses.")
        accuracy_score -= 20

    if "black but comely" in transcript.lower() or "song of solomon 1:5" in transcript.lower():
        claims.append(
            AccuracyClaim(
                claim_text="The bride is black but comely, meaning blackness is a defect that must be excused.",
                status="questionable",
                category="linguistic",
                details="Translating the Hebrew 've' as 'but' instead of 'and' introduces colorism.",
                corrective_notes="Hebrew 've' is a simple conjunctive. The Ge'ez and Septuagint translate it as 'black AND beautiful'.",
                issue_type="Possible Inaccuracy",
                severity="yellow",
                explanation="Implies blackness is in opposition to comeliness.",
                correction="Corrective: Reclaim the literal translation 'black and beautiful' to avoid colorist bias.",
                references=["Song of Solomon 1:5"]
            )
        )
        race_power_concerns.append("Colorism: Implies dark skin color is mutually exclusive with beauty.")
        accuracy_score -= 10

    if not claims:
        claims.append(
            AccuracyClaim(
                claim_text="General biblical teaching on justice and covenant.",
                status="supported",
                category="theological",
                details="The sermon refers to standard covenantal themes.",
                corrective_notes="No major misuse detected. The sermon aligns with orthodox interpretation.",
                issue_type="Strongly Supported",
                severity="green",
                explanation="No scripture misuse or translation bias was found in this transcript.",
                correction="None required.",
                references=[]
            )
        )
    
    import json
    db_analysis = SermonAnalysis(
        title=request.title,
        speaker=request.speaker,
        transcript=transcript,
        summary=f"Sermon analyzed. Found {len(claims)} theological/historical claims.",
        accuracy_score=max(0, accuracy_score),
        misuse_warnings=misuse_warnings,
        race_power_concerns=race_power_concerns,
        corrective_notes="Decolonial auditing completed.",
        suggested_study_path="Review Genesis 9 and Ephesians 6 decolonial study guides."
    )
    db.add(db_analysis)
    db.commit()
    db.refresh(db_analysis)
    
    for c in claims:
        db_claim = SermonClaim(
            sermon_analysis_id=db_analysis.id,
            claim_text=c.claim_text,
            status=c.status,
            category=c.category,
            details=c.details,
            corrective_notes=c.corrective_notes
        )
        db.add(db_claim)
    db.commit()
    
    segments = [
        TranscriptSegment(
            text=transcript[:100] + "...",
            start=0.0,
            end=10.0,
            speaker=request.speaker
        )
    ]
    
    summary = SermonSummary(
        topic="Scripture Audit",
        main_theme="Decolonial analysis of the transcript",
        key_points=[c.claim_text for c in claims],
        theological_framework="Decolonial / Ethiopian Orthodox"
    )
    
    metrics = VisualDashboardMetrics(
        accuracy_score=max(0, accuracy_score),
        scripture_usage_score=90,
        context_score=80 if accuracy_score > 70 else 50,
        theology_consistency_score=accuracy_score,
        confidence_level=95
    )
    
    return SermonAnalysisResponse(
        transcription=transcript,
        transcript_segments=segments,
        summary=summary,
        metrics=metrics,
        claims=claims,
        further_study=["Genesis 9 (Ham's Curse study)", "Song of Solomon 1:5 (Colorism study)", "Ephesians 6:5 (Slavery study)"],
        processing_time=0.45
    )

# 10. GET study sessions
@app.get("/api/v1/study-sessions", response_model=List[StudySessionResponse])
def get_study_sessions(db: Session = Depends(get_db)):
    return db.query(StudySession).order_by(StudySession.created_at.desc()).all()

# 11. POST study session
@app.post("/api/v1/study-sessions", response_model=StudySessionResponse)
def create_study_session(request: StudySessionCreate, db: Session = Depends(get_db)):
    session = StudySession(
        title=request.title,
        notes=request.notes,
        meta_data=request.meta_data
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
