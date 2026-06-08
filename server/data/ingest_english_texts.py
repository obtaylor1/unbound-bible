#!/usr/bin/env python3
"""
Ingestion script for English biblical texts with Deuterocanonical support:
- KJV (+ Apocrypha): English Protestant baseline with deuterocanonical books
- WEB Ecumenical/WEBBE: World English Bible with full deuterocanonical support

Handles USFM/OSIS format parsing and creates proper EditionMetadata records.
"""

import sys
import os
import json
import re
from typing import Dict, List, Tuple, Optional, Union
from datetime import datetime

# Add backend and server paths for imports
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
server_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, backend_path)
sys.path.insert(0, server_path)

from sqlalchemy.orm import Session

# Direct imports from backend directory
sys.path.insert(0, backend_path)
sys.path.insert(0, os.path.join(server_path, 'models'))

try:
    # Import from backend
    from database import get_db, engine
    from models import BiblicalText, Translation, OriginalWord, LexiconEntry
    # Import from server models
    from edition_metadata import EditionMetadata, IngestStatusEnum
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Backend path: {backend_path}")
    print(f"Server path: {server_path}")
    print("Make sure you're running this script from the correct directory")
    sys.exit(1)


class EnglishTextsIngester:
    """Handles ingestion of English biblical texts with deuterocanonical support"""
    
    def __init__(self):
        self.session: Optional[Session] = None
        
        # Protestant canonical books (66 books)
        self.protestant_books = [
            # Old Testament (39 books)
            "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
            "Joshua", "Judges", "Ruth", "1 Samuel", "2 Samuel", "1 Kings", "2 Kings",
            "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah", "Esther",
            "Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon",
            "Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel",
            "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah", "Nahum",
            "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi",
            # New Testament (27 books)
            "Matthew", "Mark", "Luke", "John", "Acts", "Romans",
            "1 Corinthians", "2 Corinthians", "Galatians", "Ephesians",
            "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians",
            "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews",
            "James", "1 Peter", "2 Peter", "1 John", "2 John", "3 John",
            "Jude", "Revelation"
        ]
        
        # Deuterocanonical/Apocryphal books
        self.deuterocanonical_books = [
            "Tobit", "Judith", "Esther (Greek)", "Wisdom of Solomon", "Sirach",
            "Baruch", "Letter of Jeremiah", "Daniel (Greek)", "1 Maccabees", "2 Maccabees",
            "1 Esdras", "2 Esdras", "Prayer of Manasseh", "Psalm 151",
            "3 Maccabees", "4 Maccabees", "Odes"
        ]
        
        # USFM book code mappings for parsing
        self.usfm_book_codes = {
            "GEN": "Genesis", "EXO": "Exodus", "LEV": "Leviticus", "NUM": "Numbers",
            "DEU": "Deuteronomy", "JOS": "Joshua", "JDG": "Judges", "RUT": "Ruth",
            "1SA": "1 Samuel", "2SA": "2 Samuel", "1KI": "1 Kings", "2KI": "2 Kings",
            "1CH": "1 Chronicles", "2CH": "2 Chronicles", "EZR": "Ezra", "NEH": "Nehemiah",
            "EST": "Esther", "JOB": "Job", "PSA": "Psalms", "PRO": "Proverbs",
            "ECC": "Ecclesiastes", "SNG": "Song of Solomon", "ISA": "Isaiah",
            "JER": "Jeremiah", "LAM": "Lamentations", "EZK": "Ezekiel", "DAN": "Daniel",
            "HOS": "Hosea", "JOL": "Joel", "AMO": "Amos", "OBA": "Obadiah",
            "JON": "Jonah", "MIC": "Micah", "NAM": "Nahum", "HAB": "Habakkuk",
            "ZEP": "Zephaniah", "HAG": "Haggai", "ZEC": "Zechariah", "MAL": "Malachi",
            # New Testament
            "MAT": "Matthew", "MRK": "Mark", "LUK": "Luke", "JHN": "John",
            "ACT": "Acts", "ROM": "Romans", "1CO": "1 Corinthians", "2CO": "2 Corinthians",
            "GAL": "Galatians", "EPH": "Ephesians", "PHP": "Philippians", "COL": "Colossians",
            "1TH": "1 Thessalonians", "2TH": "2 Thessalonians", "1TI": "1 Timothy",
            "2TI": "2 Timothy", "TIT": "Titus", "PHM": "Philemon", "HEB": "Hebrews",
            "JAS": "James", "1PE": "1 Peter", "2PE": "2 Peter", "1JN": "1 John",
            "2JN": "2 John", "3JN": "3 John", "JUD": "Jude", "REV": "Revelation",
            # Deuterocanonical books
            "TOB": "Tobit", "JDT": "Judith", "ESG": "Esther (Greek)", 
            "WIS": "Wisdom of Solomon", "SIR": "Sirach", "BAR": "Baruch",
            "LJE": "Letter of Jeremiah", "DAG": "Daniel (Greek)", 
            "1MA": "1 Maccabees", "2MA": "2 Maccabees", "1ES": "1 Esdras",
            "2ES": "2 Esdras", "MAN": "Prayer of Manasseh", "PS2": "Psalm 151"
        }

    def create_edition_metadata(self):
        """Create EditionMetadata records for KJV and WEB English texts"""
        
        print("Creating edition metadata records for English texts...")
        
        # KJV (+ Apocrypha) Edition
        kjv_edition = EditionMetadata(
            work_id="KJV_COMPLETE",
            language_script="en/English",
            canon_tags=["protestant", "deuterocanon"],
            source_title="King James Version with Apocrypha",
            editor_translator="King James Bible Committee",
            publisher="Oxford University Press (Historical)",
            license="PD",
            provenance_url="https://www.gutenberg.org/ebooks/10",
            has_morph=False,
            ingest_status=IngestStatusEnum.queued
        )
        
        # Check if KJV already exists
        existing_kjv = self.session.query(EditionMetadata).filter(
            EditionMetadata.work_id == "KJV_COMPLETE"
        ).first()
        
        if not existing_kjv:
            self.session.add(kjv_edition)
            print("✓ Created KJV (+ Apocrypha) edition metadata")
            print("  - Language: English (en)")
            print("  - Canon tags: protestant, deuterocanon")
            print("  - License: Public Domain")
            print("  - Includes: 66 Protestant + Apocryphal books")
        else:
            print("✓ KJV edition metadata already exists")
        
        # WEB Ecumenical/WEBBE Edition
        web_edition = EditionMetadata(
            work_id="WEBBE_COMPLETE",
            language_script="en/English",
            canon_tags=["protestant", "catholic", "orthodox", "deuterocanon"],
            source_title="World English Bible Ecumenical Edition",
            editor_translator="Rainbow Missions, Inc.",
            publisher="World English Bible Project",
            license="PD",
            provenance_url="https://worldenglish.bible/",
            has_morph=False,
            ingest_status=IngestStatusEnum.queued
        )
        
        # Check if WEB already exists
        existing_web = self.session.query(EditionMetadata).filter(
            EditionMetadata.work_id == "WEBBE_COMPLETE"
        ).first()
        
        if not existing_web:
            self.session.add(web_edition)
            print("✓ Created WEB Ecumenical edition metadata")
            print("  - Language: English (en)")
            print("  - Canon tags: protestant, catholic, orthodox, deuterocanon")
            print("  - License: Public Domain")
            print("  - Includes: 66 Protestant + Full deuterocanonical corpus")
        else:
            print("✓ WEB Ecumenical edition metadata already exists")
        
        self.session.commit()
        print("✓ English edition metadata records created successfully")

    def parse_usfm_text(self, usfm_file_path: str, translation_code: str) -> List[Dict]:
        """
        Placeholder function to parse USFM format biblical texts
        
        Expected USFM structure:
        \\id GEN - Genesis
        \\h Genesis
        \\toc1 The First Book of Moses, called Genesis
        \\c 1
        \\p
        \\v 1 In the beginning God created the heaven and the earth.
        \\v 2 And the earth was without form, and void...
        """
        
        print(f"Parsing USFM file: {usfm_file_path} for {translation_code}")
        
        # Placeholder parsed data representing USFM content
        # In real implementation, this would parse actual USFM files
        parsed_data = []
        
        # Sample canonical books
        canonical_sample = [
            {
                "book": "Genesis",
                "chapter": 1,
                "verse": 1,
                "text": "In the beginning God created the heaven and the earth.",
                "is_deuterocanonical": False
            },
            {
                "book": "Genesis", 
                "chapter": 1,
                "verse": 2,
                "text": "And the earth was without form, and void; and darkness was upon the face of the deep. And the Spirit of God moved upon the face of the waters.",
                "is_deuterocanonical": False
            }
        ]
        
        # Sample deuterocanonical books
        if translation_code in ["KJV", "WEBBE"]:
            deuterocanonical_sample = [
                {
                    "book": "Tobit",
                    "chapter": 1,
                    "verse": 1,
                    "text": "The book of the words of Tobit, son of Tobiel, the son of Ananiel, the son of Aduel, the son of Gabael, descended from the seed of Asael, of the tribe of Naphtali.",
                    "is_deuterocanonical": True
                },
                {
                    "book": "Wisdom of Solomon",
                    "chapter": 1,
                    "verse": 1,
                    "text": "Love righteousness, you rulers of the earth, think of the Lord with a good heart, and in simplicity of heart seek him.",
                    "is_deuterocanonical": True
                },
                {
                    "book": "Sirach",
                    "chapter": 1,
                    "verse": 1,
                    "text": "All wisdom is from the Lord, and is with him forever.",
                    "is_deuterocanonical": True
                },
                {
                    "book": "1 Maccabees",
                    "chapter": 1,
                    "verse": 1,
                    "text": "And it happened, after that Alexander son of Philip, the Macedonian, who came out of the land of Chittim, had smitten Darius king of the Persians and Medes, that he reigned in his stead, the first over Greece.",
                    "is_deuterocanonical": True
                }
            ]
            parsed_data.extend(deuterocanonical_sample)
        
        parsed_data.extend(canonical_sample)
        
        # TODO: Implement actual USFM parsing logic
        # def parse_usfm_file(file_path):
        #     with open(file_path, 'r', encoding='utf-8') as f:
        #         content = f.read()
        #         # Parse USFM markers: \id, \h, \c, \v, \p, etc.
        #         verses = []
        #         current_book = None
        #         current_chapter = 1
        #         
        #         for line in content.split('\n'):
        #             if line.startswith('\\id '):
        #                 book_code = line.split()[1]
        #                 current_book = self.usfm_book_codes.get(book_code)
        #             elif line.startswith('\\c '):
        #                 current_chapter = int(line.split()[1])
        #             elif line.startswith('\\v '):
        #                 verse_match = re.match(r'\\v (\d+) (.+)', line)
        #                 if verse_match:
        #                     verse_num = int(verse_match.group(1))
        #                     verse_text = verse_match.group(2)
        #                     verses.append({
        #                         'book': current_book,
        #                         'chapter': current_chapter,
        #                         'verse': verse_num,
        #                         'text': verse_text,
        #                         'is_deuterocanonical': current_book in self.deuterocanonical_books
        #                     })
        #         return verses
        
        print(f"✓ Parsed {len(parsed_data)} verses from {translation_code} USFM (placeholder data)")
        return parsed_data

    def parse_osis_text(self, osis_file_path: str, translation_code: str) -> List[Dict]:
        """
        Placeholder function to parse OSIS format biblical texts
        
        Expected OSIS structure:
        <osis>
          <osisText>
            <div type="book" osisID="Gen">
              <title type="main">Genesis</title>
              <chapter osisID="Gen.1">
                <verse osisID="Gen.1.1">In the beginning God created the heaven and the earth.</verse>
                <verse osisID="Gen.1.2">And the earth was without form, and void...</verse>
              </chapter>
            </div>
          </osisText>
        </osis>
        """
        
        print(f"Parsing OSIS file: {osis_file_path} for {translation_code}")
        
        # Placeholder implementation - in real scenario would use XML parsing
        # import xml.etree.ElementTree as ET
        # tree = ET.parse(osis_file_path)
        # root = tree.getroot()
        
        parsed_data = [
            {
                "book": "Matthew",
                "chapter": 1,
                "verse": 1,
                "text": "The book of the genealogy of Jesus Christ, the son of David, the son of Abraham.",
                "is_deuterocanonical": False
            },
            {
                "book": "Judith",
                "chapter": 1, 
                "verse": 1,
                "text": "In the twelfth year of the reign of Nebuchadnezzar, who reigned in Nineveh, the great city; in the days of Arphaxad, which reigned over the Medes in Ecbatane.",
                "is_deuterocanonical": True
            }
        ]
        
        print(f"✓ Parsed {len(parsed_data)} verses from {translation_code} OSIS (placeholder data)")
        return parsed_data

    def insert_biblical_texts(self, parsed_data: List[Dict], translation_code: str):
        """Insert parsed English texts with proper deuterocanonical tagging"""
        
        print(f"Inserting biblical texts for {translation_code}...")
        
        # Get or create translation record
        translation = self.session.query(Translation).filter(
            Translation.code == translation_code
        ).first()
        
        if not translation:
            # Create translation record
            translation_name = "King James Version" if translation_code == "KJV" else "World English Bible Ecumenical"
            translation = Translation(
                code=translation_code,
                name=translation_name,
                description=f"{translation_name} with deuterocanonical books",
                language="English",
                source_text="English Translation",
                is_original_language=False,
                is_public_domain=True
            )
            self.session.add(translation)
            self.session.commit()
        
        verse_count = 0
        deutero_count = 0
        
        for verse_data in parsed_data:
            # Check if already exists
            existing = self.session.query(BiblicalText).filter(
                BiblicalText.book == verse_data["book"],
                BiblicalText.chapter == verse_data["chapter"],
                BiblicalText.verse == verse_data["verse"],
                BiblicalText.translation == translation_code
            ).first()
            
            if not existing:
                # Prepare textual notes with deuterocanonical status
                textual_notes = {}
                if verse_data.get("is_deuterocanonical", False):
                    textual_notes = {
                        "canonical_status": "deuterocanon",
                        "protestant_canon": False,
                        "catholic_canon": True,
                        "orthodox_canon": True
                    }
                    deutero_count += 1
                else:
                    textual_notes = {
                        "canonical_status": "protestant",
                        "protestant_canon": True,
                        "catholic_canon": True,
                        "orthodox_canon": True
                    }
                
                # Create BiblicalText record
                biblical_text = BiblicalText(
                    book=verse_data["book"],
                    chapter=verse_data["chapter"],
                    verse=verse_data["verse"],
                    text=verse_data["text"],
                    translation=translation_code,
                    translation_id=translation.id,
                    textual_notes=textual_notes,
                    canonical_order=self._get_canonical_order(
                        verse_data["book"], 
                        verse_data["chapter"], 
                        verse_data["verse"],
                        verse_data.get("is_deuterocanonical", False)
                    )
                )
                
                self.session.add(biblical_text)
                verse_count += 1
        
        self.session.commit()
        print(f"✓ Inserted {verse_count} verses for {translation_code}")
        print(f"  - Canonical verses: {verse_count - deutero_count}")
        print(f"  - Deuterocanonical verses: {deutero_count}")

    def _get_canonical_order(self, book: str, chapter: int, verse: int, is_deuterocanonical: bool) -> int:
        """Calculate canonical ordering with deuterocanonical positioning"""
        
        # Protestant canonical order (1-66)
        protestant_order = {
            # Old Testament
            "Genesis": 1, "Exodus": 2, "Leviticus": 3, "Numbers": 4, "Deuteronomy": 5,
            "Joshua": 6, "Judges": 7, "Ruth": 8, "1 Samuel": 9, "2 Samuel": 10,
            "1 Kings": 11, "2 Kings": 12, "1 Chronicles": 13, "2 Chronicles": 14,
            "Ezra": 15, "Nehemiah": 16, "Esther": 17, "Job": 18, "Psalms": 19,
            "Proverbs": 20, "Ecclesiastes": 21, "Song of Solomon": 22, "Isaiah": 23,
            "Jeremiah": 24, "Lamentations": 25, "Ezekiel": 26, "Daniel": 27,
            "Hosea": 28, "Joel": 29, "Amos": 30, "Obadiah": 31, "Jonah": 32,
            "Micah": 33, "Nahum": 34, "Habakkuk": 35, "Zephaniah": 36, "Haggai": 37,
            "Zechariah": 38, "Malachi": 39,
            # New Testament
            "Matthew": 40, "Mark": 41, "Luke": 42, "John": 43, "Acts": 44,
            "Romans": 45, "1 Corinthians": 46, "2 Corinthians": 47, "Galatians": 48,
            "Ephesians": 49, "Philippians": 50, "Colossians": 51, "1 Thessalonians": 52,
            "2 Thessalonians": 53, "1 Timothy": 54, "2 Timothy": 55, "Titus": 56,
            "Philemon": 57, "Hebrews": 58, "James": 59, "1 Peter": 60, "2 Peter": 61,
            "1 John": 62, "2 John": 63, "3 John": 64, "Jude": 65, "Revelation": 66
        }
        
        # Deuterocanonical order (67+)
        deutero_order = {
            "Tobit": 67, "Judith": 68, "Esther (Greek)": 69, "Wisdom of Solomon": 70,
            "Sirach": 71, "Baruch": 72, "Letter of Jeremiah": 73, "Daniel (Greek)": 74,
            "1 Maccabees": 75, "2 Maccabees": 76, "1 Esdras": 77, "2 Esdras": 78,
            "Prayer of Manasseh": 79, "Psalm 151": 80, "3 Maccabees": 81, "4 Maccabees": 82
        }
        
        if is_deuterocanonical:
            book_order = deutero_order.get(book, 83)
        else:
            book_order = protestant_order.get(book, 99)
        
        return book_order * 1000000 + chapter * 1000 + verse

    def create_cross_reference_lookup(self):
        """Create cross-reference lookup function for verse references"""
        
        print("Creating cross-reference lookup functionality...")
        
        def lookup_verse(verse_ref: str, translations: List[str] = ["KJV", "WEBBE"]) -> Dict[str, str]:
            """
            Lookup function that returns verse text from multiple translations
            
            Args:
                verse_ref: Verse reference (e.g., 'Gen 1:1', 'John 3:16', 'Tobit 1:1')
                translations: List of translation codes to look up
                
            Returns:
                Dictionary mapping translation codes to verse texts
            """
            
            # Parse verse reference
            ref_parts = self._parse_verse_reference(verse_ref)
            if not ref_parts:
                return {"error": f"Invalid verse reference: {verse_ref}"}
            
            book, chapter, verse = ref_parts
            results = {}
            
            for trans_code in translations:
                verse_text = self.session.query(BiblicalText).filter(
                    BiblicalText.book == book,
                    BiblicalText.chapter == chapter,
                    BiblicalText.verse == verse,
                    BiblicalText.translation == trans_code
                ).first()
                
                if verse_text:
                    results[trans_code] = verse_text.text
                else:
                    results[trans_code] = f"Verse not found in {trans_code}"
            
            return results
        
        # Store the lookup function as instance method
        self.lookup_verse = lookup_verse
        print("✓ Cross-reference lookup function created")
        
        # Test the lookup function with sample data
        print("\n📖 Testing cross-reference lookup:")
        test_refs = ["Genesis 1:1", "John 3:16", "Tobit 1:1", "Wisdom of Solomon 1:1"]
        
        for ref in test_refs:
            try:
                result = lookup_verse(ref)
                print(f"  {ref}:")
                for trans, text in result.items():
                    text_preview = text[:60] + "..." if len(text) > 60 else text
                    print(f"    {trans}: {text_preview}")
            except Exception as e:
                print(f"    Error looking up {ref}: {e}")

    def _parse_verse_reference(self, verse_ref: str) -> Optional[Tuple[str, int, int]]:
        """Parse verse reference string into components"""
        
        # Handle various reference formats
        # "Gen 1:1", "Genesis 1:1", "1 John 3:16", "Song of Solomon 2:1", "Tobit 1:1"
        
        patterns = [
            r'^(\d+\s+\w+(?:\s+\w+)*)\s+(\d+):(\d+)$',  # "1 John 3:16", "Song of Solomon 2:1"
            r'^(\w+(?:\s+\w+)*)\s+(\d+):(\d+)$',        # "Genesis 1:1", "Tobit 1:1"
            r'^(\w{3})\s+(\d+):(\d+)$'                   # "Gen 1:1", "Mat 5:3"
        ]
        
        for pattern in patterns:
            match = re.match(pattern, verse_ref.strip())
            if match:
                book_str = match.group(1).strip()
                chapter = int(match.group(2))
                verse = int(match.group(3))
                
                # Handle book name abbreviations
                if len(book_str) == 3 and book_str.upper() in self.usfm_book_codes:
                    book = self.usfm_book_codes[book_str.upper()]
                else:
                    # Try to match full book name or handle variations
                    book = self._normalize_book_name(book_str)
                
                if book:
                    return (book, chapter, verse)
        
        return None

    def _normalize_book_name(self, book_str: str) -> Optional[str]:
        """Normalize book name variations to canonical form"""
        
        book_variations = {
            "Gen": "Genesis", "Genesis": "Genesis",
            "Exo": "Exodus", "Exodus": "Exodus",
            "Mat": "Matthew", "Matthew": "Matthew",
            "Joh": "John", "John": "John",
            "1 Jn": "1 John", "1 John": "1 John",
            "Rev": "Revelation", "Revelation": "Revelation",
            "Tob": "Tobit", "Tobit": "Tobit",
            "Wis": "Wisdom of Solomon", "Wisdom": "Wisdom of Solomon", 
            "Wisdom of Solomon": "Wisdom of Solomon",
            "Sir": "Sirach", "Sirach": "Sirach", "Ecclesiasticus": "Sirach",
            "1 Mac": "1 Maccabees", "1 Maccabees": "1 Maccabees"
        }
        
        return book_variations.get(book_str, book_str if book_str in self.protestant_books + self.deuterocanonical_books else None)

    def run_ingestion(self, kjv_usfm_path: Optional[str] = None, web_usfm_path: Optional[str] = None):
        """Run the complete English texts ingestion process"""
        
        print("=== English Biblical Texts Ingestion (KJV + WEB with Deuterocanon) ===")
        print("Ingesting King James Version and World English Bible Ecumenical Edition")
        print("Including Protestant canonical books + Deuterocanonical/Apocryphal books")
        print()
        
        try:
            # Initialize database session
            self.session = next(get_db())
            
            # Step 1: Create edition metadata
            self.create_edition_metadata()
            print()
            
            # Step 2: Parse and ingest KJV with Apocrypha
            if kjv_usfm_path:
                print("Processing KJV USFM file...")
                kjv_data = self.parse_usfm_text(kjv_usfm_path, "KJV")
            else:
                print("Simulating KJV parsing with placeholder data...")
                kjv_data = self.parse_usfm_text("placeholder_kjv.usfm", "KJV")
            
            self.insert_biblical_texts(kjv_data, "KJV")
            print()
            
            # Step 3: Parse and ingest WEB Ecumenical
            if web_usfm_path:
                print("Processing WEB Ecumenical USFM file...")
                web_data = self.parse_usfm_text(web_usfm_path, "WEBBE")
            else:
                print("Simulating WEB Ecumenical parsing with placeholder data...")
                web_data = self.parse_usfm_text("placeholder_webbe.usfm", "WEBBE")
            
            self.insert_biblical_texts(web_data, "WEBBE")
            print()
            
            # Step 4: Create cross-reference lookup functionality
            self.create_cross_reference_lookup()
            print()
            
            # Verification
            kjv_count = self.session.query(BiblicalText).filter(BiblicalText.translation == "KJV").count()
            web_count = self.session.query(BiblicalText).filter(BiblicalText.translation == "WEBBE").count()
            
            # Count deuterocanonical verses using proper JSON queries
            from sqlalchemy import text
            deutero_kjv = self.session.query(BiblicalText).filter(
                BiblicalText.translation == "KJV",
                text("textual_notes->>'canonical_status' = 'deuterocanon'")
            ).count()
            
            deutero_web = self.session.query(BiblicalText).filter(
                BiblicalText.translation == "WEBBE", 
                text("textual_notes->>'canonical_status' = 'deuterocanon'")
            ).count()
            
            print("✅ English texts ingestion completed successfully!")
            print()
            print("Summary:")
            print(f"- KJV total verses: {kjv_count} (including {deutero_kjv} deuterocanonical)")
            print(f"- WEB Ecumenical verses: {web_count} (including {deutero_web} deuterocanonical)")
            print("- Cross-reference lookup: Available")
            print("- Deuterocanonical support: Full integration with canonical status tracking")
            print()
            print("Supported deuterocanonical books:")
            for book in self.deuterocanonical_books[:8]:  # Show first 8
                print(f"  - {book}")
            print("  - And more...")
            print()
            print("Next steps:")
            print("1. Generate vector embeddings for semantic search")
            print("2. Link to abstract verse IDs for cross-canonical support")  
            print("3. Integrate with existing RAG system for enhanced queries")
            
        except Exception as e:
            print(f"❌ Error during ingestion: {e}")
            if self.session:
                self.session.rollback()
            raise
            
        finally:
            if self.session:
                self.session.close()


def main():
    """Main entry point for English texts ingestion"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Ingest English biblical texts with deuterocanonical support")
    parser.add_argument("--kjv-usfm", help="Path to KJV USFM file")
    parser.add_argument("--web-usfm", help="Path to WEB Ecumenical USFM file")
    parser.add_argument("--simulate", action="store_true",
                       help="Run with placeholder data (default if no files specified)")
    
    args = parser.parse_args()
    
    # Initialize and run ingester
    ingester = EnglishTextsIngester()
    
    if args.simulate or (not args.kjv_usfm and not args.web_usfm):
        print("Running with placeholder data for demonstration...")
        ingester.run_ingestion()
    else:
        ingester.run_ingestion(args.kjv_usfm, args.web_usfm)


if __name__ == "__main__":
    main()