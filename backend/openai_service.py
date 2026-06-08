# OpenAI Service for The Liberation Bible Project
# Referenced from blueprint:python_openai integration

import json
import os
from typing import List, Dict, Any, Optional
from openai import OpenAI

# Initialize OpenAI client with API key from environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set")

openai_client = OpenAI(api_key=OPENAI_API_KEY)


async def transcribe_audio(audio_file_path: str) -> str:
    """
    Transcribe audio file using OpenAI Whisper API
    
    Args:
        audio_file_path: Path to the audio file to transcribe
        
    Returns:
        Transcribed text content
    """
    try:
        with open(audio_file_path, "rb") as audio_file:
            response = openai_client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file
            )
        return response.text
    except Exception as e:
        raise Exception(f"Failed to transcribe audio: {e}")


async def analyze_sermon_content(
    transcribed_text: str,
    historical_notes: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Analyze sermon content against historical notes using OpenAI GPT-5
    
    Args:
        transcribed_text: The transcribed sermon text
        historical_notes: List of historical notes from database
        
    Returns:
        Analysis results with biblical connections and cultural context
    """
    try:
        # Prepare context from historical notes
        context_text = "\n".join([
            f"Note {i+1}: {note.get('title', 'Untitled')} - {note.get('content', '')}"
            for i, note in enumerate(historical_notes[:10])  # Limit to top 10 for context
        ])
        
        # Create analysis prompt
        prompt = f"""
        You are a biblical scholar analyzing a sermon for historical and cultural context.
        
        SERMON TRANSCRIPT:
        {transcribed_text}
        
        AVAILABLE HISTORICAL CONTEXT:
        {context_text}
        
        Please analyze this sermon and provide:
        1. Key biblical themes and passages referenced
        2. Historical context connections from the provided notes
        3. Cultural significance and decolonization perspective
        4. Accuracy assessment of historical claims
        5. Suggestions for additional historical context
        
        Respond in JSON format with these exact fields:
        {{
            "biblical_themes": ["theme1", "theme2"],
            "referenced_passages": ["book chapter:verse"],
            "historical_connections": ["connection descriptions"],
            "cultural_significance": "analysis text",
            "accuracy_assessment": "assessment text",
            "suggestions": ["suggestion1", "suggestion2"]
        }}
        """
        
        # the newest OpenAI model is "gpt-5" which was released August 7, 2025.
        # do not change this unless explicitly requested by the user
        response = openai_client.chat.completions.create(
            model="gpt-5",
            messages=[
                {
                    "role": "system",
                    "content": "You are a biblical scholar and historian specializing in cultural context and decolonization perspectives on scripture."
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=1500
        )
        
        content = response.choices[0].message.content
        if content is None:
            raise Exception("Empty response from OpenAI API")
        result = json.loads(content)
        return result
        
    except Exception as e:
        raise Exception(f"Failed to analyze sermon content: {e}")


async def suggest_cultural_context(biblical_passage: str) -> Dict[str, Any]:
    """
    Suggest additional cultural context for a specific biblical passage
    
    Args:
        biblical_passage: The biblical passage reference (e.g., "Genesis 1:1")
        
    Returns:
        Cultural context suggestions
    """
    try:
        prompt = f"""
        Provide cultural and historical context for the biblical passage: {biblical_passage}
        
        Focus on:
        1. Original Hebrew/Greek/Aramaic cultural meaning
        2. Historical setting and customs
        3. How colonization may have affected interpretation
        4. Liberation theology perspectives
        
        Respond in JSON format:
        {{
            "original_context": "historical setting description",
            "cultural_practices": ["practice1", "practice2"],
            "language_insights": "original language significance",
            "liberation_perspective": "decolonized interpretation",
            "additional_resources": ["resource1", "resource2"]
        }}
        """
        
        # the newest OpenAI model is "gpt-5" which was released August 7, 2025.
        # do not change this unless explicitly requested by the user
        response = openai_client.chat.completions.create(
            model="gpt-5",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=800
        )
        
        content = response.choices[0].message.content
        if content is None:
            raise Exception("Empty response from OpenAI API")
        result = json.loads(content)
        return result
        
    except Exception as e:
        raise Exception(f"Failed to get cultural context: {e}")