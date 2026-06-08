#!/usr/bin/env python3

"""
Liberation Bible Project - Public Domain Translation Ingestion

Ingests ASV (American Standard Version) and WEB (World English Bible) translations
Both are fully public domain and align with the decolonization mission
"""

import requests
import time
import hashlib
from sqlalchemy.orm import Session
from database import engine, SessionLocal
from models import BiblicalText, Translation, Base
from contextlib import contextmanager

# All 66 biblical books in order
BIBLE_BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth",
    "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", 
    "Ezra", "Nehemiah", "Esther", "Job", "Psalms", "Proverbs", "Ecclesiastes", 
    "Song of Solomon", "Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel",
    "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", 
    "Zephaniah", "Haggai", "Zechariah", "Malachi",
    "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians", 
    "2 Corinthians", "Galatians", "Ephesians", "Philippians", "Colossians", 
    "1 Thessalonians", "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", 
    "Philemon", "Hebrews", "James", "1 Peter", "2 Peter", "1 John", "2 John", 
    "3 John", "Jude", "Revelation"
]

def get_book_abbreviation(book_name):
    """Get abbreviated book names for API calls"""
    abbreviations = {
        "Genesis": "gen", "Exodus": "exo", "Leviticus": "lev", "Numbers": "num", 
        "Deuteronomy": "deu", "Joshua": "jos", "Judges": "jdg", "Ruth": "rut",
        "1 Samuel": "1sa", "2 Samuel": "2sa", "1 Kings": "1ki", "2 Kings": "2ki",
        "1 Chronicles": "1ch", "2 Chronicles": "2ch", "Ezra": "ezr", "Nehemiah": "neh", 
        "Esther": "est", "Job": "job", "Psalms": "psa", "Proverbs": "pro", 
        "Ecclesiastes": "ecc", "Song of Solomon": "sng", "Isaiah": "isa", 
        "Jeremiah": "jer", "Lamentations": "lam", "Ezekiel": "ezk", "Daniel": "dan",
        "Hosea": "hos", "Joel": "jol", "Amos": "amo", "Obadiah": "oba", "Jonah": "jon", 
        "Micah": "mic", "Nahum": "nam", "Habakkuk": "hab", "Zephaniah": "zep", 
        "Haggai": "hag", "Zechariah": "zec", "Malachi": "mal",
        "Matthew": "mat", "Mark": "mrk", "Luke": "luk", "John": "jhn", "Acts": "act", 
        "Romans": "rom", "1 Corinthians": "1co", "2 Corinthians": "2co", 
        "Galatians": "gal", "Ephesians": "eph", "Philippians": "php", 
        "Colossians": "col", "1 Thessalonians": "1th", "2 Thessalonians": "2th", 
        "1 Timothy": "1ti", "2 Timothy": "2ti", "Titus": "tit", "Philemon": "phm", 
        "Hebrews": "heb", "James": "jas", "1 Peter": "1pe", "2 Peter": "2pe", 
        "1 John": "1jn", "2 John": "2jn", "3 John": "3jn", "Jude": "jud", 
        "Revelation": "rev"
    }
    return abbreviations.get(book_name, book_name.lower())

def add_translation_metadata(db: Session):
    """Add translation metadata to database"""
    translations = [
        {
            "code": "ASV",
            "name": "American Standard Version",
            "description": "The American Standard Version of 1901, public domain revision of the Revised Version",
            "language": "English",
            "source_text": "Hebrew Masoretic Text and Greek Textus Receptus",
            "year_published": 1901,
            "is_original_language": False,
            "is_public_domain": True
        },
        {
            "code": "WEB",
            "name": "World English Bible",
            "description": "Modern public domain Bible translation based on the Majority Text",
            "language": "English", 
            "source_text": "Hebrew Masoretic Text and Greek Majority Text",
            "year_published": 2000,
            "is_original_language": False,
            "is_public_domain": True
        }
    ]
    
    for trans_data in translations:
        # Check if translation already exists
        existing = db.query(Translation).filter(Translation.code == trans_data["code"]).first()
        if not existing:
            translation = Translation(**trans_data)
            db.add(translation)
            print(f"✅ Added {trans_data['name']} translation metadata")
        else:
            print(f"⚠️  {trans_data['name']} already exists, skipping")
    
    db.commit()

def ingest_bible_from_api(translation_code: str, db: Session):
    """Ingest bible translation from bible-api.com (public domain focus)"""
    
    print(f"\n🔄 Starting {translation_code} translation ingestion...")
    
    # Get translation ID
    translation = db.query(Translation).filter(Translation.code == translation_code).first()
    if not translation:
        print(f"❌ Translation {translation_code} not found in database")
        return
    
    total_verses = 0
    failed_requests = 0
    
    for book in BIBLE_BOOKS:
        print(f"📖 Processing {book}...")
        
        try:
            # Use bible-api.com - supports ASV and WEB 
            # Format: GET https://bible-api.com/{book}/{chapter}:{verse}?translation={code}
            book_abbrev = get_book_abbreviation(book)
            
            # Get book info first to know how many chapters
            # We'll iterate through standard chapter counts
            chapter_counts = get_standard_chapter_counts()
            max_chapters = chapter_counts.get(book, 50)  # Default fallback
            
            for chapter in range(1, max_chapters + 1):
                # Get all verses for this chapter
                url = f"https://bible-api.com/{book_abbrev}/{chapter}"
                if translation_code.lower() != "kjv":  # KJV is default
                    url += f"?translation={translation_code.lower()}"
                
                try:
                    response = requests.get(url, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Handle both single verse and chapter responses
                        if isinstance(data, dict) and 'verses' in data:
                            verses = data['verses']
                        elif isinstance(data, dict) and 'text' in data:
                            verses = [data]  # Single verse format
                        else:
                            print(f"⚠️  Unexpected response format for {book} {chapter}")
                            continue
                        
                        for verse_data in verses:
                            verse_num = verse_data.get('verse')
                            verse_text = verse_data.get('text', '')
                            
                            if verse_num and verse_text:
                                # Check if verse already exists
                                existing = db.query(BiblicalText).filter(
                                    BiblicalText.book == book,
                                    BiblicalText.chapter == chapter,
                                    BiblicalText.verse == verse_num,
                                    BiblicalText.translation == translation_code
                                ).first()
                                
                                if not existing:
                                    biblical_text = BiblicalText(
                                        book=book,
                                        chapter=chapter,
                                        verse=verse_num,
                                        text=verse_text.strip(),
                                        translation=translation_code,
                                        translation_id=translation.id
                                    )
                                    db.add(biblical_text)
                                    total_verses += 1
                        
                        # Commit every chapter to avoid large transactions
                        db.commit()
                        
                    elif response.status_code == 404:
                        # Reached end of book, break to next book
                        break
                    else:
                        print(f"❌ API error {response.status_code} for {book} {chapter}")
                        failed_requests += 1
                    
                    # Rate limiting - be respectful to free API
                    time.sleep(0.1)
                    
                except requests.RequestException as e:
                    print(f"❌ Network error for {book} {chapter}: {e}")
                    failed_requests += 1
                    continue
        
        except Exception as e:
            print(f"❌ Error processing {book}: {e}")
            continue
    
    print(f"\n✅ {translation_code} ingestion complete!")
    print(f"📊 Total verses imported: {total_verses}")
    print(f"⚠️  Failed requests: {failed_requests}")

def get_standard_chapter_counts():
    """Standard chapter counts for biblical books"""
    return {
        "Genesis": 50, "Exodus": 40, "Leviticus": 27, "Numbers": 36, "Deuteronomy": 34,
        "Joshua": 24, "Judges": 21, "Ruth": 4, "1 Samuel": 31, "2 Samuel": 24,
        "1 Kings": 22, "2 Kings": 25, "1 Chronicles": 29, "2 Chronicles": 36,
        "Ezra": 10, "Nehemiah": 13, "Esther": 10, "Job": 42, "Psalms": 150,
        "Proverbs": 31, "Ecclesiastes": 12, "Song of Solomon": 8, "Isaiah": 66,
        "Jeremiah": 52, "Lamentations": 5, "Ezekiel": 48, "Daniel": 12,
        "Hosea": 14, "Joel": 3, "Amos": 9, "Obadiah": 1, "Jonah": 4, "Micah": 7,
        "Nahum": 3, "Habakkuk": 3, "Zephaniah": 3, "Haggai": 2, "Zechariah": 14, "Malachi": 4,
        "Matthew": 28, "Mark": 16, "Luke": 24, "John": 21, "Acts": 28, "Romans": 16,
        "1 Corinthians": 16, "2 Corinthians": 13, "Galatians": 6, "Ephesians": 6,
        "Philippians": 4, "Colossians": 4, "1 Thessalonians": 5, "2 Thessalonians": 3,
        "1 Timothy": 6, "2 Timothy": 4, "Titus": 3, "Philemon": 1, "Hebrews": 13,
        "James": 5, "1 Peter": 5, "2 Peter": 3, "1 John": 5, "2 John": 1, "3 John": 1,
        "Jude": 1, "Revelation": 22
    }

@contextmanager
def get_db_session():
    """Context manager for database sessions"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def main():
    """Main ingestion function"""
    print("🌍 Liberation Bible Project - Public Domain Translation Ingestion")
    print("=" * 70)
    
    try:
        with get_db_session() as db:
            # Add translation metadata
            add_translation_metadata(db)
            
            # Ingest ASV translation
            print("\n📚 PHASE 1: American Standard Version (ASV)")
            ingest_bible_from_api("ASV", db)
            
            # Ingest WEB translation  
            print("\n📚 PHASE 2: World English Bible (WEB)")
            ingest_bible_from_api("WEB", db)
            
        print("\n🎉 All public domain translations imported successfully!")
        print("📊 Summary:")
        
        with get_db_session() as db:
            kjv_count = db.query(BiblicalText).filter(BiblicalText.translation == "KJV").count()
            asv_count = db.query(BiblicalText).filter(BiblicalText.translation == "ASV").count()
            web_count = db.query(BiblicalText).filter(BiblicalText.translation == "WEB").count()
            
            print(f"   KJV verses: {kjv_count:,}")
            print(f"   ASV verses: {asv_count:,}")
            print(f"   WEB verses: {web_count:,}")
            print(f"   Total verses: {kjv_count + asv_count + web_count:,}")
            
    except Exception as e:
        print(f"💥 Fatal error during ingestion: {e}")
        raise

if __name__ == "__main__":
    main()