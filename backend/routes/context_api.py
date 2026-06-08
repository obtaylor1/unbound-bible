#!/usr/bin/env python3
"""
Context API for word-level interactive features
Handles linguistic lookups and bias detection for clickable words
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, text
from typing import Optional, Dict, Any, List
import re

from database import get_db
from models import (
    BiblicalText, LexiconEntry, HistoricalNote, 
    GeographicalLocation, OriginalWord, Translation, LanguageEnum
)

router = APIRouter(prefix="/api/v1/context", tags=["context"])


class WordContextService:
    """Service for handling word context lookups"""
    
    def __init__(self, db: Session):
        self.db = db
        
        # Known linguistic mappings for original names
        self.name_mappings = {
            "peter": {
                "original_name": "Shimon bar Yonah / Kepha", 
                "meaning": "He who hears / Rock",
                "language": "Aramaic/Greek",
                "strong_number": "G4074"
            },
            "jesus": {
                "original_name": "Yeshua (ישוע)",
                "meaning": "YHWH saves / Salvation",
                "language": "Hebrew/Aramaic", 
                "strong_number": "H3091"
            },
            "christ": {
                "original_name": "Mashiach (משיח)",
                "meaning": "Anointed One",
                "language": "Hebrew",
                "strong_number": "H4899"
            },
            "life": {
                "original_name": "Zoe (ζωή) / Chai (חי)",
                "meaning": "Life force / Living",
                "language": "Greek/Hebrew",
                "strong_number": "G2222"
            },
            "god": {
                "original_name": "Elohim (אלהים) / Theos (θεός)",
                "meaning": "Mighty ones / Divine being",
                "language": "Hebrew/Greek",
                "strong_number": "H430"
            },
            "lord": {
                "original_name": "YHWH (יהוה) / Adonai (אדני)",
                "meaning": "The eternal / My master",
                "language": "Hebrew",
                "strong_number": "H3068"
            },
            "love": {
                "original_name": "Agape (ἀγάπη) / Ahavah (אהבה)",
                "meaning": "Unconditional love / Affection",
                "language": "Greek/Hebrew",
                "strong_number": "G26"
            },
            "spirit": {
                "original_name": "Pneuma (πνεῦμα) / Ruach (רוח)",
                "meaning": "Breath / Wind / Spirit",
                "language": "Greek/Hebrew",
                "strong_number": "G4151"
            }
        }
        
        # Translation bias patterns for controversial verses
        self.bias_patterns = {
            "sos_1_5": {
                "verse_refs": ["SOS 1:5", "Song of Solomon 1:5", "Song 1:5"],
                "title": "Translator Bias Detected: 'but' vs. 'and'",
                "note": "The KJV adds 'but' where Hebrew uses 'and' (ו), creating unnecessary contrast. The verse celebrates both darkness and beauty without opposition. This change reflects translators' discomfort with affirming darker skin tones.",
                "original_hebrew": "שְׁחוֹרָה אֲנִי וְנָאוָה",
                "literal_translation": "I am dark and lovely"
            },
            "exodus_12_38": {
                "verse_refs": ["Exodus 12:38", "Exod 12:38", "EXO 12:38"],
                "title": "Translation Minimization: Mixed Multitude",
                "note": "Many translations downplay the 'mixed multitude' (erev rav) that left Egypt with Israel, obscuring the diverse ethnic composition of the Exodus community.",
                "original_hebrew": "עֵרֶב רַב",
                "literal_translation": "great mixture / mixed multitude"
            },
            "acts_8_27": {
                "verse_refs": ["Acts 8:27", "ACT 8:27"],
                "title": "Geographic Context: Ethiopian Identity",
                "note": "The Ethiopian eunuch represents early African Christianity. Some translations obscure the significance of this African conversion story in spreading Christianity beyond European boundaries.",
                "original_greek": "Αἰθίοψ",
                "literal_translation": "Ethiopian / Cushite"
            }
        }
    
    def get_word_context(self, word: str, verse_ref: Optional[str] = None) -> Dict[str, Any]:
        """Get linguistic or bias context for a word"""
        
        word_lower = word.lower().strip('.,!?;:"\'()[]{}')
        
        # Check for translation bias first if verse reference provided
        if verse_ref:
            bias_info = self._check_translation_bias(verse_ref)
            if bias_info:
                return bias_info
        
        # Check for linguistic context
        linguistic_info = self._get_linguistic_context(word_lower, verse_ref)
        if linguistic_info:
            return linguistic_info
        
        # Try lexicon lookup for Hebrew/Greek words
        lexicon_info = self._get_lexicon_context(word_lower)
        if lexicon_info:
            return lexicon_info
        
        return {
            "type": "Not Found",
            "message": f"No contextual information available for '{word}'"
        }
    
    def _check_translation_bias(self, verse_ref: str) -> Optional[Dict[str, Any]]:
        """Check if verse has known translation bias issues"""
        
        # Normalize verse reference
        verse_ref_normalized = self._normalize_verse_ref(verse_ref)
        
        for bias_key, bias_data in self.bias_patterns.items():
            for ref_pattern in bias_data["verse_refs"]:
                if self._verse_matches(verse_ref_normalized, ref_pattern):
                    return {
                        "type": "Bias Alert",
                        "title": bias_data["title"],
                        "note": bias_data["note"],
                        "original_text": bias_data.get("original_hebrew") or bias_data.get("original_greek"),
                        "literal_translation": bias_data["literal_translation"],
                        "verse_reference": verse_ref
                    }
        
        # Check historical notes table for additional bias alerts
        # First, find the specific biblical texts for this verse
        verse_parts = self._parse_verse_reference(verse_ref)
        if verse_parts:
            book, chapter, verse = verse_parts
            
            # Query for biblical texts that match this verse
            biblical_texts = self.db.query(BiblicalText).filter(
                BiblicalText.book == book,
                BiblicalText.chapter == chapter,
                BiblicalText.verse == verse
            ).all()
            
            if biblical_texts:
                # Get biblical_text_ids to scope the historical notes query
                biblical_text_ids = [bt.id for bt in biblical_texts]
                
                # Query historical notes that are actually linked to this specific verse
                historical_note = self.db.query(HistoricalNote).filter(
                    and_(
                        HistoricalNote.biblical_text_id.in_(biblical_text_ids),
                        or_(
                            HistoricalNote.title.ilike("%bias%"),
                            HistoricalNote.title.ilike("%translation%")
                        )
                    )
                ).first()
                
                if historical_note:
                    return {
                        "type": "Bias Alert", 
                        "title": historical_note.title,
                        "note": historical_note.content,
                        "verse_reference": verse_ref,
                        "source": "Historical Notes Database"
                    }
        
        return None
    
    def _get_linguistic_context(self, word: str, verse_ref: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get linguistic context for original language names/words"""
        
        if word in self.name_mappings:
            mapping = self.name_mappings[word]
            
            # Try to get additional context from lexicon
            strong_context = None
            if mapping.get("strong_number"):
                lexicon_entry = self.db.query(LexiconEntry).filter(
                    LexiconEntry.strong_number == mapping["strong_number"]
                ).first()
                if lexicon_entry:
                    strong_context = {
                        "detailed_definition": lexicon_entry.detailed_definition,
                        "usage_notes": lexicon_entry.usage_notes,
                        "part_of_speech": lexicon_entry.part_of_speech
                    }
            
            return {
                "type": "Linguistic",
                "word": word.title(),
                "original_name": mapping["original_name"],
                "meaning": mapping["meaning"],
                "language": mapping["language"],
                "strong_number": mapping.get("strong_number"),
                "verse_reference": verse_ref,
                "lexicon_context": strong_context,
                "cross_references": self._get_cross_references(word, verse_ref)
            }
        
        return None
    
    def _get_lexicon_context(self, word: str) -> Optional[Dict[str, Any]]:
        """Look up word in lexicon entries"""
        
        # Try exact match first
        lexicon_entry = self.db.query(LexiconEntry).filter(
            or_(
                LexiconEntry.original_word.ilike(f"%{word}%"),
                LexiconEntry.transliteration.ilike(f"%{word}%"),
                LexiconEntry.definition.ilike(f"%{word}%")
            )
        ).first()
        
        if lexicon_entry:
            return {
                "type": "Linguistic",
                "word": word.title(),
                "original_name": lexicon_entry.original_word,
                "meaning": lexicon_entry.definition,
                "language": lexicon_entry.language.value if lexicon_entry.language else "Unknown",
                "strong_number": lexicon_entry.strong_number,
                "transliteration": lexicon_entry.transliteration,
                "part_of_speech": lexicon_entry.part_of_speech,
                "detailed_definition": lexicon_entry.detailed_definition
            }
        
        return None
    
    def _normalize_verse_ref(self, verse_ref: str) -> str:
        """Normalize verse reference for comparison"""
        # Remove extra spaces and standardize format
        return re.sub(r'\s+', ' ', verse_ref.strip().upper())
    
    def _verse_matches(self, verse_ref1: str, verse_ref2: str) -> bool:
        """Check if two verse references match"""
        ref1_norm = self._normalize_verse_ref(verse_ref1)
        ref2_norm = self._normalize_verse_ref(verse_ref2)
        return ref1_norm == ref2_norm or ref1_norm in ref2_norm or ref2_norm in ref1_norm
    
    def _get_cross_references(self, word: str, verse_ref: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get cross-references for word usage across translations"""
        
        if not verse_ref:
            return []
        
        try:
            # Parse verse reference to get book, chapter, verse
            parts = self._parse_verse_reference(verse_ref)
            if not parts:
                return []
            
            book, chapter, verse = parts
            
            # Get all translations of this verse
            verses = self.db.query(BiblicalText).filter(
                BiblicalText.book == book,
                BiblicalText.chapter == chapter, 
                BiblicalText.verse == verse
            ).limit(5).all()
            
            cross_refs = []
            for v in verses:
                # Check if the word appears in this translation
                if word.lower() in v.text.lower():
                    cross_refs.append({
                        "translation": v.translation,
                        "text": v.text,
                        "contains_word": True
                    })
            
            return cross_refs
            
        except Exception as e:
            print(f"Error getting cross references: {e}")
            return []
    
    def _parse_verse_reference(self, verse_ref: str) -> Optional[tuple]:
        """Parse verse reference into book, chapter, verse"""
        
        # Handle various formats: "SOS 1:5", "Song of Solomon 1:5", etc.
        patterns = [
            r'^(.*)\s+(\d+):(\d+)$',  # "Book Chapter:Verse"
            r'^(.*)\s+(\d+)\.(\d+)$'  # "Book Chapter.Verse"
        ]
        
        for pattern in patterns:
            match = re.match(pattern, verse_ref.strip())
            if match:
                book_str = match.group(1).strip()
                chapter = int(match.group(2))
                verse = int(match.group(3))
                
                # Normalize book name
                book = self._normalize_book_name(book_str)
                if book:
                    return (book, chapter, verse)
        
        return None
    
    def _normalize_book_name(self, book_str: str) -> Optional[str]:
        """Normalize book name variations"""
        
        book_mappings = {
            "SOS": "Song of Solomon",
            "SONG": "Song of Solomon", 
            "SONG OF SOLOMON": "Song of Solomon",
            "CANTICLES": "Song of Solomon",
            "EXO": "Exodus",
            "EXOD": "Exodus", 
            "EXODUS": "Exodus",
            "ACT": "Acts",
            "ACTS": "Acts"
        }
        
        book_upper = book_str.upper()
        return book_mappings.get(book_upper, book_str)

    def get_canon_history_context(self) -> Dict[str, Any]:
        """Get Constantine myth-buster information"""
        
        return {
            "type": "Canon History",
            "title": "Formation of the Canon: Historical Consensus",
            "content": {
                "myth": "Constantine and the Council of Nicaea (325 AD) determined the biblical canon",
                "reality": "The biblical canon was largely established through North African councils decades later",
                "key_facts": [
                    "Council of Nicaea (325 AD) focused on Christological disputes, not canon formation",
                    "Council of Hippo (393 AD) first listed the 27 NT books we know today", 
                    "Council of Carthage (397 AD) confirmed the canon list",
                    "These were North African councils led by Augustine and other African bishops",
                    "The canon reflected widespread church consensus that had developed organically"
                ],
                "significance": "The biblical canon emerged from African theological scholarship and widespread Christian consensus, not imperial decree",
                "sources": [
                    "Augustine of Hippo's canonical writings",
                    "Athanasius' Festal Letter (367 AD)",
                    "Jerome's Latin Vulgate compilation"
                ]
            }
        }


@router.get("/word")
async def get_word_context(
    word: str = Query(..., description="The word to look up"),
    verse_ref: Optional[str] = Query(None, description="Verse reference (e.g., 'SOS 1:5')"),
    db: Session = Depends(get_db)
):
    """
    Get contextual information for a word - linguistic or bias detection
    
    Returns either:
    - Linguistic context (original Hebrew/Aramaic/Greek with meaning)
    - Bias alert (translation issues and corrections)
    - Not found (no context available)
    """
    
    try:
        service = WordContextService(db)
        context = service.get_word_context(word, verse_ref)
        
        return {
            "success": True,
            "word": word,
            "verse_ref": verse_ref,
            "context": context
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving word context: {str(e)}"
        )


@router.get("/canon-history")
async def get_canon_history():
    """
    Get Constantine myth-buster information about canon formation
    """
    
    try:
        service = WordContextService(next(get_db()))
        history_context = service.get_canon_history_context()
        
        return {
            "success": True,
            "context": history_context
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving canon history: {str(e)}"
        )


@router.get("/test")
async def test_context_endpoint():
    """Test endpoint to verify context API is working"""
    
    return {
        "message": "Context API is operational",
        "endpoints": {
            "/word": "Get linguistic or bias context for words",
            "/canon-history": "Get Constantine myth-buster information"
        }
    }