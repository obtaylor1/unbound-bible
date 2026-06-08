#!/usr/bin/env python3
"""
Data ingestion script for the Understanding the Bible report.

Populates core tables with:
- Geographical locations (ancient places → modern locations)
- Original Hebrew/Aramaic names (lexicon entries)
- Historical notes about canon formation and Constantine myth
- Ethiopian canonical books
- Translation bias markers for controversial verses
"""

import sys
import os
from typing import Dict, List, Tuple
from datetime import datetime

# Add backend directory to path for imports
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
sys.path.insert(0, backend_path)

from sqlalchemy.orm import Session

try:
    from database import get_db
    from models import (
        GeographicalLocation, LexiconEntry, HistoricalNote, BiblicalText, 
        Translation, LanguageEnum, BookEnum
    )
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Backend path: {backend_path}")
    print("Make sure you're running this script from the correct directory")
    sys.exit(1)


class ReportDataIngester:
    """Handles ingestion of data from the Understanding the Bible report"""
    
    def __init__(self):
        self.session = None
        
    def ingest_geographical_locations(self):
        """Extract and ingest geographical locations from the report"""
        
        print("Ingesting geographical locations...")
        
        # Geographical data from the report (Ancient place → Modern location)
        geographical_data = [
            ("Assyria", "Northern Iraq, northeastern Syria, southeastern Turkey", 
             "Once a powerful empire that conquered Israel's northern kingdom"),
            ("Babylon", "Hillah, Iraq", 
             "Capital of Nebuchadnezzar's empire; ruins near Hillah"),
            ("Canaan", "Israel, Palestine, Lebanon, western Jordan", 
             "Land promised to Abraham"),
            ("Philistia", "Gaza Strip, southwestern Israel", 
             "Coastal home of the Philistines"),
            ("Edom", "Southern Jordan, southern Israel", 
             "Territory of Esau's descendants"),
            ("Moab", "Central-western Jordan", 
             "East of the Dead Sea"),
            ("Ammon", "Amman, Jordan", 
             "Descendants of Lot; evolved into Philadelphia"),
            ("Paddan Aram", "Southeastern Turkey, northern Syria", 
             "Patriarchal homeland"),
            ("Shinar", "Southern Iraq", 
             "Early Mesopotamian plain (Tower of Babel)"),
            ("Galilee", "Northern Israel", 
             "Region where Jesus ministered"),
            ("Samaria", "Sebastia, West Bank, Palestine", 
             "Capital of the northern kingdom"),
            ("Gilead", "Northwestern Jordan", 
             "East-Jordan hill country"),
            ("Nineveh", "Mosul, Iraq", 
             "Assyrian capital visited by Jonah"),
            ("Damascus", "Damascus, Syria", 
             "Ancient city that retains its name; one of world's oldest inhabited cities"),
            ("Jericho", "Ariha/Jericho, West Bank", 
             "Site of Joshua's conquest"),
            ("Hebron", "Hebron (Al-Khalil), West Bank, Palestine", 
             "Abraham's burial site"),
            ("Bethel", "Beitin, West Bank", 
             "Where Jacob dreamed of a ladder"),
            ("Goshen", "Eastern Nile Delta, Egypt", 
             "Fertile region where Jacob's family settled"),
            ("Haran", "Harran, southeastern Turkey", 
             "Abraham's way-station"),
            ("Joppa", "Tel Aviv-Yafo, Israel", 
             "Port from which Jonah fled; incorporated into Tel Aviv"),
            ("Ephesus", "Selçuk, Turkey", 
             "Site of Paul's ministry")
        ]
        
        count = 0
        for ancient_name, modern_location, description in geographical_data:
            # Check if already exists
            existing = self.session.query(GeographicalLocation).filter(
                GeographicalLocation.name == ancient_name
            ).first()
            
            if not existing:
                geo_location = GeographicalLocation(
                    biblical_text_id=None,  # Will be linked later
                    name=ancient_name,
                    modern_name=modern_location,
                    description=description,
                    confidence_score=0.9,  # High confidence from scholarly source
                    identification_source="Understanding the Bible report 2025"
                )
                self.session.add(geo_location)
                count += 1
        
        self.session.commit()
        print(f"✓ Inserted {count} geographical locations")
        
    def ingest_original_names_lexicon(self):
        """Extract and ingest original Hebrew/Aramaic names into lexicon"""
        
        print("Ingesting original Hebrew/Aramaic names...")
        
        # Original names data from the report
        name_data = [
            ("Jesus", "Yeshua", "ישוע", "hebrew", "to rescue or deliver", 
             "Shortened form of Yehoshua"),
            ("Mary", "Miriam", "מרים", "hebrew", "beloved, wished for child", 
             "Same as Moses' sister; pronounced Maryam in Aramaic"),
            ("Joseph", "Yosef", "יוסף", "hebrew", "he will add", 
             "Common Hebrew name"),
            ("Peter", "Shimon", "שמעון בן יונה", "hebrew", "he has heard", 
             "Originally Shimon bar Yonah; Jesus gave him Aramaic nickname Kepha (rock)"),
            ("John", "Yohanan", "יוחנן", "hebrew", "YHWH is gracious", 
             "Common Hebrew name meaning God is gracious"),
            ("James", "Ya'akov", "יעקב", "hebrew", "supplanter", 
             "Same name as Jacob; English James arose from later linguistic evolution"),
            ("Matthew", "Levi", "לוי", "hebrew", "joined, attached", 
             "Tax collector called Levi before following Jesus")
        ]
        
        count = 0
        for english_name, hebrew_name, hebrew_text, language, meaning, notes in name_data:
            # Check if already exists
            existing = self.session.query(LexiconEntry).filter(
                LexiconEntry.original_word == hebrew_text
            ).first()
            
            if not existing:
                lang_enum = LanguageEnum.hebrew if language == "hebrew" else LanguageEnum.aramaic
                
                lexicon_entry = LexiconEntry(
                    strong_number=f"N_{english_name[:4].upper()}",  # Shortened identifier (10 char limit)
                    language=lang_enum,
                    original_word=hebrew_text,
                    transliteration=hebrew_name,
                    definition=f"{english_name} - {meaning}",
                    detailed_definition=f"Original name: {hebrew_name} ({hebrew_text}). Meaning: {meaning}. Notes: {notes}",
                    usage_notes=f"NAME_ROOT - Original Hebrew/Aramaic name for biblical figure {english_name}"
                )
                self.session.add(lexicon_entry)
                count += 1
        
        self.session.commit()
        print(f"✓ Inserted {count} original name lexicon entries (flagged as NAME_ROOT)")
        
    def ingest_historical_canon_notes(self):
        """Extract and ingest historical notes about canon formation and Constantine myth"""
        
        print("Ingesting historical notes about canon formation...")
        
        # Historical notes from the report
        historical_notes_data = [
            (
                "Constantine Myth Debunked",
                "Contrary to popular myth, Emperor Constantine and the Council of Nicaea (AD 325) did not determine which books belonged in the Bible. After Nicaea, Constantine did order Eusebius of Caesarea to produce 50 copies of the Scriptures for Constantinople, but no evidence shows that the council itself decided the canon. The biblical canon was established through a gradual process over several centuries, not by imperial decree.",
                "CANON_HISTORY",
                "4th century AD",
                "Understanding the Bible report 2025"
            ),
            (
                "Protestant Canon Development", 
                "The Protestant Old Testament (39 books) matches the Hebrew Tanakh. The extra books found in Catholic and Orthodox Bibles (deuterocanonical/apocryphal books) were removed during the Reformation because Reformers believed only the Hebrew-Bible books were canonical. The 66-book canon omits works such as Tobit, Judith, 1-2 Maccabees, Wisdom of Solomon, Sirach, Baruch, and others.",
                "CANON_HISTORY",
                "16th century AD (Reformation)",
                "Understanding the Bible report 2025"
            ),
            (
                "Ethiopian Orthodox Canon",
                "The Ethiopian Orthodox Tewahedo Church preserves the largest biblical canon—46 Old Testament and 35 New Testament books (81 total). Its canon includes books like Jubilees, 1 Enoch (quoted in Jude 14-15), Tobit, Judith, Sirach, Wisdom of Solomon, and books unique to Ethiopia such as Meqabyan 1-3. These 'Ethiopian Maccabees' are entirely different from Greek Maccabees and recount revolts against pagan kings.",
                "CANON_HISTORY", 
                "Ancient to medieval period",
                "Understanding the Bible report 2025"
            ),
            (
                "Canon Diversity Reality",
                "Christian traditions disagree on the status of many books. Catholics and Orthodox accept deuterocanonical books as inspired; Protestants treat them as Apocrypha. The Ethiopian Church includes those books plus unique works like Enoch, Jubilees, and Meqabyan. This diversity reminds us that the 66-book Protestant canon is not the only historical collection of scripture.",
                "CANON_HISTORY",
                "Historical overview",
                "Understanding the Bible report 2025"
            ),
            (
                "Translation Bias - Exodus 12:38",
                "The KJV translates Exodus 12:38 as 'a mixed multitude went up also with them.' Scholar Esau McCaulley argues that the Hebrew phrase highlights an 'ethnically diverse crowd,' likely including Egyptians and Cushites (Africans). The KJV's generic phrase does not communicate the verse's emphasis on ethnic diversity.",
                "TRANSLATION_BIAS",
                "Biblical period",
                "Understanding the Bible report 2025"
            ),
            (
                "Translation Bias - Song of Solomon 1:5",
                "The Hebrew reads 'שְׁחוֹרָה אֲנִי וְנָאוָה' ('I am black and beautiful'). The KJV translates it as 'I am black but comely,' inserting a contrast not present in the Hebrew. Scholar Wilda Gafney points out that the Hebrew conjunction means 'and,' not 'but,' suggesting translators' cultural context influenced their inability to regard blackness as beautiful.",
                "TRANSLATION_BIAS",
                "Biblical period",
                "Understanding the Bible report 2025"
            )
        ]
        
        count = 0
        for title, content, category, period, source in historical_notes_data:
            # Check if already exists
            existing = self.session.query(HistoricalNote).filter(
                HistoricalNote.title == title
            ).first()
            
            if not existing:
                historical_note = HistoricalNote(
                    biblical_text_id=None,  # General historical notes not tied to specific verses
                    title=f"[{category}] {title}",  # Include category in title
                    content=content,
                    historical_period=period,
                    source=source
                )
                self.session.add(historical_note)
                count += 1
        
        self.session.commit()
        print(f"✓ Inserted {count} historical notes (CANON_HISTORY and TRANSLATION_BIAS)")
        
    def ingest_ethiopian_canonical_books(self):
        """Insert Ethiopian canonical books into biblical_texts table"""
        
        print("Ingesting Ethiopian canonical books...")
        
        # Ethiopian books from the report
        ethiopian_books = [
            # Old Testament additions
            ("Jubilees", "Second-century BC retelling of Genesis and Exodus; known only complete in Ethiopian manuscripts"),
            ("1 Enoch", "Collection of apocalyptic visions, quoted in Jude 14-15; preserved fully in Geʽez manuscripts"),
            ("Tobit", "Deuterocanonical book preserved in Ethiopian canon"),
            ("Judith", "Deuterocanonical book preserved in Ethiopian canon"),
            ("2 Maccabees", "Second book of Maccabees in Ethiopian canon"),
            ("3 Maccabees", "Third book of Maccabees in Ethiopian canon"),
            ("Book of Josephus", "Josippon - historical work in Ethiopian canon"),
            ("Sirach", "Jesus ben Sirach - wisdom literature in Ethiopian canon"),
            ("Wisdom of Solomon", "Deuterocanonical wisdom book in Ethiopian canon"),
            ("Meqabyan 1", "Ethiopian Maccabees Book 1 - unique to Ethiopia"),
            ("Meqabyan 2", "Ethiopian Maccabees Book 2 - unique to Ethiopia"),
            ("Meqabyan 3", "Ethiopian Maccabees Book 3 - unique to Ethiopia"),
            ("Book of Abraham", "Sutuel - survives only in Ethiopic"),
            ("Ascension of Isaiah", "Pseudepigraphical work preserved in Ethiopian tradition"),
            
            # New Testament additions (Sinodos collection)
            ("Sirate Tsion", "Order of Zion - Part of Sinodos; instructions for church order"),
            ("Tizaz", "Book of Herald/Commandments - Part of Sinodos; church regulations"),
            ("Gitsew", "Third part of Sinodos; details liturgical practices"),
            ("Abtilis", "Fourth part of Sinodos; prescribes ecclesiastical order"),
            ("1st Book of Dominos", "Book of the Covenant - deals with church order"),
            ("2nd Book of Dominos", "Book of the Covenant - includes discourse of Jesus after resurrection"),
            ("Book of Qäləmentos", "Letter from Peter to Clement, distinct from 1-2 Clement"),
            ("Didascalia", "Ethiopian version of Didascalia Apostolorum - church manual")
        ]
        
        # Get or create Ethiopian translation record
        ethiopian_translation = self.session.query(Translation).filter(
            Translation.code == "ETHIOPIAN"
        ).first()
        
        if not ethiopian_translation:
            ethiopian_translation = Translation(
                code="ETHIOPIAN",
                name="Ethiopian Orthodox Tewahedo Canon",
                description="81-book canon of Ethiopian Orthodox Church (46 OT + 35 NT)",
                language="Geez",
                source_text="Ethiopian Orthodox Tradition",
                is_original_language=False,
                is_public_domain=True
            )
            self.session.add(ethiopian_translation)
            self.session.commit()
        
        count = 0
        for book_name, description in ethiopian_books:
            # Check if already exists
            existing = self.session.query(BiblicalText).filter(
                BiblicalText.book == book_name,
                BiblicalText.translation == "ETHIOPIAN"
            ).first()
            
            if not existing:
                # Create placeholder entry for Ethiopian book
                biblical_text = BiblicalText(
                    book=book_name,
                    chapter=1,
                    verse=1,
                    text=f"[{book_name} - {description}] This book is part of the Ethiopian Orthodox canon but not available in Protestant tradition.",
                    translation="ETHIOPIAN",
                    translation_id=ethiopian_translation.id,
                    textual_notes={"canon_status": "ETHIOPIAN_UNIQUE", "description": description}
                )
                self.session.add(biblical_text)
                count += 1
        
        self.session.commit()
        print(f"✓ Inserted {count} Ethiopian canonical books (flagged as ETHIOPIAN_UNIQUE)")
        
    def create_controversial_verse_markers(self):
        """Mark controversial verses for translation bias highlighting"""
        
        print("Creating controversial verse markers...")
        
        controversial_verses = [
            ("Exodus", 12, 38, "TRANSLATION_BIAS", 
             "KJV 'mixed multitude' vs Hebrew emphasis on 'ethnically diverse crowd'"),
            ("Song of Solomon", 1, 5, "TRANSLATION_BIAS",
             "KJV 'black but comely' vs Hebrew 'black and beautiful' - conjunction issue")
        ]
        
        count = 0
        for book, chapter, verse, bias_type, note in controversial_verses:
            # Find the verse in database
            biblical_text = self.session.query(BiblicalText).filter(
                BiblicalText.book == book,
                BiblicalText.chapter == chapter, 
                BiblicalText.verse == verse
            ).first()
            
            if biblical_text:
                # Update textual notes to mark translation bias
                if not biblical_text.textual_notes:
                    biblical_text.textual_notes = {}
                
                biblical_text.textual_notes.update({
                    "translation_bias": bias_type,
                    "bias_note": note,
                    "alert_type": "TRANSLATOR_BIAS_DETECTED"
                })
                count += 1
        
        self.session.commit()
        print(f"✓ Marked {count} controversial verses for translation bias highlighting")
        
    def run_ingestion(self):
        """Run the complete ingestion process"""
        
        print("=== Understanding the Bible Report Data Ingestion ===")
        print("Populating geographical locations, lexicon, historical notes, and Ethiopian books")
        print()
        
        try:
            # Initialize database session
            self.session = next(get_db())
            
            # Step 1: Ingest geographical locations  
            self.ingest_geographical_locations()
            print()
            
            # Step 2: Ingest original Hebrew/Aramaic names
            self.ingest_original_names_lexicon()
            print()
            
            # Step 3: Ingest historical notes about canon formation
            self.ingest_historical_canon_notes()
            print()
            
            # Step 4: Ingest Ethiopian canonical books
            self.ingest_ethiopian_canonical_books()
            print()
            
            # Step 5: Mark controversial verses for translation bias
            self.create_controversial_verse_markers()
            print()
            
            # Verification
            geo_count = self.session.query(GeographicalLocation).count()
            lexicon_count = self.session.query(LexiconEntry).filter(
                LexiconEntry.usage_notes.like("%NAME_ROOT%")
            ).count()
            historical_count = self.session.query(HistoricalNote).filter(
                HistoricalNote.title.like("%[CANON_HISTORY]%") | 
                HistoricalNote.title.like("%[TRANSLATION_BIAS]%")
            ).count()
            ethiopian_count = self.session.query(BiblicalText).filter(
                BiblicalText.translation == "ETHIOPIAN"
            ).count()
            
            print("✅ Data ingestion completed successfully!")
            print()
            print("Verification:")
            print(f"- Geographical locations: {geo_count} entries")
            print(f"- Original names (NAME_ROOT): {lexicon_count} entries")  
            print(f"- Historical/bias notes: {historical_count} entries")
            print(f"- Ethiopian canonical books: {ethiopian_count} entries")
            print()
            
            if geo_count >= 15:
                print("✓ Geographical locations target met (≥15 pairings)")
            else:
                print(f"⚠ Geographical locations below target: {geo_count} < 15")
                
            if historical_count >= 4:
                print("✓ Historical anti-myth and bias notes successfully ingested")
            else:
                print(f"⚠ Historical notes below expected: {historical_count}")
                
            print()
            print("Next steps:")
            print("1. Implement translation bias highlighting in TextualComparison.jsx")
            print("2. Implement canonical toggle logic for Ethiopian vs Protestant books")
            print("3. Enhance myth-buster chat with CANON_HISTORY grounding")
            
        except Exception as e:
            print(f"❌ Error during ingestion: {e}")
            if self.session:
                self.session.rollback()
            raise
            
        finally:
            if self.session:
                self.session.close()


def main():
    """Main entry point for the ingestion script"""
    
    print("Running Understanding the Bible report data ingestion...")
    
    # Initialize and run ingester
    ingester = ReportDataIngester()
    ingester.run_ingestion()


if __name__ == "__main__":
    main()