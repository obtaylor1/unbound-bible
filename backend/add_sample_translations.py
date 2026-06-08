#!/usr/bin/env python3

"""
Add sample verses for ASV and WEB translations to demonstrate multi-translation functionality
"""

from sqlalchemy.orm import Session
from database import SessionLocal
from models import BiblicalText, Translation
from contextlib import contextmanager

@contextmanager
def get_db_session():
    """Context manager for database sessions"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def add_sample_verses():
    """Add sample verses for popular passages in ASV and WEB"""
    
    sample_verses = [
        # John 3:16 - Most famous verse
        {
            "book": "John", "chapter": 3, "verse": 16,
            "kjv": "For God so loved the world, that he gave his only begotten Son, that whosoever believeth in him should not perish, but have everlasting life.",
            "asv": "For God so loved the world, that he gave his only begotten Son, that whosoever believeth on him should not perish, but have eternal life.", 
            "web": "For God so loved the world, that he gave his one and only Son, that whoever believes in him should not perish, but have eternal life."
        },
        # Genesis 1:1 - Beginning
        {
            "book": "Genesis", "chapter": 1, "verse": 1,
            "kjv": "In the beginning God created the heaven and the earth.",
            "asv": "In the beginning God created the heavens and the earth.",
            "web": "In the beginning God created the heavens and the earth."
        },
        # Psalm 23:1 - The Lord is my shepherd
        {
            "book": "Psalms", "chapter": 23, "verse": 1,
            "kjv": "The LORD is my shepherd; I shall not want.",
            "asv": "Jehovah is my shepherd; I shall not want.",
            "web": "Yahweh is my shepherd: I shall lack nothing."
        },
        # Matthew 28:19 - Great Commission
        {
            "book": "Matthew", "chapter": 28, "verse": 19,
            "kjv": "Go ye therefore, and teach all nations, baptizing them in the name of the Father, and of the Son, and of the Holy Ghost:",
            "asv": "Go ye therefore, and make disciples of all the nations, baptizing them into the name of the Father and of the Son and of the Holy Spirit:",
            "web": "Go, and make disciples of all nations, baptizing them in the name of the Father and of the Son and of the Holy Spirit,"
        },
        # Romans 3:23 - All have sinned
        {
            "book": "Romans", "chapter": 3, "verse": 23,
            "kjv": "For all have sinned, and come short of the glory of God;",
            "asv": "for all have sinned, and fall short of the glory of God;",
            "web": "for all have sinned, and fall short of the glory of God;"
        },
        # Ephesians 2:8 - Salvation by grace
        {
            "book": "Ephesians", "chapter": 2, "verse": 8,
            "kjv": "For by grace are ye saved through faith; and that not of yourselves: it is the gift of God:",
            "asv": "for by grace have ye been saved through faith; and that not of yourselves, it is the gift of God;",
            "web": "for by grace you have been saved through faith, and that not of yourselves; it is the gift of God,"
        }
    ]
    
    with get_db_session() as db:
        # Get translation references
        asv_translation = db.query(Translation).filter(Translation.code == "ASV").first()
        web_translation = db.query(Translation).filter(Translation.code == "WEB").first()
        kjv_translation = db.query(Translation).filter(Translation.code == "KJV").first()
        
        if not asv_translation or not web_translation:
            print("❌ Translation metadata not found. Run ingest_public_translations.py first.")
            return
            
        verses_added = 0
        
        for verse_data in sample_verses:
            book = verse_data["book"]
            chapter = verse_data["chapter"] 
            verse = verse_data["verse"]
            
            # Add ASV version
            existing_asv = db.query(BiblicalText).filter(
                BiblicalText.book == book,
                BiblicalText.chapter == chapter,
                BiblicalText.verse == verse,
                BiblicalText.translation == "ASV"
            ).first()
            
            if not existing_asv:
                asv_text = BiblicalText(
                    book=book,
                    chapter=chapter,
                    verse=verse,
                    text=verse_data["asv"],
                    translation="ASV",
                    translation_id=asv_translation.id
                )
                db.add(asv_text)
                verses_added += 1
                print(f"✅ Added {book} {chapter}:{verse} (ASV)")
            
            # Add WEB version
            existing_web = db.query(BiblicalText).filter(
                BiblicalText.book == book,
                BiblicalText.chapter == chapter,
                BiblicalText.verse == verse,
                BiblicalText.translation == "WEB"
            ).first()
            
            if not existing_web:
                web_text = BiblicalText(
                    book=book,
                    chapter=chapter,
                    verse=verse,
                    text=verse_data["web"],
                    translation="WEB",
                    translation_id=web_translation.id
                )
                db.add(web_text)
                verses_added += 1
                print(f"✅ Added {book} {chapter}:{verse} (WEB)")
        
        db.commit()
        print(f"\n🎉 Successfully added {verses_added} sample translation verses!")
        
        # Show summary
        kjv_count = db.query(BiblicalText).filter(BiblicalText.translation == "KJV").count()
        asv_count = db.query(BiblicalText).filter(BiblicalText.translation == "ASV").count()
        web_count = db.query(BiblicalText).filter(BiblicalText.translation == "WEB").count()
        
        print(f"📊 Database summary:")
        print(f"   KJV verses: {kjv_count:,}")
        print(f"   ASV verses: {asv_count:,}")
        print(f"   WEB verses: {web_count:,}")
        print(f"   Total verses: {kjv_count + asv_count + web_count:,}")

if __name__ == "__main__":
    print("🌍 Adding Sample Translation Data")
    print("=" * 50)
    add_sample_verses()