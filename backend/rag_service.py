# Liberation Bible Project - RAG Service
# Sophisticated Question-Answer Interface using Retrieval-Augmented Generation

import re
import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Union
from enum import Enum
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import text, func, or_
import openai
import os

from models import (
    BiblicalText, HistoricalNote, GeographicalLocation, OriginalWord, 
    CrossReference, LexiconEntry, PersonPlaceNetwork, AbstractVerse,
    Canon, Versification, CanonicalPosition
)
from vector_search import vector_search_service
from openai_service import openai_client


class QuestionType(Enum):
    """Classification of biblical questions"""
    LOCATION = "location"
    PERSON = "person"
    CONCEPTUAL = "conceptual"
    HISTORICAL = "historical"
    TEXTUAL = "textual"
    GENERAL = "general"


@dataclass
class RetrievedContext:
    """Container for retrieved contextual information"""
    biblical_passages: List[Dict[str, Any]]
    historical_notes: List[Dict[str, Any]]
    geographical_data: List[Dict[str, Any]]
    lexicon_entries: List[Dict[str, Any]]
    cross_references: List[Dict[str, Any]]
    confidence_score: float


@dataclass
class RAGResponse:
    """Structured response from RAG system"""
    question: str
    answer: str
    question_type: QuestionType
    biblical_passages: List[Dict[str, Any]]
    historical_context: List[Dict[str, Any]]
    geographical_data: List[Dict[str, Any]]
    lexicon_insights: List[Dict[str, Any]]
    related_queries: List[str]
    confidence_score: float
    processing_time: float


class QuestionClassifier:
    """AI-powered question type classification"""
    
    def __init__(self):
        self.location_patterns = [
            r'\b(where|location|place|lived|dwelt|resided|journey|traveled|went|city|land|country)\b',
            r'\b(coordinates|map|modern|ancient\s+location)\b',
        ]
        self.person_patterns = [
            r'\b(who\s+was|what\s+was.*name|identity|called|known\s+as)\b',
            r'\b(father|mother|son|daughter|brother|sister|wife|husband)\b',
        ]
        self.conceptual_patterns = [
            r'\b(about|regarding|concerning|verses\s+about|meaning\s+of)\b',
            r'\b(love|forgiveness|faith|hope|salvation|wisdom|peace)\b',
        ]
        self.historical_patterns = [
            r'\b(when|during|time|period|era|year|century|pharaoh|king|emperor)\b',
            r'\b(historical|context|background|culture|customs)\b',
        ]
        self.textual_patterns = [
            r'\b(translation|compare|differences|original|hebrew|greek|aramaic)\b',
            r'\b(manuscript|text|variant|reading)\b',
        ]
        self.canonical_myths_patterns = [
            r'\b(constantine|nicaea|nicea|council.*nicaea|emperor.*constantine)\b',
            r'\b(who.*decided.*bible|who.*chose.*books|emperor.*bible|roman.*emperor.*canon)\b',
            r'\b(canon.*formation|bible.*formation|how.*bible.*formed|biblical.*canon)\b',
        ]

    async def classify_question(self, question: str) -> QuestionType:
        """
        Classify question type using pattern matching and AI assistance
        """
        question_lower = question.lower()
        
        # Check for canonical myths patterns first (highest priority)
        canonical_myths_score = sum(1 for pattern in self.canonical_myths_patterns 
                                  if re.search(pattern, question_lower))
        
        # If canonical myths detected, prioritize as HISTORICAL type with special flag
        if canonical_myths_score > 0:
            return QuestionType.HISTORICAL  # We'll handle the canonical myth flag in context retrieval
        
        # Pattern-based classification (fast path)
        location_score = sum(1 for pattern in self.location_patterns 
                           if re.search(pattern, question_lower))
        person_score = sum(1 for pattern in self.person_patterns 
                         if re.search(pattern, question_lower))
        conceptual_score = sum(1 for pattern in self.conceptual_patterns 
                             if re.search(pattern, question_lower))
        historical_score = sum(1 for pattern in self.historical_patterns 
                             if re.search(pattern, question_lower))
        textual_score = sum(1 for pattern in self.textual_patterns 
                          if re.search(pattern, question_lower))
        
        scores = {
            QuestionType.LOCATION: location_score,
            QuestionType.PERSON: person_score,
            QuestionType.CONCEPTUAL: conceptual_score,
            QuestionType.HISTORICAL: historical_score,
            QuestionType.TEXTUAL: textual_score,
        }
        
        # Get highest scoring type
        max_score = max(scores.values())
        if max_score > 0:
            for q_type, score in scores.items():
                if score == max_score:
                    return q_type
        
        # Fallback to AI classification for ambiguous cases
        try:
            prompt = f"""
            Classify this biblical question into one of these types:
            - LOCATION: Questions about places, geography, where things happened
            - PERSON: Questions about people, names, identities, relationships
            - CONCEPTUAL: Questions about themes, concepts, theology, meanings
            - HISTORICAL: Questions about time periods, events, historical context
            - TEXTUAL: Questions about translations, manuscripts, original languages
            - GENERAL: Questions that don't fit other categories
            
            Question: "{question}"
            
            Respond with just the category name.
            """
            
            response = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=0.1
            )
            
            classification = response.choices[0].message.content.strip().upper()
            
            # Map response to enum
            type_mapping = {
                "LOCATION": QuestionType.LOCATION,
                "PERSON": QuestionType.PERSON,
                "CONCEPTUAL": QuestionType.CONCEPTUAL,
                "HISTORICAL": QuestionType.HISTORICAL,
                "TEXTUAL": QuestionType.TEXTUAL,
                "GENERAL": QuestionType.GENERAL,
            }
            
            return type_mapping.get(classification, QuestionType.GENERAL)
            
        except Exception as e:
            print(f"Error in AI classification: {e}")
            return QuestionType.GENERAL
    
    def is_canonical_myths_question(self, question: str) -> bool:
        """
        Detect if question is about canonical myths (Constantine/Nicaea/Canon formation)
        """
        question_lower = question.lower()
        canonical_myths_score = sum(1 for pattern in self.canonical_myths_patterns 
                                  if re.search(pattern, question_lower))
        return canonical_myths_score > 0


class ContextRetriever:
    """Comprehensive context retrieval from multiple data sources"""
    
    def __init__(self):
        self.max_biblical_passages = 10
        self.max_historical_notes = 5
        self.max_geographical_data = 5
        self.max_lexicon_entries = 8
        # Canonical myths patterns for myth-buster grounding
        self.canonical_myths_patterns = [
            r'\b(constantine|nicaea|nicea|council.*nicaea|emperor.*constantine)\b',
            r'\b(who.*decided.*bible|who.*chose.*books|emperor.*bible|roman.*emperor.*canon)\b',
            r'\b(canon.*formation|bible.*formation|how.*bible.*formed|biblical.*canon)\b',
        ]
    
    def _is_canonical_myths_question(self, question: str) -> bool:
        """
        Detect if question is about canonical myths (Constantine/Nicaea/Canon formation)
        """
        question_lower = question.lower()
        canonical_myths_score = sum(1 for pattern in self.canonical_myths_patterns 
                                  if re.search(pattern, question_lower))
        return canonical_myths_score > 0
        
    async def retrieve_context(
        self, 
        db: Session, 
        question: str, 
        question_type: QuestionType,
        extracted_entities: Optional[List[str]] = None
    ) -> RetrievedContext:
        """
        Retrieve relevant context based on question type and entities
        """
        
        # Extract entities if not provided
        if extracted_entities is None:
            extracted_entities = await self._extract_entities(question)
        
        # Retrieve context based on question type
        if question_type == QuestionType.LOCATION:
            return await self._retrieve_location_context(db, question, extracted_entities)
        elif question_type == QuestionType.PERSON:
            return await self._retrieve_person_context(db, question, extracted_entities)
        elif question_type == QuestionType.CONCEPTUAL:
            return await self._retrieve_conceptual_context(db, question, extracted_entities)
        elif question_type == QuestionType.HISTORICAL:
            return await self._retrieve_historical_context(db, question, extracted_entities)
        elif question_type == QuestionType.TEXTUAL:
            return await self._retrieve_textual_context(db, question, extracted_entities)
        else:
            return await self._retrieve_general_context(db, question, extracted_entities)
    
    async def _extract_entities(self, question: str) -> List[str]:
        """Extract key entities (names, places, concepts) from question"""
        try:
            prompt = f"""
            Extract key biblical entities from this question. Include:
            - People names (Moses, Peter, David, etc.)
            - Place names (Egypt, Jerusalem, Galilee, etc.)  
            - Biblical concepts (forgiveness, salvation, love, etc.)
            - Book names (Genesis, Matthew, etc.)
            
            Question: "{question}"
            
            Return as a JSON list of entities.
            """
            
            response = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200
            )
            
            content = response.choices[0].message.content
            if content:
                try:
                    # Try to parse as JSON first
                    result = json.loads(content)
                    # Handle both list and dict responses
                    if isinstance(result, list):
                        return result
                    elif isinstance(result, dict):
                        return result.get("entities", [])
                    else:
                        return []
                except json.JSONDecodeError:
                    # Fallback: extract entities from text using simple patterns
                    import re
                    entities = re.findall(r'[A-Z][a-z]+', content)
                    return entities[:10]
            
        except Exception as e:
            print(f"Error extracting entities: {e}")
        
        # Fallback: simple keyword extraction
        words = question.split()
        entities = [word.strip('.,;:!?"\'') for word in words 
                   if len(word) > 3 and word[0].isupper()]
        return entities[:10]  # Limit to 10 entities
    
    async def _retrieve_location_context(
        self, db: Session, question: str, entities: List[str]
    ) -> RetrievedContext:
        """Retrieve context for location-based questions"""
        
        # Search biblical texts with semantic search
        biblical_passages = await vector_search_service.semantic_search(
            db, question, limit=self.max_biblical_passages
        )
        
        # Search geographical locations
        geo_data = []
        for entity in entities:
            geo_results = db.query(GeographicalLocation).filter(
                or_(
                    GeographicalLocation.name.ilike(f"%{entity}%"),
                    GeographicalLocation.modern_name.ilike(f"%{entity}%"),
                    GeographicalLocation.description.ilike(f"%{entity}%")
                )
            ).limit(3).all()
            
            for geo in geo_results:
                geo_data.append({
                    "ancient_name": geo.name,
                    "modern_name": geo.modern_name,
                    "coordinates": [geo.latitude, geo.longitude] if geo.latitude and geo.longitude else None,
                    "description": geo.description,
                    "confidence": geo.confidence_score if hasattr(geo, 'confidence_score') else 0.7
                })
        
        # Get historical notes related to places
        historical_notes = []
        for entity in entities:
            notes = db.query(HistoricalNote).filter(
                or_(
                    HistoricalNote.title.ilike(f"%{entity}%"),
                    HistoricalNote.content.ilike(f"%{entity}%")
                )
            ).limit(2).all()
            
            for note in notes:
                historical_notes.append({
                    "title": note.title,
                    "content": note.content,
                    "period": note.historical_period,
                    "source": note.source
                })
        
        return RetrievedContext(
            biblical_passages=biblical_passages,
            historical_notes=historical_notes[:self.max_historical_notes],
            geographical_data=geo_data[:self.max_geographical_data],
            lexicon_entries=[],
            cross_references=[],
            confidence_score=0.8
        )
    
    async def _retrieve_person_context(
        self, db: Session, question: str, entities: List[str]
    ) -> RetrievedContext:
        """Retrieve context for person-based questions"""
        
        # Search biblical texts
        biblical_passages = await vector_search_service.semantic_search(
            db, question, limit=self.max_biblical_passages
        )
        
        # Search for person references in lexicon
        lexicon_entries = []
        for entity in entities:
            lexicon_results = db.query(LexiconEntry).filter(
                or_(
                    LexiconEntry.original_word.ilike(f"%{entity}%"),
                    LexiconEntry.definition.ilike(f"%{entity}%"),
                    LexiconEntry.transliteration.ilike(f"%{entity}%")
                )
            ).limit(3).all()
            
            for entry in lexicon_results:
                lexicon_entries.append({
                    "word": entry.original_word,
                    "language": entry.language.value if entry.language else "unknown",
                    "definition": entry.definition,
                    "transliteration": entry.transliteration,
                    "strong_number": entry.strong_number
                })
        
        # Search historical notes
        historical_notes = []
        for entity in entities:
            notes = db.query(HistoricalNote).filter(
                or_(
                    HistoricalNote.title.ilike(f"%{entity}%"),
                    HistoricalNote.content.ilike(f"%{entity}%")
                )
            ).limit(2).all()
            
            for note in notes:
                historical_notes.append({
                    "title": note.title,
                    "content": note.content,
                    "period": note.historical_period,
                    "source": note.source
                })
        
        return RetrievedContext(
            biblical_passages=biblical_passages,
            historical_notes=historical_notes[:self.max_historical_notes],
            geographical_data=[],
            lexicon_entries=lexicon_entries[:self.max_lexicon_entries],
            cross_references=[],
            confidence_score=0.85
        )
    
    async def _retrieve_conceptual_context(
        self, db: Session, question: str, entities: List[str]
    ) -> RetrievedContext:
        """Retrieve context for conceptual/thematic questions"""
        
        # Use semantic search for conceptual questions
        biblical_passages = await vector_search_service.semantic_search(
            db, question, limit=self.max_biblical_passages, similarity_threshold=0.6
        )
        
        # Search for thematic historical notes
        historical_notes = []
        for entity in entities:
            notes = db.query(HistoricalNote).filter(
                HistoricalNote.content.ilike(f"%{entity}%")
            ).limit(2).all()
            
            for note in notes:
                historical_notes.append({
                    "title": note.title,
                    "content": note.content,
                    "period": note.historical_period,
                    "source": note.source
                })
        
        # Search lexicon for concept definitions
        lexicon_entries = []
        for entity in entities:
            lexicon_results = db.query(LexiconEntry).filter(
                or_(
                    LexiconEntry.definition.ilike(f"%{entity}%"),
                    LexiconEntry.word_text.ilike(f"%{entity}%")
                )
            ).limit(2).all()
            
            for entry in lexicon_results:
                lexicon_entries.append({
                    "word": entry.original_word,
                    "language": entry.language.value if entry.language else "unknown",
                    "definition": entry.definition,
                    "transliteration": entry.transliteration,
                    "strong_number": entry.strong_number
                })
        
        return RetrievedContext(
            biblical_passages=biblical_passages,
            historical_notes=historical_notes[:self.max_historical_notes],
            geographical_data=[],
            lexicon_entries=lexicon_entries[:self.max_lexicon_entries],
            cross_references=[],
            confidence_score=0.75
        )
    
    async def _retrieve_historical_context(
        self, db: Session, question: str, entities: List[str]
    ) -> RetrievedContext:
        """Retrieve context for historical questions with myth-buster grounding"""
        
        # Search biblical texts
        biblical_passages = await vector_search_service.semantic_search(
            db, question, limit=self.max_biblical_passages
        )
        
        historical_notes = []
        
        # **MYTH-BUSTER GROUNDING**: Check if this is a canonical myths question
        is_canonical_myths = self._is_canonical_myths_question(question)
        if is_canonical_myths:
            # Prioritize CANON_HISTORY notes for Constantine/Nicaea/Canon questions
            canon_history_notes = db.query(HistoricalNote).filter(
                or_(
                    HistoricalNote.title.ilike('%CANON_HISTORY%'),
                    HistoricalNote.content.ilike('%Constantine%'),
                    HistoricalNote.content.ilike('%Nicaea%'),
                    HistoricalNote.content.ilike('%canon%formation%'),
                    HistoricalNote.content.ilike('%biblical%canon%')
                )
            ).limit(4).all()  # Get more for myth-busting
            
            for note in canon_history_notes:
                historical_notes.append({
                    "title": note.title,
                    "content": note.content,
                    "period": note.historical_period,
                    "source": note.source,
                    "priority": "canonical_myth_buster"  # Flag for prompt prioritization
                })
        
        # Regular historical context retrieval for remaining slots
        remaining_slots = max(0, self.max_historical_notes - len(historical_notes))
        if remaining_slots > 0:
            for entity in entities:
                notes = db.query(HistoricalNote).filter(
                    or_(
                        HistoricalNote.title.ilike(f"%{entity}%"),
                        HistoricalNote.content.ilike(f"%{entity}%"),
                        HistoricalNote.historical_period.ilike(f"%{entity}%")
                    )
                ).limit(2).all()
            
            for note in notes:
                historical_notes.append({
                    "title": note.title,
                    "content": note.content,
                    "period": note.historical_period,
                    "source": note.source
                })
        
        # Get related geographical context
        geo_data = []
        for entity in entities:
            geo_results = db.query(GeographicalLocation).filter(
                or_(
                    GeographicalLocation.name.ilike(f"%{entity}%"),
                    GeographicalLocation.description.ilike(f"%{entity}%")
                )
            ).limit(2).all()
            
            for geo in geo_results:
                geo_data.append({
                    "ancient_name": geo.name,
                    "modern_name": geo.modern_name,
                    "description": geo.description,
                    "archaeological_evidence": getattr(geo, 'archaeological_evidence', None)
                })
        
        return RetrievedContext(
            biblical_passages=biblical_passages,
            historical_notes=historical_notes[:self.max_historical_notes],
            geographical_data=geo_data[:self.max_geographical_data],
            lexicon_entries=[],
            cross_references=[],
            confidence_score=0.82
        )
    
    async def _retrieve_textual_context(
        self, db: Session, question: str, entities: List[str]
    ) -> RetrievedContext:
        """Retrieve context for textual/translation questions"""
        
        # Search biblical texts
        biblical_passages = await vector_search_service.semantic_search(
            db, question, limit=self.max_biblical_passages
        )
        
        # Focus on lexicon entries for original language insights
        lexicon_entries = []
        for entity in entities:
            lexicon_results = db.query(LexiconEntry).filter(
                or_(
                    LexiconEntry.original_word.ilike(f"%{entity}%"),
                    LexiconEntry.definition.ilike(f"%{entity}%"),
                    LexiconEntry.transliteration.ilike(f"%{entity}%")
                )
            ).limit(4).all()
            
            for entry in lexicon_results:
                lexicon_entries.append({
                    "word": entry.original_word,
                    "language": entry.language.value if entry.language else "unknown",
                    "definition": entry.definition,
                    "transliteration": entry.transliteration,
                    "strong_number": entry.strong_number,
                    "etymology": getattr(entry, 'etymology', None)
                })
        
        return RetrievedContext(
            biblical_passages=biblical_passages,
            historical_notes=[],
            geographical_data=[],
            lexicon_entries=lexicon_entries[:self.max_lexicon_entries],
            cross_references=[],
            confidence_score=0.80
        )
    
    async def _retrieve_general_context(
        self, db: Session, question: str, entities: List[str]
    ) -> RetrievedContext:
        """Retrieve general context for unclassified questions"""
        
        # Use semantic search as primary method
        biblical_passages = await vector_search_service.semantic_search(
            db, question, limit=self.max_biblical_passages, similarity_threshold=0.6
        )
        
        # Light search across all data types
        historical_notes = []
        geo_data = []
        lexicon_entries = []
        
        for entity in entities[:3]:  # Limit entities for general search
            # Historical notes
            notes = db.query(HistoricalNote).filter(
                HistoricalNote.content.ilike(f"%{entity}%")
            ).limit(1).all()
            
            for note in notes:
                historical_notes.append({
                    "title": note.title,
                    "content": note.content,
                    "period": note.historical_period,
                    "source": note.source
                })
        
        return RetrievedContext(
            biblical_passages=biblical_passages,
            historical_notes=historical_notes[:2],
            geographical_data=[],
            lexicon_entries=[],
            cross_references=[],
            confidence_score=0.65
        )


class ResponseGenerator:
    """AI-powered response generation using retrieved context"""
    
    def __init__(self):
        self.model = "gpt-4"
        self.max_tokens = 800
    
    async def generate_response(
        self, 
        question: str, 
        question_type: QuestionType,
        context: RetrievedContext
    ) -> str:
        """
        Generate intelligent response using OpenAI and retrieved context
        """
        
        # Build context prompt
        context_prompt = self._build_context_prompt(context, question_type)
        
        # Create specialized system prompt based on question type
        system_prompt = self._get_system_prompt(question_type)
        
        # Main prompt
        main_prompt = f"""
        QUESTION: {question}
        
        RETRIEVED CONTEXT:
        {context_prompt}
        
        Please provide a comprehensive, accurate answer that:
        1. Directly answers the question
        2. Uses the biblical passages and context provided
        3. Includes specific references (book, chapter, verse)
        4. Provides historical and cultural context when relevant
        5. Mentions geographical information if applicable
        6. Is scholarly but accessible
        7. Acknowledges uncertainty where appropriate
        
        Format your response in a natural, conversational way while being informative and accurate.
        """
        
        try:
            response = openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": main_prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=0.3
            )
            
            return response.choices[0].message.content or "I apologize, but I couldn't generate a response to your question."
            
        except Exception as e:
            print(f"Error generating response: {e}")
            return "I apologize, but I encountered an error while processing your question. Please try again."
    
    def _build_context_prompt(self, context: RetrievedContext, question_type: QuestionType) -> str:
        """Build formatted context prompt from retrieved data"""
        
        prompt_parts = []
        
        # Biblical passages
        if context.biblical_passages:
            prompt_parts.append("BIBLICAL PASSAGES:")
            for i, passage in enumerate(context.biblical_passages[:8], 1):
                ref = passage.get('reference', 'Unknown')
                text = passage.get('text', '')[:200] + "..." if len(passage.get('text', '')) > 200 else passage.get('text', '')
                score = passage.get('similarity_score', 0)
                prompt_parts.append(f"{i}. {ref} (relevance: {score:.2f}): {text}")
        
        # Historical context
        if context.historical_notes:
            # Check for canonical myth-buster notes and prioritize them
            myth_buster_notes = [note for note in context.historical_notes if note.get('priority') == 'canonical_myth_buster']
            regular_notes = [note for note in context.historical_notes if note.get('priority') != 'canonical_myth_buster']
            
            if myth_buster_notes:
                prompt_parts.append("\n🔍 CRITICAL CANONICAL HISTORY (Myth-Buster Facts):")
                for i, note in enumerate(myth_buster_notes[:3], 1):
                    title = note.get('title', 'Untitled')
                    content = note.get('content', '')  # Full content for myth-busting
                    period = note.get('period', '')
                    prompt_parts.append(f"FACT {i}: {title} ({period}): {content}")
                
                prompt_parts.append("\n⚠️ IMPORTANT: Use the above canonical history facts to correct any misconceptions about Constantine, Nicaea, or biblical canon formation.")
            
            if regular_notes:
                prompt_parts.append("\nADDITIONAL HISTORICAL CONTEXT:")
                remaining_notes = regular_notes[:4 - len(myth_buster_notes)]
                for i, note in enumerate(remaining_notes, 1):
                    title = note.get('title', 'Untitled')
                    content = note.get('content', '')[:150] + "..." if len(note.get('content', '')) > 150 else note.get('content', '')
                    period = note.get('period', '')
                    prompt_parts.append(f"{i}. {title} ({period}): {content}")
        
        # Geographical data
        if context.geographical_data:
            prompt_parts.append("\nGEOGRAPHICAL INFORMATION:")
            for i, geo in enumerate(context.geographical_data[:4], 1):
                ancient_name = geo.get('ancient_name', 'Unknown')
                modern_name = geo.get('modern_name', 'Unknown location')
                description = geo.get('description', '')[:100] + "..." if len(geo.get('description', '')) > 100 else geo.get('description', '')
                prompt_parts.append(f"{i}. {ancient_name} (modern: {modern_name}): {description}")
        
        # Lexicon entries
        if context.lexicon_entries:
            prompt_parts.append("\nORIGINAL LANGUAGE INSIGHTS:")
            for i, entry in enumerate(context.lexicon_entries[:5], 1):
                word = entry.get('word', 'Unknown')
                language = entry.get('language', 'unknown')
                definition = entry.get('definition', '')[:100] + "..." if len(entry.get('definition', '')) > 100 else entry.get('definition', '')
                prompt_parts.append(f"{i}. {word} ({language}): {definition}")
        
        return "\n".join(prompt_parts)
    
    def _get_system_prompt(self, question_type: QuestionType) -> str:
        """Get specialized system prompt based on question type"""
        
        base_prompt = """You are a biblical scholar and expert in ancient Near Eastern studies with deep knowledge of Hebrew, Greek, and Aramaic texts. You provide accurate, scholarly responses while being accessible to general audiences."""
        
        type_specific = {
            QuestionType.LOCATION: " Focus on geographical accuracy, archaeological evidence, and modern location identification.",
            QuestionType.PERSON: " Focus on historical accuracy, name etymology, and cultural context of individuals.",
            QuestionType.CONCEPTUAL: " Focus on theological accuracy, cross-references, and thematic development.",
            QuestionType.HISTORICAL: " Focus on historical accuracy, chronology, and cultural context.",
            QuestionType.TEXTUAL: " Focus on textual criticism, manuscript evidence, and translation accuracy.",
            QuestionType.GENERAL: " Provide comprehensive coverage across multiple aspects."
        }
        
        return base_prompt + type_specific.get(question_type, "")
    
    async def generate_related_queries(self, question: str, context: RetrievedContext) -> List[str]:
        """Generate related follow-up questions"""
        
        try:
            prompt = f"""
            Based on this question: "{question}"
            
            And this context: {len(context.biblical_passages)} biblical passages, {len(context.historical_notes)} historical notes, {len(context.geographical_data)} geographical locations
            
            Generate 3-5 related questions that someone might want to ask next. These should be:
            - Naturally related to the original question
            - More specific or explore different aspects
            - Answerable using biblical and historical data
            
            Return as a JSON list of questions.
            """
            
            response = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300
            )
            
            content = response.choices[0].message.content
            if content:
                try:
                    result = json.loads(content)
                    # Handle both list and dict responses
                    if isinstance(result, list):
                        return result
                    elif isinstance(result, dict):
                        return result.get("questions", [])
                    else:
                        return []
                except json.JSONDecodeError:
                    # Fallback: extract questions from text
                    import re
                    questions = re.findall(r'"([^"]+\?)"', content)
                    return questions[:5] if questions else ["What can you tell me more about this topic?"]
            
        except Exception as e:
            print(f"Error generating related queries: {e}")
        
        return []


class QueryProcessor:
    """Main orchestration class for RAG pipeline"""
    
    def __init__(self):
        self.classifier = QuestionClassifier()
        self.retriever = ContextRetriever()
        self.generator = ResponseGenerator()
    
    async def process_query(self, db: Session, question: str) -> RAGResponse:
        """
        Main entry point for processing biblical questions
        """
        import time
        start_time = time.time()
        
        try:
            # Step 1: Classify question type
            question_type = await self.classifier.classify_question(question)
            
            # Step 2: Retrieve relevant context
            context = await self.retriever.retrieve_context(db, question, question_type)
            
            # Step 3: Generate response
            answer = await self.generator.generate_response(question, question_type, context)
            
            # Step 4: Generate related queries
            related_queries = await self.generator.generate_related_queries(question, context)
            
            processing_time = time.time() - start_time
            
            return RAGResponse(
                question=question,
                answer=answer,
                question_type=question_type,
                biblical_passages=context.biblical_passages,
                historical_context=context.historical_notes,
                geographical_data=context.geographical_data,
                lexicon_insights=context.lexicon_entries,
                related_queries=related_queries,
                confidence_score=context.confidence_score,
                processing_time=processing_time
            )
            
        except Exception as e:
            print(f"Error processing query: {e}")
            processing_time = time.time() - start_time
            
            return RAGResponse(
                question=question,
                answer="I apologize, but I encountered an error while processing your question. Please try again.",
                question_type=QuestionType.GENERAL,
                biblical_passages=[],
                historical_context=[],
                geographical_data=[],
                lexicon_insights=[],
                related_queries=[],
                confidence_score=0.0,
                processing_time=processing_time
            )


# Global instance
rag_service = QueryProcessor()