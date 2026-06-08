#!/usr/bin/env python3
"""
Master Data Ingestion Script
Runs all data ingestion scripts in the correct order for the Liberation Bible Project.
"""

import logging
import sys
import os
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_ingestion_script(script_name, description):
    """Run a single ingestion script"""
    logger.info(f"=" * 60)
    logger.info(f"STARTING: {description}")
    logger.info(f"Script: {script_name}")
    logger.info(f"=" * 60)
    
    try:
        # Import and run the script
        if script_name == 'ingest_kjv':
            from ingest_kjv import main as kjv_main
            kjv_main()
        elif script_name == 'ingest_geography':
            from ingest_geography import main as geo_main
            geo_main()
        elif script_name == 'ingest_strongs':
            from ingest_strongs import main as strongs_main
            strongs_main()
            
        logger.info(f"✅ COMPLETED: {description}")
        return True
        
    except Exception as e:
        logger.error(f"❌ FAILED: {description}")
        logger.error(f"Error: {str(e)}")
        return False

def main():
    """Run all data ingestion processes"""
    logger.info("🚀 Starting Liberation Bible Project Data Ingestion")
    logger.info("This will populate the database with public domain biblical texts and related data")
    
    # Define ingestion order - KJV first, then supporting data
    ingestion_tasks = [
        ('ingest_kjv', 'King James Version Bible Text Import'),
        ('ingest_strongs', 'Strong\'s Exhaustive Concordance Lexicon Import'),
        ('ingest_geography', 'Biblical Geographical Locations Import')
    ]
    
    success_count = 0
    total_tasks = len(ingestion_tasks)
    
    # Run each ingestion task
    for script, description in ingestion_tasks:
        if run_ingestion_script(script, description):
            success_count += 1
        else:
            logger.error(f"Failed to complete {description}")
            # Continue with other tasks even if one fails
    
    # Summary
    logger.info("=" * 60)
    logger.info("📊 DATA INGESTION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total tasks: {total_tasks}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {total_tasks - success_count}")
    
    if success_count == total_tasks:
        logger.info("🎉 ALL DATA INGESTION TASKS COMPLETED SUCCESSFULLY!")
        logger.info("The Liberation Bible Project database is now populated with:")
        logger.info("  • King James Version (KJV) Bible text")
        logger.info("  • Strong's Concordance lexical data")
        logger.info("  • Biblical geographical locations")
        logger.info("  • Translation metadata")
    else:
        logger.warning("⚠️  Some data ingestion tasks failed. Check logs above for details.")
    
    # Additional setup notes
    logger.info("\n📋 Next Steps:")
    logger.info("  1. Masoretic Text (Hebrew OT) - requires separate download")
    logger.info("  2. Textus Receptus (Greek NT) - requires separate download") 
    logger.info("  3. Ethiopian Canon - placeholder JSON created, awaits source texts")
    logger.info("  4. Link lexical entries to biblical text verses")
    
    logger.info("\n🔗 Database is ready for:")
    logger.info("  • Biblical text searches and analysis")
    logger.info("  • Geographical mapping of biblical locations")
    logger.info("  • Strong's concordance word studies")
    logger.info("  • Historical context integration")

if __name__ == "__main__":
    main()