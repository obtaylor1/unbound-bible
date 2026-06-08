#!/usr/bin/env python3
"""
KJV Bible Text Ingestion Script
Downloads and imports the King James Version Bible from Project Gutenberg into the database.
"""

import re
import requests
from sqlalchemy.orm import Session
from database import engine, get_db
from models import Base, BiblicalText, Translation, LanguageEnum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Project Gutenberg KJV Bible URL - Using File #30 which has complete 31,102 verses
KJV_URL = "https://www.gutenberg.org/files/30/30-0.txt"

# Book name mapping from Project Gutenberg File #30 format to standard format
BOOK_MAPPING = {
    "Book 01 Genesis": "Genesis",
    "Book 02 Exodus": "Exodus", 
    "Book 03 Leviticus": "Leviticus",
    "Book 04 Numbers": "Numbers",
    "Book 05 Deuteronomy": "Deuteronomy",
    "Book 06 Joshua": "Joshua",
    "Book 07 Judges": "Judges",
    "Book 08 Ruth": "Ruth",
    "Book 09 1 Samuel": "1 Samuel",
    "Book 10 2 Samuel": "2 Samuel",
    "Book 11 1 Kings": "1 Kings",
    "Book 12 2 Kings": "2 Kings",
    "Book 13 1 Chronicles": "1 Chronicles",
    "Book 14 2 Chronicles": "2 Chronicles",
    "Book 15 Ezra": "Ezra",
    "Book 16 Nehemiah": "Nehemiah",
    "Book 17 Esther": "Esther",
    "Book 18 Job": "Job",
    "Book 19 Psalms": "Psalms",
    "Book 20 Proverbs": "Proverbs",
    "Book 21 Ecclesiastes": "Ecclesiastes",
    "Book 22 Song of Solomon": "Song of Solomon",
    "Book 23 Isaiah": "Isaiah",
    "Book 24 Jeremiah": "Jeremiah",
    "Book 25 Lamentations": "Lamentations",
    "Book 26 Ezekiel": "Ezekiel",
    "Book 27 Daniel": "Daniel",
    "Book 28 Hosea": "Hosea",
    "Book 29 Joel": "Joel",
    "Book 30 Amos": "Amos",
    "Book 31 Obadiah": "Obadiah",
    "Book 32 Jonah": "Jonah",
    "Book 33 Micah": "Micah",
    "Book 34 Nahum": "Nahum",
    "Book 35 Habakkuk": "Habakkuk",
    "Book 36 Zephaniah": "Zephaniah",
    "Book 37 Haggai": "Haggai",
    "Book 38 Zechariah": "Zechariah",
    "Book 39 Malachi": "Malachi",
    "Book 40 Matthew": "Matthew",
    "Book 41 Mark": "Mark",
    "Book 42 Luke": "Luke",
    "Book 43 John": "John",
    "Book 44 Acts": "Acts",
    "Book 45 Romans": "Romans",
    "Book 46 1 Corinthians": "1 Corinthians",
    "Book 47 2 Corinthians": "2 Corinthians",
    "Book 48 Galatians": "Galatians",
    "Book 49 Ephesians": "Ephesians",
    "Book 50 Philippians": "Philippians",
    "Book 51 Colossians": "Colossians",
    "Book 52 1 Thessalonians": "1 Thessalonians",
    "Book 53 2 Thessalonians": "2 Thessalonians",
    "Book 54 1 Timothy": "1 Timothy",
    "Book 55 2 Timothy": "2 Timothy",
    "Book 56 Titus": "Titus",
    "Book 57 Philemon": "Philemon",
    "Book 58 Hebrews": "Hebrews",
    "Book 59 James": "James",
    "Book 60 1 Peter": "1 Peter",
    "Book 61 2 Peter": "2 Peter",
    "Book 62 1 John": "1 John",
    "Book 63 2 John": "2 John", 
    "Book 64 3 John": "3 John",
    "Book 65 Jude": "Jude",
    "Book 66 Revelation": "Revelation"
}

def download_kjv_text():
    """Download KJV Bible text from Project Gutenberg"""
    logger.info("Downloading KJV Bible text from Project Gutenberg...")
    response = requests.get(KJV_URL)
    response.raise_for_status()
    return response.text

def parse_kjv_text(text):
    """Parse the Project Gutenberg KJV text into structured verse data"""
    logger.info("Parsing KJV Bible text...")
    
    verses = []
    current_book = None
    books_found = set()
    
    # Split text into lines
    lines = text.split('\n')
    
    # Find the start of the actual Bible content - skip table of contents
    start_parsing = False
    in_table_of_contents = True
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Skip header content until we reach the actual Bible content
        # We need to skip the table of contents and start when we see the actual Genesis title
        if not start_parsing:
            # Look for the actual Genesis title in File #30 format
            # This will be after the table of contents and followed by verses
            if (line == "Book 01 Genesis" and 
                i > 70 and in_table_of_contents):
                start_parsing = True
                in_table_of_contents = False
                current_book = "Genesis"
                books_found.add("Genesis")
                logger.info("Found start of actual Bible content with Genesis (File #30 format)")
                logger.info(f"Processing book: Genesis")
                continue
            else:
                continue
        
        # Stop parsing at the end marker
        if line.startswith("***") and "END OF" in line:
            logger.info("Found end of Project Gutenberg content")
            break
            
        # Skip empty lines and Project Gutenberg markers
        if not line or "Project Gutenberg" in line:
            continue
            
        # Check if this line is a book title (only after we've started parsing)
        if line in BOOK_MAPPING:
            current_book = BOOK_MAPPING[line]
            books_found.add(current_book)
            logger.info(f"Processing book: {current_book}")
            continue
            
        # Skip section headers
        if line in ["The Old Testament of the King James Version of the Bible", 
                   "The New Testament of the King James Bible"]:
            continue
            
        # Parse verse patterns like "01:001:001 In the beginning..." (File #30 format)
        verse_match = re.match(r'^\d+:(\d+):(\d+)\s+(.+)$', line)
        if verse_match and current_book:
            chapter = int(verse_match.group(1))
            verse = int(verse_match.group(2))
            text = verse_match.group(3).strip()
            
            verses.append({
                'book': current_book,
                'chapter': chapter, 
                'verse': verse,
                'text': text
            })
            
        # Handle continuation of verse text (lines that don't start with book:chapter:verse)
        elif current_book and verses and not re.match(r'^\d+:\d+:\d+', line) and line.strip():
            # This is a continuation of the previous verse
            verses[-1]['text'] += ' ' + line.strip()
    
    logger.info(f"Parsed {len(verses)} verses from KJV Bible")
    logger.info(f"Found {len(books_found)} unique books: {sorted(books_found)}")
    
    # Validate that we have all expected books
    expected_books = set(BOOK_MAPPING.values())
    missing_books = expected_books - books_found
    if missing_books:
        logger.warning(f"Missing books: {sorted(missing_books)}")
    
    return verses

def create_translation_entry(db: Session):
    """Create the KJV translation entry in the database"""
    logger.info("Creating KJV translation entry...")
    
    # Check if KJV translation already exists
    existing = db.query(Translation).filter(Translation.code == "KJV").first()
    if existing:
        logger.info("KJV translation already exists")
        return existing
        
    kjv_translation = Translation(
        code="KJV",
        name="King James Version",
        description="The King James Version (KJV) is an English translation of the Christian Bible for the Church of England. Published in 1611, it became one of the most influential and widely-used English translations.",
        language="English",
        source_text="Masoretic Text (OT), Textus Receptus (NT)",
        year_published=1611,
        is_original_language=False,
        is_public_domain=True
    )
    
    db.add(kjv_translation)
    db.commit()
    db.refresh(kjv_translation)
    
    logger.info("KJV translation entry created")
    return kjv_translation

def import_verses_to_db(verses, db: Session, translation: Translation):
    """Import parsed verses into the database"""
    logger.info("Importing verses to database...")
    
    # Clear existing KJV verses if any
    db.query(BiblicalText).filter(BiblicalText.translation == "KJV").delete()
    db.commit()
    
    batch_size = 1000
    for i in range(0, len(verses), batch_size):
        batch = verses[i:i + batch_size]
        db_verses = []
        
        for verse_data in batch:
            db_verse = BiblicalText(
                book=verse_data['book'],
                chapter=verse_data['chapter'],
                verse=verse_data['verse'],
                text=verse_data['text'],
                translation="KJV",
                translation_id=translation.id
            )
            db_verses.append(db_verse)
            
        db.add_all(db_verses)
        db.commit()
        
        logger.info(f"Imported verses {i+1}-{min(i+batch_size, len(verses))}")
    
    logger.info(f"Successfully imported {len(verses)} verses")

def main():
    """Main ingestion function"""
    logger.info("Starting KJV Bible ingestion...")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    
    # Get database session
    db = next(get_db())
    
    try:
        # Download and parse KJV text
        kjv_text = download_kjv_text()
        verses = parse_kjv_text(kjv_text)
        
        # Create translation entry
        translation = create_translation_entry(db)
        
        # Import verses to database
        import_verses_to_db(verses, db, translation)
        
        logger.info("KJV Bible ingestion completed successfully!")
        
        # Print some statistics
        total_verses = db.query(BiblicalText).filter(BiblicalText.translation == "KJV").count()
        unique_books = db.query(BiblicalText.book).filter(BiblicalText.translation == "KJV").distinct().count()
        
        logger.info(f"Statistics:")
        logger.info(f"  - Total verses imported: {total_verses}")
        logger.info(f"  - Number of books: {unique_books}")
        
    except Exception as e:
        logger.error(f"Error during ingestion: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()