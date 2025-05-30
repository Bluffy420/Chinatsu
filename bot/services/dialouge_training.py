import json
import re
from typing import List, Dict, Any
from pathlib import Path
from ..database.models import LearningData

class DialogueTrainer:
    def __init__(self):
        self.dialogue_patterns = {}
        self.character_traits = {
            "chinatsu": {
                "personality": {
                    "determined": 0.9,
                    "hardworking": 0.9,
                    "supportive": 0.8,
                    "direct": 0.7,
                    "competitive": 0.7
                },
                "speech_style": {
                    "polite": 0.8,
                    "friendly": 0.7,
                    "encouraging": 0.8,
                    "honest": 0.9
                }
            }
        }
    
    def load_dialogue_data(self, dialogue_file: str):
        """Load dialogue data from JSON file"""
        try:
            with open(dialogue_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Process dialogue entries
            for entry in data:
                if entry.get('character').lower() == 'chinatsu':
                    self._process_dialogue_entry(entry)
                    
        except Exception as e:
            print(f"Error loading dialogue data: {e}")
    
    def _process_dialogue_entry(self, entry: Dict[str, Any]):
        """Process a single dialogue entry"""
        context = entry.get('context', '')
        dialogue = entry.get('dialogue', '')
        emotion = entry.get('emotion', 'neutral')
        
        # Clean and normalize the text
        dialogue = self._normalize_text(dialogue)
        
        # Store in database
        LearningData.execute_query(
            """
            INSERT INTO dialogue_patterns 
            (context_type, input_pattern, response_template, emotion, usage_count)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(input_pattern, response_template) DO UPDATE SET
                usage_count = usage_count + 1
            """,
            (context, dialogue, dialogue, emotion)
        )
        
        # Extract speech patterns
        self._extract_speech_patterns(dialogue, emotion)
    
    def _normalize_text(self, text: str) -> str:
        """Clean and normalize dialogue text"""
        # Remove special characters, keep only English text and basic punctuation
        text = re.sub(r'[^\w\s!?.,]', '', text)
        return text.strip()
    
    def _extract_speech_patterns(self, dialogue: str, emotion: str):
        """Extract and store common speech patterns"""
        # Common English speech patterns
        patterns = {
            r'(?i)(hello|hi|hey)': 'greeting',
            r'(?i)(thanks|thank you)': 'gratitude',
            r'(?i)(sorry|apologize)': 'apology',
            r'(?i)(great job|well done|awesome)': 'praise',
            r'(?i)(you can do it|keep going)': 'encouraging',
            r'(?i)(please|would you)': 'polite_request',
            r'(?i)(lol|haha|hehe)': 'amusement'
        }
        
        for pattern, pattern_type in patterns.items():
            if re.search(pattern, dialogue):
                self.dialogue_patterns[pattern_type] = self.dialogue_patterns.get(pattern_type, 0) + 1
    
    def get_character_response(self, context: str, emotion: str = 'neutral') -> str:
        """Get a character-appropriate response"""
        try:
            # Query the database for matching patterns
            results = LearningData.execute_query(
                """
                SELECT response_template, usage_count
                FROM dialogue_patterns
                WHERE context_type = ? AND emotion = ?
                ORDER BY usage_count DESC
                LIMIT 5
                """,
                (context, emotion),
                fetch=True
            )
            
            if results:
                # Return the most commonly used appropriate response
                return results[0][0]
                
        except Exception as e:
            print(f"Error getting character response: {e}")
            
        return None
    
    def add_dialogue_entry(self, context: str, dialogue: str, emotion: str = 'neutral'):
        """Add a new dialogue entry"""
        entry = {
            'character': 'chinatsu',
            'context': context,
            'dialogue': dialogue,
            'emotion': emotion
        }
        self._process_dialogue_entry(entry)

# Example dialogue data structure:
"""
{
    "character": "Chinatsu",
    "context": "practice_encouragement",
    "dialogue": "You can do it! I'll keep practicing hard too!",
    "emotion": "encouraging"
}
""" 