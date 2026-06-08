#!/usr/bin/env python3
"""
Ingestion script for core original language biblical texts:
- OSHB (Open Scriptures Hebrew Bible - Masoretic Text)
- SBLGNT/UGNT (Greek New Testament)

This script creates EditionMetadata records and implements placeholder parsing
functions for ingesting Hebrew and Greek original language texts.
"""

import sys
import os
import json
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# Add backend directory to path for imports
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
sys.path.insert(0, backend_path)

from sqlalchemy.orm import Session

try:
    from database import get_db, engine
    from models import Translation, BiblicalText, OriginalWord, LexiconEntry, LanguageEnum
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Backend path: {backend_path}")
    print("Make sure you're running this script from the correct directory")
    sys.exit(1)


class CoreOriginalsIngester:
    """Handles ingestion of Hebrew Bible (OSHB) and Greek New Testament (SBLGNT/UGNT)"""
    
    def __init__(self):
        self.session: Optional[Session] = None
        
        # Book name mappings for Hebrew Bible (OSHB)
        self.oshb_book_mapping = {
            "Gen": "Genesis", "Exod": "Exodus", "Lev": "Leviticus", "Num": "Numbers",
            "Deut": "Deuteronomy", "Josh": "Joshua", "Judg": "Judges", "Ruth": "Ruth",
            "1Sam": "1 Samuel", "2Sam": "2 Samuel", "1Kgs": "1 Kings", "2Kgs": "2 Kings",
            "1Chr": "1 Chronicles", "2Chr": "2 Chronicles", "Ezra": "Ezra", "Neh": "Nehemiah",
            "Esth": "Esther", "Job": "Job", "Ps": "Psalms", "Prov": "Proverbs",
            "Eccl": "Ecclesiastes", "Song": "Song of Solomon", "Isa": "Isaiah",
            "Jer": "Jeremiah", "Lam": "Lamentations", "Ezek": "Ezekiel", "Dan": "Daniel",
            "Hos": "Hosea", "Joel": "Joel", "Amos": "Amos", "Obad": "Obadiah",
            "Jonah": "Jonah", "Mic": "Micah", "Nah": "Nahum", "Hab": "Habakkuk",
            "Zeph": "Zephaniah", "Hag": "Haggai", "Zech": "Zechariah", "Mal": "Malachi"
        }
        
        # Book name mappings for Greek New Testament
        self.gnt_book_mapping = {
            "Matt": "Matthew", "Mark": "Mark", "Luke": "Luke", "John": "John",
            "Acts": "Acts", "Rom": "Romans", "1Cor": "1 Corinthians", "2Cor": "2 Corinthians",
            "Gal": "Galatians", "Eph": "Ephesians", "Phil": "Philippians", "Col": "Colossians",
            "1Thess": "1 Thessalonians", "2Thess": "2 Thessalonians", "1Tim": "1 Timothy",
            "2Tim": "2 Timothy", "Titus": "Titus", "Phlm": "Philemon", "Heb": "Hebrews",
            "Jas": "James", "1Pet": "1 Peter", "2Pet": "2 Peter", "1John": "1 John",
            "2John": "2 John", "3John": "3 John", "Jude": "Jude", "Rev": "Revelation"
        }

    def create_edition_metadata(self):
        """Create EditionMetadata records (using Translation model) for OSHB and SBLGNT/UGNT"""
        
        print("Creating edition metadata records...")
        
        # OSHB (Hebrew Masoretic Text)
        oshb_translation = Translation(
            code="OSHB",
            name="Open Scriptures Hebrew Bible",
            description="Hebrew Masoretic Text with morphological analysis from Open Scriptures",
            language="Hebrew",  # Hebrew (hbo language script)
            source_text="Masoretic Text",
            year_published=None,  # Ancient text, no specific publication year
            is_original_language=True,
            is_public_domain=True  # CC BY 4.0 license
        )
        
        # Check if OSHB already exists
        existing_oshb = self.session.query(Translation).filter(Translation.code == "OSHB").first()
        if not existing_oshb:
            self.session.add(oshb_translation)
            print("✓ Created OSHB (Hebrew MT) edition metadata")
            print("  - Language: Hebrew (hbo)")
            print("  - Canon tags: protestant, catholic, orthodox, ethiopian")
            print("  - License: CC BY 4.0")
            print("  - Has morphological analysis: True")
        else:
            print("✓ OSHB edition metadata already exists")
        
        # SBLGNT (Greek New Testament)
        sblgnt_translation = Translation(
            code="SBLGNT",
            name="SBL Greek New Testament",
            description="Society of Biblical Literature Greek New Testament with critical apparatus",
            language="Greek",  # Greek (grc language script)
            source_text="Critical Greek Text",
            year_published=2010,
            is_original_language=True,
            is_public_domain=True  # CC BY-SA license
        )
        
        # Check if SBLGNT already exists
        existing_sblgnt = self.session.query(Translation).filter(Translation.code == "SBLGNT").first()
        if not existing_sblgnt:
            self.session.add(sblgnt_translation)
            print("✓ Created SBLGNT (Greek NT) edition metadata")
            print("  - Language: Greek (grc)")
            print("  - Canon tags: protestant, catholic, orthodox, ethiopian")
            print("  - License: CC BY-SA")
            print("  - Has morphological analysis: True")
        else:
            print("✓ SBLGNT edition metadata already exists")
        
        # Alternative: UGNT (Unfolding Greek New Testament)
        ugnt_translation = Translation(
            code="UGNT",
            name="Unfolding Greek New Testament",
            description="Greek New Testament with detailed morphological parsing and translation notes",
            language="Greek",
            source_text="Nestle-Aland/UBS Critical Text",
            year_published=2022,
            is_original_language=True,
            is_public_domain=True  # CC BY-SA 4.0 license (better for full redistribution)
        )
        
        # Check if UGNT already exists
        existing_ugnt = self.session.query(Translation).filter(Translation.code == "UGNT").first()
        if not existing_ugnt:
            self.session.add(ugnt_translation)
            print("✓ Created UGNT (Greek NT) edition metadata")
            print("  - Language: Greek (grc)")
            print("  - Canon tags: protestant, catholic, orthodox, ethiopian")
            print("  - License: CC BY-SA 4.0 (preferred for full redistribution)")
            print("  - Has morphological analysis: True")
        else:
            print("✓ UGNT edition metadata already exists")
        
        self.session.commit()
        print("✓ Edition metadata records created successfully")

    def parse_oshb_xml(self, xml_file_path: str) -> List[Dict]:
        """
        Placeholder function to parse OSHB XML files
        
        Expected OSHB XML structure:
        <osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace">
          <osisText>
            <div type="book" osisID="Gen">
              <chapter osisID="Gen.1">
                <verse osisID="Gen.1.1">
                  <w lemma="H7225" morph="Ncfsa" src="1">בְּרֵאשִׁית֙</w>
                  <w lemma="H1254" morph="Vqp3ms" src="2">בָּרָ֣א</w>
                  <w lemma="H430" morph="Ncmpa" src="3">אֱלֹהִ֔ים</w>
                </verse>
              </chapter>
            </div>
          </osisText>
        </osis>
        """
        
        print(f"Parsing OSHB XML file: {xml_file_path}")
        
        # Placeholder data structure representing parsed OSHB content
        # In real implementation, this would parse the actual XML file
        parsed_data = [
            {
                "book": "Genesis",
                "chapter": 1,
                "verse": 1,
                "text": "בְּרֵאשִׁית֙ בָּרָ֣א אֱלֹהִ֔ים אֵ֥ת הַשָּׁמַ֖יִם וְאֵ֥ת הָאָֽרֶץ׃",
                "words": [
                    {
                        "word": "בְּרֵאשִׁית֙",
                        "lemma": "H7225",  # Strong's number
                        "morph": "Ncfsa",  # Morphological code
                        "transliteration": "bereshit",
                        "gloss": "beginning"
                    },
                    {
                        "word": "בָּרָ֣א",
                        "lemma": "H1254",
                        "morph": "Vqp3ms",
                        "transliteration": "bara",
                        "gloss": "created"
                    },
                    {
                        "word": "אֱלֹהִ֔ים",
                        "lemma": "H430",
                        "morph": "Ncmpa",
                        "transliteration": "elohim",
                        "gloss": "God"
                    }
                ]
            }
        ]
        
        # TODO: Implement actual XML parsing logic
        # tree = ET.parse(xml_file_path)
        # root = tree.getroot()
        # ... parse XML structure ...
        
        print(f"✓ Parsed {len(parsed_data)} verses from OSHB XML (placeholder data)")
        return parsed_data

    def parse_ugnt_text(self, tsv_file_path: str) -> List[Dict]:
        """
        Placeholder function to parse UGNT TSV/text files
        
        Expected UGNT TSV structure:
        Reference\tGreekText\tSBLText\tParsing\tLemma\tGloss\tMorphology\tNormalized
        40001001\tΚατὰ\tΚατὰ\tPREP\tκατά\taccording to\tPrep\tκατα
        40001001\tΜαθθαῖον\tΜαθθαῖον\tN-ASM\tΜαθθαῖος\tMatthew\tN-ASM\tματθαιον
        """
        
        print(f"Parsing UGNT TSV file: {tsv_file_path}")
        
        # Placeholder data structure representing parsed UGNT content
        # In real implementation, this would parse the actual TSV file
        parsed_data = [
            {
                "book": "Matthew",
                "chapter": 1,
                "verse": 1,
                "text": "Βίβλος γενέσεως Ἰησοῦ Χριστοῦ υἱοῦ Δαυὶδ υἱοῦ Ἀβραάμ.",
                "words": [
                    {
                        "word": "Βίβλος",
                        "lemma": "G976",  # Strong's number
                        "morph": "N-NSF",  # Morphological code
                        "transliteration": "biblos",
                        "gloss": "book"
                    },
                    {
                        "word": "γενέσεως",
                        "lemma": "G1078",
                        "morph": "N-GSF",
                        "transliteration": "geneseos",
                        "gloss": "generation"
                    },
                    {
                        "word": "Ἰησοῦ",
                        "lemma": "G2424",
                        "morph": "N-GSM",
                        "transliteration": "Iesou",
                        "gloss": "Jesus"
                    }
                ]
            }
        ]
        
        # TODO: Implement actual TSV parsing logic
        # with open(tsv_file_path, 'r', encoding='utf-8') as f:
        #     for line in f:
        #         fields = line.strip().split('\t')
        #         ... parse TSV structure ...
        
        print(f"✓ Parsed {len(parsed_data)} verses from UGNT TSV (placeholder data)")
        return parsed_data

    def insert_biblical_texts(self, parsed_data: List[Dict], translation_code: str):
        """Insert parsed original language texts into biblical_texts table"""
        
        print(f"Inserting biblical texts for {translation_code}...")
        
        # Get translation record
        translation = self.session.query(Translation).filter(
            Translation.code == translation_code
        ).first()
        
        if not translation:
            raise ValueError(f"Translation '{translation_code}' not found in database")
        
        verse_count = 0
        word_count = 0
        
        for verse_data in parsed_data:
            # Create BiblicalText record
            biblical_text = BiblicalText(
                book=verse_data["book"],
                chapter=verse_data["chapter"],
                verse=verse_data["verse"],
                text=verse_data["text"],
                translation=translation_code,
                translation_id=translation.id,
                # Note: text_embedding will be generated separately via vector_search service
                canonical_order=self._get_canonical_order(verse_data["book"], 
                                                        verse_data["chapter"], 
                                                        verse_data["verse"])
            )
            
            self.session.add(biblical_text)
            self.session.flush()  # Get the ID
            verse_count += 1
            
            # Create OriginalWord records for morphological analysis
            if "words" in verse_data:
                for word_position, word_data in enumerate(verse_data["words"], 1):
                    # Find or create lexicon entry
                    lexicon_entry = self._get_or_create_lexicon_entry(
                        word_data["lemma"], 
                        word_data.get("gloss", ""),
                        translation_code
                    )
                    
                    # Create OriginalWord record  
                    language = LanguageEnum.hebrew if translation_code == "OSHB" else LanguageEnum.greek
                    original_word = OriginalWord(
                        biblical_text_id=biblical_text.id,
                        lexicon_entry_id=lexicon_entry.id if lexicon_entry else None,
                        word_text=word_data["word"],
                        language=language,
                        definition=word_data.get("gloss", ""),
                        word_position=word_position,
                        strong_number=word_data.get("lemma", "")
                    )
                    
                    self.session.add(original_word)
                    word_count += 1
        
        self.session.commit()
        print(f"✓ Inserted {verse_count} verses and {word_count} original language words for {translation_code}")

    def _get_canonical_order(self, book: str, chapter: int, verse: int) -> int:
        """Calculate canonical ordering for verse"""
        # Simplified canonical ordering (book_order * 1000000 + chapter * 1000 + verse)
        book_orders = {
            "Genesis": 1, "Exodus": 2, "Leviticus": 3, "Numbers": 4, "Deuteronomy": 5,
            "Matthew": 40, "Mark": 41, "Luke": 42, "John": 43, "Acts": 44
            # ... add all 66+ books
        }
        
        book_order = book_orders.get(book, 99)
        return book_order * 1000000 + chapter * 1000 + verse

    def _get_or_create_lexicon_entry(self, strong_number: str, definition: str, translation_code: str) -> Optional[LexiconEntry]:
        """Get existing lexicon entry or create new one"""
        if not strong_number:
            return None
            
        existing_entry = self.session.query(LexiconEntry).filter(
            LexiconEntry.strong_number == strong_number
        ).first()
        
        if existing_entry:
            return existing_entry
        
        # Determine language from Strong's number
        language = LanguageEnum.hebrew if strong_number.startswith('H') else LanguageEnum.greek
        
        # Create new lexicon entry
        new_entry = LexiconEntry(
            strong_number=strong_number,
            language=language,
            original_word="",  # Would be filled from actual lexicon data
            definition=definition,
            transliteration=""  # Would be filled from actual lexicon data
        )
        
        self.session.add(new_entry)
        self.session.flush()
        return new_entry

    def run_ingestion(self, oshb_xml_path: Optional[str] = None, ugnt_tsv_path: Optional[str] = None):
        """Run the complete ingestion process"""
        
        print("=== Core Original Language Texts Ingestion ===")
        print("Ingesting Hebrew Bible (OSHB) and Greek New Testament (SBLGNT/UGNT)")
        print()
        
        try:
            # Initialize database session
            self.session = next(get_db())
            
            # Step 1: Create edition metadata
            self.create_edition_metadata()
            print()
            
            # Step 2: Parse and ingest OSHB (Hebrew Bible)
            if oshb_xml_path:
                print("Processing OSHB (Hebrew Bible)...")
                oshb_data = self.parse_oshb_xml(oshb_xml_path)
                self.insert_biblical_texts(oshb_data, "OSHB")
            else:
                print("Simulating OSHB parsing with placeholder data...")
                oshb_data = self.parse_oshb_xml("placeholder_oshb.xml")
                self.insert_biblical_texts(oshb_data, "OSHB")
            print()
            
            # Step 3: Parse and ingest UGNT (Greek New Testament)
            if ugnt_tsv_path:
                print("Processing UGNT (Greek New Testament)...")
                ugnt_data = self.parse_ugnt_text(ugnt_tsv_path)
                self.insert_biblical_texts(ugnt_data, "UGNT")
            else:
                print("Simulating UGNT parsing with placeholder data...")
                ugnt_data = self.parse_ugnt_text("placeholder_ugnt.tsv")
                self.insert_biblical_texts(ugnt_data, "UGNT")
            print()
            
            print("✅ Core original language texts ingestion completed successfully!")
            print()
            print("Summary:")
            print("- OSHB (Hebrew MT): language_script=hbo/Hebrew, canon_tags=all, license=CC BY 4.0, has_morph=True")
            print("- SBLGNT (Greek NT): language_script=grc/Greek, canon_tags=all, license=CC BY-SA")
            print("- UGNT (Greek NT): language_script=grc/Greek, canon_tags=all, license=CC BY-SA 4.0, has_morph=True")
            print()
            print("Next steps:")
            print("1. Generate vector embeddings for semantic search")
            print("2. Link to abstract verse IDs for cross-canonical support")
            print("3. Populate morphological analysis with full lexicon data")
            
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
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Ingest core original language biblical texts")
    parser.add_argument("--oshb-xml", help="Path to OSHB XML file")
    parser.add_argument("--ugnt-tsv", help="Path to UGNT TSV file")
    parser.add_argument("--simulate", action="store_true", 
                       help="Run with placeholder data (default if no files specified)")
    
    args = parser.parse_args()
    
    # Initialize and run ingester
    ingester = CoreOriginalsIngester()
    
    if args.simulate or (not args.oshb_xml and not args.ugnt_tsv):
        print("Running with placeholder data for demonstration...")
        ingester.run_ingestion()
    else:
        ingester.run_ingestion(args.oshb_xml, args.ugnt_tsv)


if __name__ == "__main__":
    main()