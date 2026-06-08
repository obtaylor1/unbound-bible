#!/usr/bin/env python3
"""
Test Adam and Eve AI Integration
================================

Test script to verify that the AI can properly retrieve and use 
Adam and Eve content through the vector search service.
"""

import os
import sys
import asyncio
from typing import List, Dict, Any

# Add parent directories to Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)

# Import backend models and services
from database import SessionLocal
from models import BiblicalText, Translation
from vector_search import VectorSearchService

async def test_adameve_integration():
    """Test that Adam and Eve content is properly indexed and retrievable"""
    
    print("=" * 70)
    print("TESTING ADAM AND EVE AI INTEGRATION")
    print("=" * 70)
    
    # Initialize services
    vector_service = VectorSearchService()
    db = SessionLocal()
    
    try:
        # Test 1: Check that Adam and Eve content exists in database
        print("\n1. CHECKING DATABASE CONTENT...")
        print("-" * 40)
        
        adam_eve_texts = db.query(BiblicalText).filter(
            BiblicalText.book.like("Adam and Eve%")
        ).all()
        
        total_texts = len(adam_eve_texts)
        embedded_texts = len([t for t in adam_eve_texts if t.text_embedding is not None])
        
        print(f"Total Adam and Eve texts: {total_texts}")
        print(f"Texts with embeddings: {embedded_texts}")
        
        if total_texts == 0:
            print("❌ ERROR: No Adam and Eve texts found in database")
            return
        if embedded_texts == 0:
            print("❌ ERROR: No Adam and Eve texts have embeddings")
            return
        if embedded_texts < total_texts:
            print(f"⚠️  WARNING: Only {embedded_texts}/{total_texts} texts have embeddings")
        else:
            print("✅ All Adam and Eve texts have embeddings")
        
        # Test 2: Test semantic search for Adam and Eve content
        print("\n2. TESTING SEMANTIC SEARCH...")
        print("-" * 40)
        
        test_queries = [
            "Adam and Eve leaving the garden",
            "Satan tempting Adam",
            "Cave of Treasures",
            "Adam's sorrow and regret"
        ]
        
        for query in test_queries:
            print(f"\nSearching for: '{query}'")
            results = await vector_service.semantic_search(
                db=db, 
                query=query, 
                limit=3,
                translation_filters=["ADAMEVE"]  # Only search Adam and Eve content
            )
            
            if results:
                print(f"  ✅ Found {len(results)} results:")
                for result in results:
                    print(f"    • {result['reference']}: {result['text'][:100]}...")
                    print(f"      Similarity: {result['similarity_score']:.3f}")
            else:
                print(f"  ❌ No results found")
        
        # Test 3: Test general search that might include Adam and Eve
        print("\n3. TESTING GENERAL SEMANTIC SEARCH...")
        print("-" * 40)
        
        general_queries = [
            "the first man and woman in paradise",
            "disobedience and banishment from Eden"
        ]
        
        for query in general_queries:
            print(f"\nSearching for: '{query}' (all translations)")
            results = await vector_service.semantic_search(
                db=db, 
                query=query, 
                limit=5
            )
            
            adam_eve_results = [r for r in results if "Adam and Eve" in r['book']]
            
            if adam_eve_results:
                print(f"  ✅ Found {len(adam_eve_results)} Adam and Eve results:")
                for result in adam_eve_results:
                    print(f"    • {result['reference']}: {result['text'][:80]}...")
                    print(f"      Similarity: {result['similarity_score']:.3f}")
            else:
                print(f"  ⚠️  No Adam and Eve results found in general search")
        
        # Test 4: Sample some actual content
        print("\n4. SAMPLE ADAM AND EVE CONTENT...")
        print("-" * 40)
        
        sample_texts = adam_eve_texts[:3]  # First 3 texts
        for text in sample_texts:
            print(f"\n{text.book} {text.chapter}:{text.verse}")
            print(f"Text: {text.text[:200]}...")
            embedding_status = "✅ Has embedding" if text.text_embedding is not None else "❌ No embedding"
            print(f"Status: {embedding_status}")
        
        print("\n" + "=" * 70)
        print("INTEGRATION TEST COMPLETED")
        print("=" * 70)
        
        if embedded_texts == total_texts and embedded_texts > 0:
            print("✅ SUCCESS: Adam and Eve content is fully integrated and ready for AI use")
            print("\nThe AI Study Assistant can now:")
            print("• Answer questions about Adam and Eve")
            print("• Find relevant passages about Satan's temptations")
            print("• Reference the Cave of Treasures")
            print("• Discuss Adam's trials and experiences")
        else:
            print("⚠️ PARTIAL SUCCESS: Integration has issues that need addressing")
        
    except Exception as e:
        print(f"❌ ERROR during testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_adameve_integration())