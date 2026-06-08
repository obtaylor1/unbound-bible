# Liberation Bible Project - Verse Resolution Service
# Handles mapping between abstract verse IDs and different versification systems

from sqlalchemy.orm import Session
from typing import List, Dict, Tuple, Optional, Union
from models import AbstractVerse, Canon, Versification, CanonicalPosition, BiblicalText
import hashlib
import logging

logger = logging.getLogger(__name__)

class VerseResolutionService:
    """
    Service for resolving verses between different canonical and versification systems.
    Handles complex mappings like LXX/MT differences, merged/split verses, and 
    multi-canonical traditions (Protestant, Catholic, Ethiopian Orthodox).
    """
    
    def __init__(self, db: Session):
        self.db = db
        self._cache = {}  # Simple in-memory cache for performance
        
    def normalize_book_name(self, book: str) -> str:
        """Normalize book names for consistent matching across different systems."""
        # Basic normalization - can be extended for more complex mappings
        book = book.strip().lower()
        
        # Handle common variants
        book_mappings = {
            "1 samuel": "first_samuel",
            "2 samuel": "second_samuel",
            "1 kings": "first_kings",
            "2 kings": "second_kings",
            "1 chronicles": "first_chronicles",
            "2 chronicles": "second_chronicles",
            "song of solomon": "song_of_songs",
            "1 corinthians": "first_corinthians",
            "2 corinthians": "second_corinthians",
            "1 thessalonians": "first_thessalonians",
            "2 thessalonians": "second_thessalonians",
            "1 timothy": "first_timothy",
            "2 timothy": "second_timothy",
            "1 peter": "first_peter",
            "2 peter": "second_peter",
            "1 john": "first_john",
            "2 john": "second_john",
            "3 john": "third_john"
        }
        
        return book_mappings.get(book, book.replace(" ", "_"))

    def generate_canonical_key(self, book: str, chapter: int, verse: int) -> str:
        """
        Generate a canonical key for verse identification across traditions.
        Format: book.chapter.verse (e.g., "genesis.1.1", "meqabyan1.1.1")
        """
        normalized_book = self.normalize_book_name(book)
        return f"{normalized_book}.{chapter}.{verse}"
    
    def generate_content_hash(self, text: str) -> str:
        """Generate SHA256 hash of verse content for deduplication."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def map_to_abstract_id(self, canon_code: str, book: str, chapter: int, verse: int) -> Optional[int]:
        """
        Map a (canon, book, chapter, verse) reference to an abstract verse ID.
        
        Args:
            canon_code: Canon identifier (e.g., "PROT66", "ETH81")
            book: Book name
            chapter: Chapter number
            verse: Verse number
            
        Returns:
            Abstract verse ID if found, None otherwise
        """
        cache_key = f"{canon_code}:{book}:{chapter}:{verse}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            # Get the versification for this canon
            canon = self.db.query(Canon).filter(Canon.code == canon_code).first()
            if not canon:
                logger.warning(f"Canon not found: {canon_code}")
                return None
            
            # Get the default versification for this canon
            versification = self.db.query(Versification).filter(
                Versification.canon_id == canon.id,
                Versification.is_default == True
            ).first()
            
            if not versification:
                # Fallback to first versification for this canon
                versification = self.db.query(Versification).filter(
                    Versification.canon_id == canon.id
                ).first()
                
            if not versification:
                logger.warning(f"No versification found for canon: {canon_code}")
                return None
            
            # Find the canonical position
            position = self.db.query(CanonicalPosition).filter(
                CanonicalPosition.versification_id == versification.id,
                CanonicalPosition.book == book,
                CanonicalPosition.chapter_start == chapter,
                CanonicalPosition.verse_start == verse
            ).first()
            
            if position:
                abstract_id = position.abstract_verse_id
                self._cache[cache_key] = abstract_id
                return abstract_id
            
            logger.info(f"No abstract verse found for {canon_code} {book} {chapter}:{verse}")
            return None
            
        except Exception as e:
            logger.error(f"Error mapping to abstract ID: {e}")
            return None

    def resolve_from_abstract(
        self, 
        abstract_id: int, 
        versification_code: str
    ) -> List[Tuple[str, int, int, int, int]]:
        """
        Resolve an abstract verse ID to positions in a specific versification.
        
        Args:
            abstract_id: Abstract verse ID
            versification_code: Target versification (e.g., "MT", "LXX", "KJV")
            
        Returns:
            List of (book, chapter_start, verse_start, chapter_end, verse_end) tuples
            Multiple tuples handle cases where one abstract verse maps to multiple positions
        """
        try:
            # Get the target versification
            versification = self.db.query(Versification).filter(
                Versification.code == versification_code
            ).first()
            
            if not versification:
                logger.warning(f"Versification not found: {versification_code}")
                return []
            
            # Find all canonical positions for this abstract verse in this versification
            positions = self.db.query(CanonicalPosition).filter(
                CanonicalPosition.abstract_verse_id == abstract_id,
                CanonicalPosition.versification_id == versification.id
            ).all()
            
            results = []
            for pos in positions:
                results.append((
                    pos.book,
                    pos.chapter_start,
                    pos.verse_start,
                    pos.chapter_end or pos.chapter_start,
                    pos.verse_end or pos.verse_start
                ))
            
            return results
            
        except Exception as e:
            logger.error(f"Error resolving from abstract ID {abstract_id}: {e}")
            return []

    def find_or_create_abstract_verse(
        self, 
        book: str, 
        chapter: int, 
        verse: int, 
        text: Optional[str] = None
    ) -> AbstractVerse:
        """
        Find existing abstract verse or create new one for the given reference.
        
        Args:
            book: Book name
            chapter: Chapter number  
            verse: Verse number
            text: Optional verse text for content hashing
            
        Returns:
            AbstractVerse instance
        """
        canonical_key = self.generate_canonical_key(book, chapter, verse)
        
        # Try to find existing abstract verse
        existing = self.db.query(AbstractVerse).filter(
            AbstractVerse.canonical_key == canonical_key
        ).first()
        
        if existing:
            return existing
        
        # Create new abstract verse
        content_hash = None
        if text:
            content_hash = self.generate_content_hash(text)
        
        abstract_verse = AbstractVerse(
            canonical_key=canonical_key,
            content_hash=content_hash,
            notes={"created_from": f"{book} {chapter}:{verse}"}
        )
        
        self.db.add(abstract_verse)
        self.db.flush()  # Get the ID without committing
        
        return abstract_verse

    def create_canonical_position(
        self,
        abstract_verse: AbstractVerse,
        versification: Versification,
        book: str,
        chapter_start: int,
        verse_start: int,
        chapter_end: Optional[int] = None,
        verse_end: Optional[int] = None,
        position_type: str = "exact",
        confidence_score: float = 1.0,
        mapping_notes: Optional[str] = None
    ) -> CanonicalPosition:
        """
        Create a canonical position mapping for an abstract verse.
        
        Args:
            abstract_verse: The abstract verse
            versification: Target versification
            book: Book name
            chapter_start: Starting chapter
            verse_start: Starting verse
            chapter_end: Ending chapter (for ranges)
            verse_end: Ending verse (for ranges)
            position_type: Type of mapping (exact, split, merged, approximate)
            confidence_score: Confidence in this mapping (0.0 to 1.0)
            mapping_notes: Optional notes about this mapping
            
        Returns:
            CanonicalPosition instance
        """
        position = CanonicalPosition(
            abstract_verse_id=abstract_verse.id,
            versification_id=versification.id,
            book=book,
            chapter_start=chapter_start,
            verse_start=verse_start,
            chapter_end=chapter_end,
            verse_end=verse_end,
            position_type=position_type,
            confidence_score=confidence_score,
            mapping_notes=mapping_notes
        )
        
        self.db.add(position)
        return position

    def get_cross_versification_mappings(
        self, 
        book: str, 
        chapter: int, 
        verse: int,
        source_versification: str
    ) -> Dict[str, List[Tuple[str, int, int]]]:
        """
        Get mappings for a verse across all available versifications.
        
        Args:
            book: Book name
            chapter: Chapter number
            verse: Verse number
            source_versification: Source versification code
            
        Returns:
            Dictionary mapping versification codes to list of (book, chapter, verse) tuples
        """
        # First, find the abstract verse ID from the source
        canon = self.db.query(Canon).join(Versification).filter(
            Versification.code == source_versification
        ).first()
        
        if not canon:
            return {}
        
        abstract_id = self.map_to_abstract_id(canon.code, book, chapter, verse)
        if not abstract_id:
            return {}
        
        # Get all versifications
        versifications = self.db.query(Versification).all()
        
        mappings = {}
        for versification in versifications:
            positions = self.resolve_from_abstract(abstract_id, versification.code)
            if positions:
                mappings[versification.code] = [
                    (pos[0], pos[1], pos[2]) for pos in positions
                ]
        
        return mappings

    def handle_versification_differences(self) -> Dict[str, str]:
        """
        Get known versification differences for common edge cases.
        This can be extended to handle specific mappings like LXX vs MT differences.
        
        Returns:
            Dictionary of known mapping rules
        """
        return {
            "psalm_numbering": "LXX psalm numbering differs from MT by approximately 1 in Psalms 10-148",
            "daniel_additions": "LXX includes Susanna, Bel and Dragon not in MT",
            "esther_additions": "LXX includes additional passages not in MT",
            "jeremiah_order": "LXX has different chapter arrangement than MT",
            "ethiopian_canon": "Ethiopian tradition includes Meqabyan 1-3, Enoch, Jubilees, and other books"
        }

    def clear_cache(self):
        """Clear the resolution cache."""
        self._cache.clear()

def get_resolution_service(db: Session) -> VerseResolutionService:
    """Factory function to get a VerseResolutionService instance."""
    return VerseResolutionService(db)