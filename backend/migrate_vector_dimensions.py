#!/usr/bin/env python3
"""
Migration script to fix vector dimension mismatch issue.
Updates text_embedding column from 384D to 1536D to match text-embedding-ada-002.
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database import DATABASE_URL

def migrate_vector_dimensions():
    """
    Migrate vector column from 384 dimensions to 1536 dimensions.
    This fixes the critical dimension mismatch causing RAG query timeouts.
    """
    
    print("🔄 Starting vector dimension migration...")
    
    # Create engine
    engine = create_engine(DATABASE_URL)
    
    try:
        with engine.begin() as conn:
            print("📊 Checking current vector column...")
            
            # Check if vector column exists and get its current dimensions
            result = conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'biblical_texts' AND column_name = 'text_embedding'
            """))
            
            column_info = result.fetchone()
            if column_info:
                print(f"✅ Found existing vector column: {column_info}")
            else:
                print("❌ No text_embedding column found!")
                return False
            
            print("🗑️  Dropping existing vector index...")
            # Drop the existing vector index if it exists
            conn.execute(text("""
                DROP INDEX IF EXISTS ix_biblical_texts_embedding;
            """))
            
            print("🗑️  Dropping existing vector column...")
            # Drop the existing vector column
            conn.execute(text("""
                ALTER TABLE biblical_texts DROP COLUMN IF EXISTS text_embedding;
            """))
            
            print("➕ Adding new vector column with 1536 dimensions...")
            # Add new vector column with correct dimensions
            conn.execute(text("""
                ALTER TABLE biblical_texts 
                ADD COLUMN text_embedding vector(1536);
            """))
            
            print("🔍 Creating new vector index...")
            # Create new vector index optimized for 1536D vectors
            conn.execute(text("""
                CREATE INDEX ix_biblical_texts_embedding 
                ON biblical_texts 
                USING ivfflat (text_embedding vector_cosine_ops) 
                WITH (lists = 100);
            """))
            
            print("✅ Vector dimension migration completed successfully!")
            print("📝 Summary:")
            print("   - Dropped old 384D vector column")  
            print("   - Added new 1536D vector column")
            print("   - Recreated vector index for cosine similarity")
            print("   - Ready for text-embedding-ada-002 (1536D) vectors")
            
            return True
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    success = migrate_vector_dimensions()
    sys.exit(0 if success else 1)