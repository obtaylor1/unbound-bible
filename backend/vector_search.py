# Liberation Bible Project - Vector Search Service
# Research-Grade Semantic Search with pgvector

import os
import openai
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from models import BiblicalText, Translation
from database import get_db

# Initialize OpenAI client using environment variable
client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

class VectorSearchService:
    """Research-grade semantic search service for biblical texts"""
    
    def __init__(self):
        self.embedding_model = "text-embedding-ada-002"  # 1536 dimensions - match existing data
        self.embedding_dim = 1536
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate vector embedding for text using OpenAI"""
        try:
            response = client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return [0.0] * self.embedding_dim
    
    async def populate_embeddings(self, db: Session, batch_size: int = 100):
        """Populate embeddings for all biblical texts without embeddings"""
        texts_without_embeddings = db.query(BiblicalText).filter(
            BiblicalText.text_embedding.is_(None)
        ).limit(batch_size).all()
        
        for text in texts_without_embeddings:
            try:
                # Create embedding text with context
                embedding_text = f"{text.book} {text.chapter}:{text.verse} - {text.text}"
                embedding = await self.generate_embedding(embedding_text)
                
                # Update text with embedding using proper pgvector format
                # Convert embedding to proper vector format for PostgreSQL
                embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                db.execute(
                    text("UPDATE biblical_texts SET text_embedding = :embedding::vector WHERE id = :text_id"),
                    {"embedding": embedding_str, "text_id": text.id}
                )
                
                print(f"Generated embedding for {text.book} {text.chapter}:{text.verse}")
                
            except Exception as e:
                print(f"Error processing {text.book} {text.chapter}:{text.verse}: {e}")
                continue
        
        db.commit()
        return len(texts_without_embeddings)
    
    async def semantic_search(
        self, 
        db: Session, 
        query: str, 
        limit: int = 10,
        similarity_threshold: float = 0.7,
        translation_filters: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search on biblical texts
        
        Args:
            query: Natural language query (e.g., "where is Cush referenced poetically?")
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score (0.0 to 1.0)
            translation_filters: List of translation codes to filter by
        
        Returns:
            List of matching verses with similarity scores and metadata
        """
        try:
            # Generate embedding for search query
            query_embedding = await self.generate_embedding(query)
            query_embedding_str = f"[{','.join(map(str, query_embedding))}]"
            
            # Build SQL query with direct vector string substitution to avoid parameter binding issues
            translation_filter_sql = ""
            if translation_filters:
                # Safely format translation filters for SQL
                formatted_filters = "'" + "','".join(translation_filters) + "'"
                translation_filter_sql = f"AND bt.translation IN ({formatted_filters})"
            
            sql_query_str = f"""
                SELECT 
                    bt.id,
                    bt.book,
                    bt.chapter,
                    bt.verse,
                    bt.text,
                    bt.translation,
                    t.name as translation_name,
                    1 - (bt.text_embedding <=> '{query_embedding_str}'::vector) as similarity_score
                FROM biblical_texts bt
                LEFT JOIN translations t ON bt.translation_id = t.id
                WHERE bt.text_embedding IS NOT NULL
                AND 1 - (bt.text_embedding <=> '{query_embedding_str}'::vector) >= {similarity_threshold}
                {translation_filter_sql}
                ORDER BY bt.text_embedding <=> '{query_embedding_str}'::vector
                LIMIT {limit}
            """
            
            result = db.execute(text(sql_query_str))
            rows = result.fetchall()
            
            # Format results with rich metadata
            results = []
            for row in rows:
                results.append({
                    'id': row.id,
                    'reference': f"{row.book} {row.chapter}:{row.verse}",
                    'book': row.book,
                    'chapter': row.chapter,
                    'verse': row.verse,
                    'text': row.text,
                    'translation': row.translation,
                    'translation_name': row.translation_name,
                    'similarity_score': float(row.similarity_score),
                    'search_query': query
                })
            
            return results
            
        except Exception as e:
            print(f"Error in semantic search: {e}")
            return []
    
    async def find_similar_passages(
        self, 
        db: Session, 
        reference_text_id: int, 
        limit: int = 5,
        exclude_same_book: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Find passages similar to a given biblical text
        
        Args:
            reference_text_id: ID of the biblical text to find similar passages for
            limit: Maximum number of similar passages to return
            exclude_same_book: Whether to exclude passages from the same book
        
        Returns:
            List of similar passages with similarity scores
        """
        try:
            # Get the reference text
            reference_text = db.query(BiblicalText).filter(
                BiblicalText.id == reference_text_id
            ).first()
            
            if not reference_text or reference_text.text_embedding is None:
                return []
            
            # Build similarity search query using direct string substitution
            ref_embedding = reference_text.text_embedding
            if isinstance(ref_embedding, list):
                ref_embedding_str = f"[{','.join(map(str, ref_embedding))}]"
            else:
                # If already a string, use it directly
                ref_embedding_str = str(ref_embedding)
            
            book_filter_sql = ""
            if exclude_same_book:
                book_filter_sql = f"AND bt.book != '{reference_text.book}'"
            
            sql_query_str = f"""
                SELECT 
                    bt.id,
                    bt.book,
                    bt.chapter,
                    bt.verse,
                    bt.text,
                    bt.translation,
                    t.name as translation_name,
                    1 - (bt.text_embedding <=> '{ref_embedding_str}'::vector) as similarity_score
                FROM biblical_texts bt
                LEFT JOIN translations t ON bt.translation_id = t.id
                WHERE bt.text_embedding IS NOT NULL
                AND bt.id != {reference_text_id}
                {book_filter_sql}
                ORDER BY bt.text_embedding <=> '{ref_embedding_str}'::vector
                LIMIT {limit}
            """
            
            result = db.execute(text(sql_query_str))
            rows = result.fetchall()
            
            # Format results
            results = []
            for row in rows:
                results.append({
                    'id': row.id,
                    'reference': f"{row.book} {row.chapter}:{row.verse}",
                    'book': row.book,
                    'chapter': row.chapter,
                    'verse': row.verse,
                    'text': row.text,
                    'translation': row.translation,
                    'translation_name': row.translation_name,
                    'similarity_score': float(row.similarity_score),
                    'reference_text': f"{reference_text.book} {reference_text.chapter}:{reference_text.verse}"
                })
            
            return results
            
        except Exception as e:
            print(f"Error finding similar passages: {e}")
            return []
    
    async def thematic_search(
        self, 
        db: Session, 
        themes: List[str], 
        limit: int = 20
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search for biblical texts by themes using semantic search
        
        Args:
            themes: List of thematic keywords or concepts
            limit: Maximum results per theme
        
        Returns:
            Dictionary mapping themes to relevant passages
        """
        results = {}
        
        for theme in themes:
            # Create thematic query
            thematic_queries = [
                f"passages about {theme}",
                f"biblical references to {theme}",
                f"scripture mentioning {theme}"
            ]
            
            theme_results = []
            for query in thematic_queries:
                search_results = await self.semantic_search(
                    db, query, limit=limit//len(thematic_queries)
                )
                theme_results.extend(search_results)
            
            # Remove duplicates and sort by similarity
            seen_ids = set()
            unique_results = []
            for result in sorted(theme_results, key=lambda x: x['similarity_score'], reverse=True):
                if result['id'] not in seen_ids:
                    unique_results.append(result)
                    seen_ids.add(result['id'])
            
            results[theme] = unique_results[:limit]
        
        return results

# Global instance
vector_search_service = VectorSearchService()