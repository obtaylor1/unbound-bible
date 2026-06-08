#!/usr/bin/env python3
"""
Generate Vector Embeddings for Adam and Eve Content
================================================================

Simple script to add vector embeddings to Adam and Eve biblical texts
for AI chat functionality and semantic search.

Works around SQL parameter binding issues with vector types by using
direct connection execute instead of SQLAlchemy text() parameters.
"""

import os
import sys
import asyncio
import psycopg2
from typing import List, Dict, Optional

# Add parent directories to Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)

# Import backend models and services
from database import SessionLocal
from models import BiblicalText, Translation
from vector_search import VectorSearchService

def connect_direct_to_postgres():
    """Get direct psycopg2 connection for vector operations"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    return psycopg2.connect(database_url)

async def generate_embeddings_for_adam_eve():
    """Generate embeddings for Adam and Eve content"""
    
    print("=" * 70)
    print("GENERATING VECTOR EMBEDDINGS FOR ADAM AND EVE CONTENT")
    print("=" * 70)
    
    # Initialize services
    vector_service = VectorSearchService()
    db = SessionLocal()
    
    try:
        # Get Adam and Eve translation ID
        translation = db.query(Translation).filter(
            Translation.code == "ADAMEVE"
        ).first()
        
        if not translation:
            print("Error: Adam and Eve translation not found. Run ingest_adam_eve.py first.")
            return
        
        print(f"Found Adam and Eve translation (ID: {translation.id})")
        
        # Get biblical texts without embeddings
        texts_without_embeddings = db.query(BiblicalText).filter(
            BiblicalText.translation_id == translation.id,
            BiblicalText.text_embedding.is_(None)
        ).all()
        
        total_texts = len(texts_without_embeddings)
        print(f"Found {total_texts} Adam and Eve texts needing embeddings")
        
        if total_texts == 0:
            print("All Adam and Eve texts already have embeddings!")
            return
        
        # Get direct database connection for vector operations
        conn = connect_direct_to_postgres()
        cursor = conn.cursor()
        
        processed = 0
        for text in texts_without_embeddings:
            try:
                # Create embedding text with context
                embedding_text = f"{text.book} {text.chapter}:{text.verse} - {text.text[:500]}"
                
                print(f"Generating embedding for {text.book} {text.chapter}:{text.verse}...")
                embedding = await vector_service.generate_embedding(embedding_text)
                
                if embedding and len(embedding) == 1536:
                    # Convert embedding to PostgreSQL vector format
                    embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                    
                    # Use direct SQL execution to avoid parameter binding issues
                    cursor.execute(
                        "UPDATE biblical_texts SET text_embedding = %s::vector WHERE id = %s",
                        (embedding_str, text.id)
                    )
                    
                    processed += 1
                    print(f"  ✅ Embedded successfully ({processed}/{total_texts})")
                else:
                    print(f"  ❌ Invalid embedding generated")
                
                # Commit every 5 records to avoid losing work
                if processed % 5 == 0:
                    conn.commit()
                    print(f"  💾 Progress saved: {processed}/{total_texts}")
                    
            except Exception as e:
                print(f"  ❌ Error: {e}")
                conn.rollback()
                continue
        
        # Final commit
        conn.commit()
        print(f"\n✅ Successfully generated {processed} embeddings")
        
        # Close connections
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        db.close()
    
    print("\n" + "=" * 70)
    print("EMBEDDING GENERATION COMPLETED")
    print("=" * 70)
    print("Adam and Eve content is now available for:")
    print("• AI Study Assistant queries")
    print("• Semantic search")
    print("• Similar passage discovery")
    print("• Thematic content exploration")

if __name__ == "__main__":
    asyncio.run(generate_embeddings_for_adam_eve())