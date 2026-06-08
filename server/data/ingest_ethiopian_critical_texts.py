#!/usr/bin/env python3
"""
Ingestion script for Ethiopian canonical texts and critical cross-reference works:
- Ethiopian additions: 1 Enoch, Jubilees, Meqabyan 1-3
- Critical reference texts: Josephus, Targum Onkelos
- Enhanced lexical linking with Strong's Numbers for Hebrew words

Creates proper EditionMetadata records and prepares for word-click functionality.
"""

import sys
import os
import json
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# Add backend and server paths for imports
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
server_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, backend_path)
sys.path.insert(0, os.path.join(server_path, 'models'))

from sqlalchemy.orm import Session

try:
    # Import from backend
    from database import get_db, engine
    from models import BiblicalText, Translation, OriginalWord, LexiconEntry, LanguageEnum
    # Import from server models
    from edition_metadata import EditionMetadata, IngestStatusEnum
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Backend path: {backend_path}")
    print(f"Server path: {server_path}")
    print("Make sure you're running this script from the correct directory")
    sys.exit(1)


class EthiopianCriticalTextsIngester:
    """Handles ingestion of Ethiopian canonical texts and critical cross-reference works"""
    
    def __init__(self):
        self.session: Optional[Session] = None
        
        # Strong's Numbers for Genesis 1:1 Hebrew words (for lexical enhancement)
        self.genesis_1_1_hebrew_words = [
            {
                "word": "בְּרֵאשִׁית֙",
                "transliteration": "bereshit", 
                "strong_number": "H7225",
                "part_of_speech": "noun",
                "definition": "beginning, first, chief",
                "position": 1
            },
            {
                "word": "בָּרָ֣א",
                "transliteration": "bara",
                "strong_number": "H1254", 
                "part_of_speech": "verb",
                "definition": "to create, shape, form",
                "position": 2
            },
            {
                "word": "אֱלֹהִ֔ים",
                "transliteration": "elohim",
                "strong_number": "H430",
                "part_of_speech": "noun",
                "definition": "God, gods",
                "position": 3
            },
            {
                "word": "אֵ֥ת",
                "transliteration": "et",
                "strong_number": "H853",
                "part_of_speech": "particle", 
                "definition": "sign of the definite direct object",
                "position": 4
            },
            {
                "word": "הַשָּׁמַ֖יִם",
                "transliteration": "hashamayim",
                "strong_number": "H8064",
                "part_of_speech": "noun",
                "definition": "heaven, heavens, sky",
                "position": 5
            },
            {
                "word": "וְאֵ֥ת",
                "transliteration": "ve'et",
                "strong_number": "H853",
                "part_of_speech": "conjunction + particle",
                "definition": "and + sign of direct object",
                "position": 6
            },
            {
                "word": "הָאָֽרֶץ",
                "transliteration": "ha'aretz",
                "strong_number": "H776",
                "part_of_speech": "noun",
                "definition": "earth, land",
                "position": 7
            }
        ]

    def create_ethiopian_critical_metadata(self):
        """Create EditionMetadata records for Ethiopian canonical and critical reference texts"""
        
        print("Creating edition metadata for Ethiopian and critical reference texts...")
        
        # 1 Enoch (Charles translation, Public Domain)
        enoch_edition = EditionMetadata(
            work_id="1_ENOCH_CHARLES",
            language_script="en/English",
            canon_tags=["ethiopian", "pseudepigrapha"],
            source_title="The Book of Enoch (R.H. Charles Translation)",
            editor_translator="R.H. Charles",
            publisher="Oxford University Press (1912)",
            license="PD",
            provenance_url="https://archive.org/details/bookofenoch00char",
            has_morph=False,
            ingest_status=IngestStatusEnum.queued
        )
        
        # Check if 1 Enoch already exists
        existing_enoch = self.session.query(EditionMetadata).filter(
            EditionMetadata.work_id == "1_ENOCH_CHARLES"
        ).first()
        
        if not existing_enoch:
            self.session.add(enoch_edition)
            print("✓ Created 1 Enoch (Charles) edition metadata")
            print("  - Canon tags: ethiopian, pseudepigrapha")
            print("  - License: Public Domain")
            print("  - Translation: R.H. Charles (1912)")
        else:
            print("✓ 1 Enoch (Charles) edition metadata already exists")
        
        # Jubilees (Charles translation, Public Domain)
        jubilees_edition = EditionMetadata(
            work_id="JUBILEES_CHARLES",
            language_script="en/English",
            canon_tags=["ethiopian", "broader_canon"],
            source_title="The Book of Jubilees (R.H. Charles Translation)",
            editor_translator="R.H. Charles",
            publisher="Adam & Charles Black (1902)",
            license="PD",
            provenance_url="https://archive.org/details/bookjubileesorl00char",
            has_morph=False,
            ingest_status=IngestStatusEnum.queued
        )
        
        # Check if Jubilees already exists
        existing_jubilees = self.session.query(EditionMetadata).filter(
            EditionMetadata.work_id == "JUBILEES_CHARLES"
        ).first()
        
        if not existing_jubilees:
            self.session.add(jubilees_edition)
            print("✓ Created Jubilees (Charles) edition metadata")
            print("  - Canon tags: ethiopian, broader_canon")
            print("  - License: Public Domain")
            print("  - Translation: R.H. Charles (1902)")
        else:
            print("✓ Jubilees (Charles) edition metadata already exists")
        
        # Meqabyan 1-3 (Wikisource versions)
        meqabyan_books = [
            ("MEQABYAN_1_WIKISOURCE", "1 Meqabyan (Ethiopian Maccabees I)", "1 Meqabyan"),
            ("MEQABYAN_2_WIKISOURCE", "2 Meqabyan (Ethiopian Maccabees II)", "2 Meqabyan"),
            ("MEQABYAN_3_WIKISOURCE", "3 Meqabyan (Ethiopian Maccabees III)", "3 Meqabyan")
        ]
        
        for work_id, title, short_name in meqabyan_books:
            meqabyan_edition = EditionMetadata(
                work_id=work_id,
                language_script="en/English",
                canon_tags=["ethiopian"],
                source_title=title,
                editor_translator="Wikisource Contributors",
                publisher="Wikimedia Foundation",
                license="CC BY-SA",
                provenance_url=f"https://en.wikisource.org/wiki/{short_name.replace(' ', '_')}",
                has_morph=False,
                ingest_status=IngestStatusEnum.queued
            )
            
            # Check if already exists
            existing = self.session.query(EditionMetadata).filter(
                EditionMetadata.work_id == work_id
            ).first()
            
            if not existing:
                self.session.add(meqabyan_edition)
                print(f"✓ Created {short_name} (Wikisource) edition metadata")
                print("  - Canon tags: ethiopian")
                print("  - License: CC BY-SA")
            else:
                print(f"✓ {short_name} (Wikisource) edition metadata already exists")
        
        # Josephus (Whiston translation, Public Domain)
        josephus_edition = EditionMetadata(
            work_id="JOSEPHUS_WHISTON",
            language_script="en/English",
            canon_tags=["extra_biblical"],
            source_title="The Works of Flavius Josephus (William Whiston Translation)",
            editor_translator="William Whiston",
            publisher="Oakley & Mason (1737)",
            license="PD",
            provenance_url="https://www.gutenberg.org/ebooks/2848",
            has_morph=False,
            ingest_status=IngestStatusEnum.queued
        )
        
        # Check if Josephus already exists
        existing_josephus = self.session.query(EditionMetadata).filter(
            EditionMetadata.work_id == "JOSEPHUS_WHISTON"
        ).first()
        
        if not existing_josephus:
            self.session.add(josephus_edition)
            print("✓ Created Josephus (Whiston) edition metadata")
            print("  - Canon tags: extra_biblical")
            print("  - License: Public Domain")
            print("  - Translation: William Whiston (1737)")
        else:
            print("✓ Josephus (Whiston) edition metadata already exists")
        
        # Targum Onkelos (Aramaic, Public Domain)
        targum_edition = EditionMetadata(
            work_id="TARGUM_ONKELOS_PD",
            language_script="arc/Aramaic",
            canon_tags=["extra_biblical", "targum"],
            source_title="Targum Onkelos (Public Domain Edition)",
            editor_translator="Traditional Aramaic Translation",
            publisher="Various Traditional Sources",
            license="PD",
            provenance_url="https://archive.org/details/targum-onkelos",
            has_morph=True,
            ingest_status=IngestStatusEnum.queued
        )
        
        # Check if Targum Onkelos already exists
        existing_targum = self.session.query(EditionMetadata).filter(
            EditionMetadata.work_id == "TARGUM_ONKELOS_PD"
        ).first()
        
        if not existing_targum:
            self.session.add(targum_edition)
            print("✓ Created Targum Onkelos edition metadata")
            print("  - Language: Aramaic (arc)")
            print("  - Canon tags: extra_biblical, targum")
            print("  - License: Public Domain")
            print("  - Has morphological analysis: True")
        else:
            print("✓ Targum Onkelos edition metadata already exists")
        
        self.session.commit()
        print("✓ Ethiopian and critical reference edition metadata created successfully")

    def enhance_hebrew_lexical_linking(self):
        """Enhance lexical linking for Hebrew words with Strong's Numbers (Genesis 1:1 example)"""
        
        print("Enhancing Hebrew lexical linking with Strong's Numbers...")
        
        # Find Genesis 1:1 in Hebrew (OSHB or Hebrew text)
        genesis_verse = self.session.query(BiblicalText).filter(
            BiblicalText.book == "Genesis",
            BiblicalText.chapter == 1,
            BiblicalText.verse == 1,
            BiblicalText.translation.in_(["OSHB", "MT", "Hebrew"])
        ).first()
        
        if not genesis_verse:
            print("⚠️ Genesis 1:1 Hebrew text not found, creating sample record...")
            
            # Create sample Hebrew Genesis 1:1 if not exists
            hebrew_translation = self.session.query(Translation).filter(
                Translation.code == "OSHB"
            ).first()
            
            if not hebrew_translation:
                hebrew_translation = Translation(
                    code="OSHB",
                    name="Open Scriptures Hebrew Bible",
                    description="Hebrew Masoretic Text with morphological analysis",
                    language="Hebrew",
                    source_text="Masoretic Text",
                    is_original_language=True,
                    is_public_domain=True
                )
                self.session.add(hebrew_translation)
                self.session.commit()
            
            # Create Hebrew Genesis 1:1
            genesis_verse = BiblicalText(
                book="Genesis",
                chapter=1,
                verse=1,
                text="בְּרֵאשִׁית֙ בָּרָ֣א אֱלֹהִ֔ים אֵ֥ת הַשָּׁמַ֖יִם וְאֵ֥ת הָאָֽרֶץ׃",
                translation="OSHB",
                translation_id=hebrew_translation.id,
                textual_notes={"language": "hebrew", "has_vowels": True, "has_cantillation": True}
            )
            self.session.add(genesis_verse)
            self.session.commit()
            print("✓ Created Hebrew Genesis 1:1 text record")
        
        # Create or verify lexicon entries for each Hebrew word
        lexicon_count = 0
        word_link_count = 0
        
        for word_data in self.genesis_1_1_hebrew_words:
            # Get or create lexicon entry (check first to avoid duplicates)
            lexicon_entry = self.session.query(LexiconEntry).filter(
                LexiconEntry.strong_number == word_data["strong_number"]
            ).first()
            
            if not lexicon_entry:
                lexicon_entry = LexiconEntry(
                    strong_number=word_data["strong_number"],
                    language=LanguageEnum.hebrew,
                    original_word=word_data["word"],
                    transliteration=word_data["transliteration"],
                    part_of_speech=word_data["part_of_speech"],
                    definition=word_data["definition"],
                    detailed_definition=f"Hebrew word: {word_data['word']} ({word_data['transliteration']}). Definition: {word_data['definition']}",
                    usage_notes=f"Genesis 1:1 word #{word_data['position']}"
                )
                self.session.add(lexicon_entry)
                self.session.flush()  # Flush individually to handle duplicates
                lexicon_count += 1
            else:
                print(f"  - Strong's {word_data['strong_number']} already exists: {word_data['word']}")
        
        self.session.commit()
        
        # Create OriginalWord entries linking Hebrew words to Strong's numbers
        for word_data in self.genesis_1_1_hebrew_words:
            # Check if word linking already exists
            existing_word = self.session.query(OriginalWord).filter(
                OriginalWord.biblical_text_id == genesis_verse.id,
                OriginalWord.word_position == word_data["position"]
            ).first()
            
            if not existing_word:
                # Get the lexicon entry
                lexicon_entry = self.session.query(LexiconEntry).filter(
                    LexiconEntry.strong_number == word_data["strong_number"]
                ).first()
                
                if lexicon_entry:
                    original_word = OriginalWord(
                        biblical_text_id=genesis_verse.id,
                        lexicon_entry_id=lexicon_entry.id,
                        word_text=word_data["word"],
                        language=LanguageEnum.hebrew,
                        strong_number=word_data["strong_number"],
                        definition=word_data["definition"],
                        word_position=word_data["position"]
                    )
                    self.session.add(original_word)
                    word_link_count += 1
        
        self.session.commit()
        
        print(f"✓ Enhanced Hebrew lexical linking:")
        print(f"  - Created {lexicon_count} new lexicon entries")
        print(f"  - Created {word_link_count} word-to-Strong's links")
        print(f"  - Genesis 1:1 Hebrew words: {len(self.genesis_1_1_hebrew_words)} words linked")
        print("  - Ready for word-click functionality")

    def insert_sample_critical_texts(self):
        """Insert sample texts for Ethiopian and critical reference works"""
        
        print("Inserting sample texts for critical reference works...")
        
        # Sample data for each work (using shorter translation codes for database constraint)
        sample_texts = [
            {
                "work_id": "1_ENOCH_CHARLES",
                "translation_code": "1EN_CH",  # Shortened to fit varchar(10)
                "book": "1 Enoch",
                "chapter": 1,
                "verse": 1,
                "text": "The words of the blessing of Enoch, wherewith he blessed the elect and righteous, who will be living in the day of tribulation, when all the wicked and godless are to be removed.",
                "canon_tags": ["ethiopian", "pseudepigrapha"]
            },
            {
                "work_id": "JUBILEES_CHARLES", 
                "translation_code": "JUB_CH",  # Shortened to fit varchar(10)
                "book": "Jubilees",
                "chapter": 1,
                "verse": 1,
                "text": "This is the history of the division of the days of the torah and of the testimony, of the events of the years, of their year weeks, of their jubilees throughout all the years of the world.",
                "canon_tags": ["ethiopian", "broader_canon"]
            },
            {
                "work_id": "MEQABYAN_1_WIKISOURCE",
                "translation_code": "MEQ1", 
                "book": "1 Meqabyan",
                "chapter": 1,
                "verse": 1,
                "text": "In those days there arose wicked men in Israel, and they persuaded many, saying: 'Let us go and make a covenant with the Gentiles around us, for since we separated from them many evils have come upon us.'",
                "canon_tags": ["ethiopian"]
            },
            {
                "work_id": "JOSEPHUS_WHISTON",
                "translation_code": "JOSEPHUS",  # Shortened to fit varchar(10)
                "book": "Antiquities",
                "chapter": 1,
                "verse": 1,
                "text": "In the beginning God created the heaven and the earth. But when the earth did not come into sight, but was covered with thick darkness, and a wind moved upon its surface, God commanded that there should be light.",
                "canon_tags": ["extra_biblical"]
            },
            {
                "work_id": "TARGUM_ONKELOS_PD",
                "translation_code": "TARG_ON",
                "book": "Genesis Targum",
                "chapter": 1,
                "verse": 1,
                "text": "בְּקַדְמִיתָא בְּרָא יְיָ יָת שְׁמַיָּא וְיָת אַרְעָא", # Aramaic text
                "canon_tags": ["extra_biblical", "targum"]
            }
        ]
        
        total_inserted = 0
        
        for text_data in sample_texts:
            # Get or create translation record
            translation = self.session.query(Translation).filter(
                Translation.code == text_data["translation_code"]
            ).first()
            
            if not translation:
                # Determine language and properties
                is_aramaic = text_data["work_id"] == "TARGUM_ONKELOS_PD"
                language = "Aramaic" if is_aramaic else "English"
                
                translation = Translation(
                    code=text_data["translation_code"],
                    name=f"{text_data['book']} Translation",
                    description=f"Translation for {text_data['book']}",
                    language=language,
                    source_text="Critical Edition",
                    is_original_language=is_aramaic,
                    is_public_domain=True
                )
                self.session.add(translation)
                self.session.commit()
            
            # Check if text already exists
            existing_text = self.session.query(BiblicalText).filter(
                BiblicalText.book == text_data["book"],
                BiblicalText.chapter == text_data["chapter"],
                BiblicalText.verse == text_data["verse"],
                BiblicalText.translation == text_data["translation_code"]
            ).first()
            
            if not existing_text:
                # Create textual notes with canon information
                textual_notes = {
                    "canon_tags": text_data["canon_tags"],
                    "work_type": "critical_reference" if "extra_biblical" in text_data["canon_tags"] else "canonical",
                    "ethiopian_canon": "ethiopian" in text_data["canon_tags"]
                }
                
                biblical_text = BiblicalText(
                    book=text_data["book"],
                    chapter=text_data["chapter"],
                    verse=text_data["verse"],
                    text=text_data["text"],
                    translation=text_data["translation_code"],
                    translation_id=translation.id,
                    textual_notes=textual_notes
                )
                
                self.session.add(biblical_text)
                total_inserted += 1
        
        self.session.commit()
        print(f"✓ Inserted {total_inserted} sample texts for critical reference works")

    def verify_integration(self):
        """Verify the Ethiopian and critical texts integration"""
        
        print("\nVerifying Ethiopian and critical texts integration...")
        
        try:
            # Count Ethiopian editions
            ethiopian_count = self.session.query(EditionMetadata).filter(
                EditionMetadata.canon_tags.contains(['ethiopian'])
            ).count()
            print(f"  - Ethiopian canonical editions: {ethiopian_count}")
            
            # Count extra-biblical editions
            extra_biblical_count = self.session.query(EditionMetadata).filter(
                EditionMetadata.canon_tags.contains(['extra_biblical'])
            ).count()
            print(f"  - Extra-biblical reference editions: {extra_biblical_count}")
            
            # Count Aramaic editions
            aramaic_count = self.session.query(EditionMetadata).filter(
                EditionMetadata.language_script.like('%Aramaic%')
            ).count()
            print(f"  - Aramaic editions: {aramaic_count}")
            
            # Verify Hebrew lexical enhancement
            gen_hebrew_words = self.session.query(OriginalWord).join(BiblicalText).filter(
                BiblicalText.book == "Genesis",
                BiblicalText.chapter == 1,
                BiblicalText.verse == 1,
                OriginalWord.language == LanguageEnum.hebrew
            ).count()
            print(f"  - Genesis 1:1 Hebrew words with Strong's links: {gen_hebrew_words}")
            
            # Sample lexicon entries
            strong_entries = self.session.query(LexiconEntry).filter(
                LexiconEntry.strong_number.in_(["H7225", "H1254", "H430", "H853"])
            ).count()
            print(f"  - Genesis 1:1 Strong's lexicon entries: {strong_entries}/4")
            
            print("✅ Integration verification completed")
            
        except Exception as e:
            print(f"❌ Verification error: {e}")

    def run_ingestion(self):
        """Run the complete Ethiopian and critical texts ingestion"""
        
        print("=== Ethiopian Canon & Critical Reference Texts Ingestion ===")
        print("Adding metadata for Ethiopian additions and cross-reference works")
        print("Includes: 1 Enoch, Jubilees, Meqabyan 1-3, Josephus, Targum Onkelos")
        print()
        
        try:
            # Initialize database session
            self.session = next(get_db())
            
            # Step 1: Create edition metadata
            self.create_ethiopian_critical_metadata()
            print()
            
            # Step 2: Enhance Hebrew lexical linking
            self.enhance_hebrew_lexical_linking()
            print()
            
            # Step 3: Insert sample critical texts
            self.insert_sample_critical_texts()
            print()
            
            # Step 4: Verify integration
            self.verify_integration()
            print()
            
            print("✅ Ethiopian and critical reference texts ingestion completed!")
            print()
            print("Summary of additions:")
            print("📜 Ethiopian Canonical Works:")
            print("  - 1 Enoch (R.H. Charles translation)")
            print("  - Jubilees (R.H. Charles translation)")  
            print("  - Meqabyan 1-3 (Ethiopian Maccabees)")
            print()
            print("📚 Critical Reference Works:")
            print("  - Josephus (William Whiston translation)")
            print("  - Targum Onkelos (Aramaic)")
            print()
            print("🔗 Lexical Enhancement:")
            print("  - Genesis 1:1 Hebrew words linked to Strong's Numbers")
            print("  - Word-click functionality preparation complete")
            print()
            print("Next steps:")
            print("1. Integrate with existing RAG system")
            print("2. Add cross-reference functionality")
            print("3. Implement word-click Hebrew lexicon lookup")
            
        except Exception as e:
            print(f"❌ Error during ingestion: {e}")
            if self.session:
                self.session.rollback()
            raise
            
        finally:
            if self.session:
                self.session.close()


def main():
    """Main entry point for Ethiopian and critical texts ingestion"""
    
    print("Running Ethiopian canonical and critical reference texts ingestion...")
    
    # Initialize and run ingester
    ingester = EthiopianCriticalTextsIngester()
    ingester.run_ingestion()


if __name__ == "__main__":
    main()