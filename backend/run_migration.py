#!/usr/bin/env python3
# Liberation Bible Project - Abstract Verse ID Migration Script
# Run this script to migrate existing data to the new architecture

import sys
import os
import logging
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db, DATABASE_URL
from migration_service import get_migration_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main migration entry point."""
    logger.info("Starting Abstract Verse ID Migration...")
    
    try:
        # Create database engine and session
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        # Get database session
        db = SessionLocal()
        
        try:
            # Create migration service and run full migration
            migration_service = get_migration_service(db)
            
            if migration_service.run_full_migration():
                logger.info("Migration completed successfully!")
                print("\n" + "="*60)
                print("✅ ABSTRACT VERSE ID MIGRATION SUCCESSFUL")
                print("="*60)
                print("\nNew Features Available:")
                print("• Abstract verse IDs for canon-independent references")
                print("• Support for Protestant, Catholic, Ethiopian Orthodox canons")
                print("• Multiple versification systems (KJV, MT, LXX, Vulgate, Ethiopian)")
                print("• Edition-agnostic cross-references")
                print("• Foundation for handling verse numbering differences")
                print("\nBackward Compatibility:")
                print("• All existing API endpoints continue to work")
                print("• Original BiblicalText records preserved")
                print("• Legacy cross-references maintained")
                print("="*60)
                return True
            else:
                logger.error("Migration failed!")
                print("\n" + "="*60)
                print("❌ MIGRATION FAILED")
                print("="*60)
                print("Check migration.log for detailed error information.")
                return False
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Critical migration error: {e}")
        print(f"\n❌ CRITICAL ERROR: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)