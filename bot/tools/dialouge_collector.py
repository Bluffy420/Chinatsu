import json
from pathlib import Path
from typing import List, Dict, Any
from ..services.dialogue_training import DialogueTrainer

class DialogueCollector:
    def __init__(self):
        self.trainer = DialogueTrainer()
        self.data_path = Path("data/dialogue")
        self.data_path.mkdir(parents=True, exist_ok=True)
        
    def add_chapter_dialogue(
        self,
        chapter: int,
        dialogues: List[Dict[str, Any]]
    ):
        """Add dialogue entries from a chapter or scene"""
        # Validate and clean dialogue entries
        cleaned_dialogues = []
        for entry in dialogues:
            if self._validate_entry(entry):
                entry['chapter'] = chapter
                cleaned_dialogues.append(entry)
        
        # Save to chapter file
        chapter_file = self.data_path / f"chapter_{chapter:03d}.json"
        with open(chapter_file, 'w', encoding='utf-8') as f:
            json.dump(cleaned_dialogues, f, indent=2)
        
        # Process dialogues
        for entry in cleaned_dialogues:
            self.trainer.add_dialogue_entry(
                entry['context'],
                entry['dialogue'],
                entry.get('emotion', 'neutral')
            )
    
    def _validate_entry(self, entry: Dict[str, Any]) -> bool:
        """Validate a dialogue entry"""
        required_fields = ['character', 'dialogue', 'context']
        if not all(field in entry for field in required_fields):
            return False
            
        if entry['character'].lower() != 'chinatsu':
            return False
            
        return True
    
    def load_all_chapters(self):
        """Load all saved chapter dialogues"""
        for chapter_file in sorted(self.data_path.glob("chapter_*.json")):
            try:
                self.trainer.load_dialogue_data(str(chapter_file))
            except Exception as e:
                print(f"Error loading {chapter_file}: {e}")

# Example usage:
"""
collector = DialogueCollector()

# Add dialogue from chapter 1
chapter_1_dialogues = [
    {
        "character": "Chinatsu",
        "dialogue": "Keep going! I'll practice hard too!",
        "context": "practice_encouragement",
        "emotion": "encouraging",
        "page": 15
    },
    {
        "character": "Chinatsu",
        "dialogue": "I'm so happy you joined the badminton club!",
        "context": "club_welcome",
        "emotion": "happy",
        "page": 22
    }
]

collector.add_chapter_dialogue(1, chapter_1_dialogues)
""" 