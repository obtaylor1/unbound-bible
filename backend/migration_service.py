# Liberation Bible Project - Migration Service
# Handles data migration for Abstract Verse ID architecture

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Set, Tuple, Optional
from models import (
    BiblicalText, AbstractVerse, Canon, Versification, CanonicalPosition, 
    CrossReference, Base
)
from database import engine
from resolve_service import VerseResolutionService
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class MigrationService:
    """
    Service for migrating existing biblical data to the new Abstract Verse ID architecture.
    Handles backfilling abstract verses, canonical positions, and updating cross-references.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.resolver = VerseResolutionService(db)
        
    def create_database_tables(self):
        """Create all new database tables for the Abstract Verse ID architecture."""
        try:
            logger.info("Creating database tables for Abstract Verse ID architecture...")
            # Use checkfirst=True to avoid errors if tables already exist
            Base.metadata.create_all(bind=engine, checkfirst=True)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.warning(f"Tables may already exist (this is normal): {e}")
            # Continue with migration even if table creation fails - tables might already exist

    def seed_default_canons(self) -> Dict[str, Canon]:
        """
        Create default biblical canons (Protestant, Catholic, Ethiopian Orthodox).
        
        Returns:
            Dictionary mapping canon codes to Canon objects
        """
        canons_data = [
            {
                "code": "PROT66",
                "name": "Protestant Canon",
                "description": "66-book Protestant biblical canon established during the Reformation",
                "book_count": 66,
                "language_tradition": "Hebrew/Greek",
                "historical_period": "16th century CE",
                "authority": "Protestant Reformers"
            },
            {
                "code": "CATH73", 
                "name": "Catholic Canon",
                "description": "73-book Catholic biblical canon defined by the Council of Trent",
                "book_count": 73,
                "language_tradition": "Hebrew/Greek/Latin",
                "historical_period": "16th century CE",
                "authority": "Council of Trent (1546 CE)"
            },
            {
                "code": "ETH81",
                "name": "Ethiopian Orthodox Canon", 
                "description": "81-book Ethiopian Orthodox Tewahedo canon including Meqabyan, Enoch, Jubilees",
                "book_count": 81,
                "language_tradition": "Ge'ez",
                "historical_period": "4th-6th century CE",
                "authority": "Ethiopian Orthodox Tewahedo Church"
            }
        ]
        
        created_canons = {}
        
        for canon_data in canons_data:
            # Check if canon already exists
            existing = self.db.query(Canon).filter(Canon.code == canon_data["code"]).first()
            if existing:
                created_canons[canon_data["code"]] = existing
                logger.info(f"Canon {canon_data['code']} already exists")
                continue
                
            canon = Canon(**canon_data)
            self.db.add(canon)
            self.db.flush()
            created_canons[canon_data["code"]] = canon
            logger.info(f"Created canon: {canon_data['name']}")
        
        return created_canons

    def seed_default_versifications(self, canons: Dict[str, Canon]) -> Dict[str, Versification]:
        """
        Create default versification systems.
        
        Args:
            canons: Dictionary of canon objects
            
        Returns:
            Dictionary mapping versification codes to Versification objects
        """
        versifications_data = [
            {
                "code": "KJV",
                "name": "King James Version",
                "canon_code": "PROT66",
                "description": "Traditional Protestant versification based on Textus Receptus",
                "source_text": "Textus Receptus / Masoretic Text",
                "manuscript_tradition": "Byzantine",
                "year_established": 1611,
                "is_default": True
            },
            {
                "code": "MT",
                "name": "Masoretic Text",
                "canon_code": "PROT66", 
                "description": "Hebrew Masoretic Text versification",
                "source_text": "Masoretic Text",
                "manuscript_tradition": "Masoretic",
                "year_established": 1000,
                "is_default": False
            },
            {
                "code": "LXX",
                "name": "Septuagint",
                "canon_code": "CATH73",
                "description": "Greek Septuagint versification with deuterocanonical books",
                "source_text": "Septuagint",
                "manuscript_tradition": "Alexandrian",
                "year_established": 250,
                "is_default": True
            },
            {
                "code": "VUL",
                "name": "Vulgate",
                "canon_code": "CATH73",
                "description": "Latin Vulgate versification",
                "source_text": "Latin Vulgate",
                "manuscript_tradition": "Latin",
                "year_established": 405,
                "is_default": False
            },
            {
                "code": "ETH",
                "name": "Ethiopian Orthodox",
                "canon_code": "ETH81",
                "description": "Ethiopian Orthodox Tewahedo versification with unique books",
                "source_text": "Ge'ez manuscripts",
                "manuscript_tradition": "Ethiopian",
                "year_established": 500,
                "is_default": True
            }
        ]
        
        created_versifications = {}
        
        for vers_data in versifications_data:
            # Check if versification already exists
            existing = self.db.query(Versification).filter(Versification.code == vers_data["code"]).first()
            if existing:
                created_versifications[vers_data["code"]] = existing
                logger.info(f"Versification {vers_data['code']} already exists")
                continue
            
            canon_code = vers_data.pop("canon_code")
            canon = canons.get(canon_code)
            if not canon:
                logger.error(f"Canon {canon_code} not found for versification {vers_data['code']}")
                continue
                
            versification = Versification(
                canon_id=canon.id,
                **vers_data
            )
            self.db.add(versification)
            self.db.flush()
            created_versifications[vers_data["code"]] = versification
            logger.info(f"Created versification: {vers_data['name']}")
        
        return created_versifications

    def get_unique_verse_references(self) -> List[Tuple[str, int, int]]:
        """
        Get all unique (book, chapter, verse) combinations from existing biblical texts.
        
        Returns:
            List of (book, chapter, verse) tuples
        """
        try:
            query = text("""
                SELECT DISTINCT book, chapter, verse 
                FROM biblical_texts 
                ORDER BY book, chapter, verse
            """)
            
            result = self.db.execute(query)
            references = [(row.book, row.chapter, row.verse) for row in result]
            logger.info(f"Found {len(references)} unique verse references")
            return references
            
        except Exception as e:
            logger.error(f"Error getting unique verse references: {e}")
            return []

    def backfill_abstract_verses(self) -> Dict[Tuple[str, int, int], int]:
        """
        Create AbstractVerse entries for all unique (book, chapter, verse) combinations.
        
        Returns:
            Dictionary mapping (book, chapter, verse) to abstract_verse_id
        """
        logger.info("Starting abstract verse backfill...")
        
        unique_references = self.get_unique_verse_references()
        abstract_verse_map = {}
        
        for book, chapter, verse in unique_references:
            try:
                # Get a sample text for content hashing (use KJV if available)
                sample_text = self.db.query(BiblicalText).filter(
                    BiblicalText.book == book,
                    BiblicalText.chapter == chapter,
                    BiblicalText.verse == verse,
                    BiblicalText.translation == "KJV"
                ).first()
                
                text_content = sample_text.text if sample_text else None
                
                # Create or find abstract verse
                abstract_verse = self.resolver.find_or_create_abstract_verse(
                    book, chapter, verse, text_content
                )
                
                abstract_verse_map[(book, chapter, verse)] = abstract_verse.id
                
            except Exception as e:
                logger.error(f"Error creating abstract verse for {book} {chapter}:{verse}: {e}")
                continue
        
        self.db.commit()
        logger.info(f"Created {len(abstract_verse_map)} abstract verses")
        return abstract_verse_map

    def backfill_canonical_positions(
        self, 
        versifications: Dict[str, Versification],
        abstract_verse_map: Dict[Tuple[str, int, int], int]
    ):
        """
        Create CanonicalPosition entries linking abstract verses to versifications.
        
        Args:
            versifications: Dictionary of versification objects
            abstract_verse_map: Mapping of verse references to abstract IDs
        """
        logger.info("Starting canonical position backfill...")
        
        # For now, create positions for KJV versification (can be extended later)
        kjv_versification = versifications.get("KJV")
        if not kjv_versification:
            logger.error("KJV versification not found")
            return
        
        position_count = 0
        
        for (book, chapter, verse), abstract_id in abstract_verse_map.items():
            try:
                # Check if position already exists
                existing = self.db.query(CanonicalPosition).filter(
                    CanonicalPosition.abstract_verse_id == abstract_id,
                    CanonicalPosition.versification_id == kjv_versification.id,
                    CanonicalPosition.book == book,
                    CanonicalPosition.chapter_start == chapter,
                    CanonicalPosition.verse_start == verse
                ).first()
                
                if existing:
                    continue
                
                # Create canonical position
                abstract_verse = self.db.query(AbstractVerse).get(abstract_id)
                if abstract_verse:
                    self.resolver.create_canonical_position(
                        abstract_verse=abstract_verse,
                        versification=kjv_versification,
                        book=book,
                        chapter_start=chapter,
                        verse_start=verse,
                        position_type="exact",
                        confidence_score=1.0,
                        mapping_notes="Initial migration from existing data"
                    )
                    position_count += 1
                
            except Exception as e:
                logger.error(f"Error creating canonical position for {book} {chapter}:{verse}: {e}")
                continue
        
        self.db.commit()
        logger.info(f"Created {position_count} canonical positions")

    def link_biblical_texts_to_abstract_verses(self, abstract_verse_map: Dict[Tuple[str, int, int], int]):
        """
        Update BiblicalText records to link them to their corresponding abstract verses.
        
        Args:
            abstract_verse_map: Mapping of verse references to abstract IDs
        """
        logger.info("Linking biblical texts to abstract verses...")
        
        updated_count = 0
        
        try:
            # Update in batches for better performance
            batch_size = 1000
            
            for i, ((book, chapter, verse), abstract_id) in enumerate(abstract_verse_map.items()):
                # Update all biblical texts for this verse reference
                result = self.db.execute(
                    text("""
                        UPDATE biblical_texts 
                        SET abstract_verse_id = :abstract_id 
                        WHERE book = :book AND chapter = :chapter AND verse = :verse
                          AND abstract_verse_id IS NULL
                    """),
                    {
                        "abstract_id": abstract_id,
                        "book": book,
                        "chapter": chapter,
                        "verse": verse
                    }
                )
                
                updated_count += result.rowcount
                
                # Commit in batches
                if (i + 1) % batch_size == 0:
                    self.db.commit()
                    logger.info(f"Processed {i + 1} verse references...")
            
            self.db.commit()
            logger.info(f"Linked {updated_count} biblical texts to abstract verses")
            
        except Exception as e:
            logger.error(f"Error linking biblical texts to abstract verses: {e}")
            self.db.rollback()
            raise

    def update_cross_references_with_abstract_ids(self):
        """
        Update existing CrossReference records to include abstract verse IDs.
        This maintains backward compatibility while enabling future-proof cross-references.
        """
        logger.info("Updating cross-references with abstract verse IDs...")
        
        try:
            # Get all cross-references that don't have abstract IDs yet
            cross_refs = self.db.query(CrossReference).filter(
                CrossReference.source_abstract_id.is_(None)
            ).all()
            
            updated_count = 0
            
            for cross_ref in cross_refs:
                # Get the abstract verse IDs for source and target texts
                source_text = cross_ref.source_text
                target_text = cross_ref.target_text
                
                if source_text and source_text.abstract_verse_id:
                    cross_ref.source_abstract_id = source_text.abstract_verse_id
                
                if target_text and target_text.abstract_verse_id:
                    cross_ref.target_abstract_id = target_text.abstract_verse_id
                
                if cross_ref.source_abstract_id or cross_ref.target_abstract_id:
                    updated_count += 1
            
            self.db.commit()
            logger.info(f"Updated {updated_count} cross-references with abstract verse IDs")
            
        except Exception as e:
            logger.error(f"Error updating cross-references: {e}")
            self.db.rollback()
            raise

    def run_full_migration(self) -> bool:
        """
        Run the complete migration process for Abstract Verse ID architecture.
        
        Returns:
            True if migration completed successfully, False otherwise
        """
        try:
            logger.info("Starting full Abstract Verse ID migration...")
            start_time = datetime.now()
            
            # Step 1: Create database tables
            self.create_database_tables()
            
            # Step 2: Seed default canons
            canons = self.seed_default_canons()
            
            # Step 3: Seed default versifications
            versifications = self.seed_default_versifications(canons)
            
            # Step 4: Backfill abstract verses
            abstract_verse_map = self.backfill_abstract_verses()
            
            # Step 5: Create canonical positions
            self.backfill_canonical_positions(versifications, abstract_verse_map)
            
            # Step 6: Link biblical texts to abstract verses
            self.link_biblical_texts_to_abstract_verses(abstract_verse_map)
            
            # Step 7: Update cross-references with abstract IDs
            self.update_cross_references_with_abstract_ids()
            
            end_time = datetime.now()
            duration = end_time - start_time
            
            logger.info(f"Migration completed successfully in {duration}")
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            self.db.rollback()
            return False

def get_migration_service(db: Session) -> MigrationService:
    """Factory function to get a MigrationService instance."""
    return MigrationService(db)