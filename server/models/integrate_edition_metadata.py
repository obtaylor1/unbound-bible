#!/usr/bin/env python3
"""
Integration script for EditionMetadata model.
Creates the edition_metadata table in the PostgreSQL database.
"""

import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend directory to path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
sys.path.insert(0, backend_path)

try:
    from database import DATABASE_URL, engine
    from edition_metadata import EditionMetadata, Base, create_sample_editions
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)


def create_edition_metadata_table():
    """Create the edition_metadata table in the database"""
    
    print("Creating EditionMetadata table...")
    
    try:
        # Create the table
        EditionMetadata.__table__.create(engine, checkfirst=True)
        print("✅ EditionMetadata table created successfully")
        
        # Verify table creation  
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_name = 'edition_metadata'"))
            if result.fetchone():
                print("✅ Table 'edition_metadata' verified in database")
            else:
                print("❌ Table verification failed")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        return False


def populate_sample_data():
    """Populate the table with sample edition metadata"""
    
    print("\nPopulating sample edition metadata...")
    
    try:
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        # Create sample editions
        sample_editions = create_sample_editions()
        
        # Add sample data
        for edition in sample_editions:
            # Check if already exists
            existing = session.query(EditionMetadata).filter(
                EditionMetadata.work_id == edition.work_id,
                EditionMetadata.language_script == edition.language_script
            ).first()
            
            if not existing:
                session.add(edition)
            else:
                print(f"  - Skipping {edition.work_id} ({edition.language_script}) - already exists")
        
        session.commit()
        
        # Count total entries
        total_count = session.query(EditionMetadata).count()
        print(f"✅ Sample data populated. Total editions: {total_count}")
        
        session.close()
        return True
        
    except Exception as e:
        print(f"❌ Error populating sample data: {e}")
        return False


def verify_integration():
    """Verify the EditionMetadata integration"""
    
    print("\nVerifying EditionMetadata integration...")
    
    try:
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        # Test queries
        print("\n📊 Database Verification:")
        
        # Count by canonical tradition
        protestantCount = session.query(EditionMetadata).filter(
            EditionMetadata.canon_tags.contains(['protestant'])
        ).count()
        print(f"  - Protestant editions: {protestantCount}")
        
        ethiopianCount = session.query(EditionMetadata).filter(
            EditionMetadata.canon_tags.contains(['ethiopian'])
        ).count()
        print(f"  - Ethiopian editions: {ethiopianCount}")
        
        # Count by language
        hebrewCount = session.query(EditionMetadata).filter(
            EditionMetadata.language_script.like('%Hebrew%')
        ).count()
        print(f"  - Hebrew editions: {hebrewCount}")
        
        greekCount = session.query(EditionMetadata).filter(
            EditionMetadata.language_script.like('%Greek%')
        ).count()
        print(f"  - Greek editions: {greekCount}")
        
        # Show morphological analysis availability
        morphCount = session.query(EditionMetadata).filter(
            EditionMetadata.has_morph == True
        ).count()
        print(f"  - Editions with morphological analysis: {morphCount}")
        
        # Show ingest status distribution
        from edition_metadata import IngestStatusEnum
        for status in IngestStatusEnum:
            count = session.query(EditionMetadata).filter(
                EditionMetadata.ingest_status == status
            ).count()
            print(f"  - {status.value}: {count} editions")
        
        session.close()
        print("✅ Integration verification complete")
        return True
        
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        return False


def main():
    """Main integration process"""
    
    print("=== EditionMetadata Database Integration ===")
    print("Creating and populating edition metadata tracking table")
    print()
    
    # Step 1: Create table
    if not create_edition_metadata_table():
        print("❌ Failed to create table")
        return False
    
    # Step 2: Populate sample data
    if not populate_sample_data():
        print("❌ Failed to populate sample data") 
        return False
    
    # Step 3: Verify integration
    if not verify_integration():
        print("❌ Failed integration verification")
        return False
    
    print("\n✅ EditionMetadata integration completed successfully!")
    print()
    print("Next steps:")
    print("1. Use the EditionMetadata model to track biblical editions")
    print("2. Integrate with existing ingestion scripts")
    print("3. Add API endpoints for edition metadata queries")
    
    return True


if __name__ == "__main__":
    main()