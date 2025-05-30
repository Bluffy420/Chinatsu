import json
import time
import logging
import aiohttp
from typing import Dict, Optional, Tuple
from ..config import MISTRAL_API_KEY, GENERATION_LIMITS
from .content_filter import content_filter
from ..database.models import UserRelations, LearningData

class ResponseGenerator:
    def __init__(self):
        self.api_url = "https://api.mistral.ai/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        }
        self.last_api_call = 0
        self.min_api_interval = 1  # seconds between API calls
        
    async def _make_api_call(self, messages: list, max_retries: int = 3) -> Optional[str]:
        """Make an API call to Mistral with retry logic"""
        # Rate limiting
        current_time = time.time()
        if current_time - self.last_api_call < self.min_api_interval:
            await asyncio.sleep(self.min_api_interval - (current_time - self.last_api_call))
        
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.api_url,
                        headers=self.headers,
                        json={
                            "model": "mistral-tiny",
                            "messages": messages,
                            "max_tokens": GENERATION_LIMITS["max_response_length"],
                            "temperature": 0.7
                        },
                        timeout=30
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            self.last_api_call = time.time()
                            return data["choices"][0]["message"]["content"]
                        else:
                            error_text = await response.text()
                            logging.error(f"API error (attempt {attempt + 1}): {error_text}")
                            
            except Exception as e:
                logging.error(f"API call failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    
        return None
        
    def _build_system_prompt(self, user_data: Dict, server_settings: Dict) -> str:
        """Build the system prompt based on user data and server settings"""
        base_prompt = "You are Chinatsu, a friendly and helpful Discord bot. "
        
        # Add personality aspects based on user relationship
        if user_data.get("reputation", 0) > 50:
            base_prompt += "You are very friendly and enthusiastic with this user. "
        elif user_data.get("reputation", 0) < -20:
            base_prompt += "You are more reserved and formal with this user. "
            
        # Add content guidelines based on server settings
        if not server_settings.get("mature_enabled", False):
            base_prompt += "Keep all responses family-friendly and avoid any mature content. "
        else:
            mature_level = server_settings.get("mature_level", 1)
            base_prompt += f"You can include mild mature content up to level {mature_level}. "
            
        # Add interaction style based on user history
        if user_data.get("interactions", 0) > 100:
            base_prompt += "You have a long history with this user and can reference past interactions. "
            
        return base_prompt
        
    async def generate_response(
        self,
        user_message: str,
        user_id: int,
        server_id: Optional[str] = None
    ) -> Tuple[str, Dict]:
        """Generate a response to the user message"""
        # Get user data and server settings
        user_data = UserRelations.get_user(user_id)
        
        # Check content safety
        filter_results = await content_filter.filter_message(user_message, server_id)
        if filter_results["is_filtered"]:
            return (
                "I cannot respond to that type of message. " + filter_results["checks"]["jailbreak"]["reason"],
                filter_results
            )
            
        # Build conversation context
        system_prompt = self._build_system_prompt(user_data, filter_results["server_settings"])
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        # Generate response
        response = await self._make_api_call(messages)
        if not response:
            return "I'm having trouble connecting to my brain right now. Please try again later.", filter_results
            
        # Check response safety
        response_filter = await content_filter.filter_message(response, server_id)
        if response_filter["is_filtered"]:
            # If our response was flagged, generate a safer one
            safe_messages = messages + [
                {"role": "system", "content": "Your previous response was flagged as inappropriate. Please provide a completely safe and appropriate response instead."}
            ]
            response = await self._make_api_call(safe_messages) or "I apologize, but I need to keep my response appropriate."
            
        # Store interaction for learning
        try:
            LearningData.execute_query(
                """
                INSERT INTO response_patterns (input_pattern, response_template, success_rate)
                VALUES (?, ?, 1.0)
                ON CONFLICT(input_pattern) DO UPDATE SET
                    usage_count = usage_count + 1,
                    success_rate = (success_rate * usage_count + 1.0) / (usage_count + 1)
                """,
                (user_message, response)
            )
        except Exception as e:
            logging.error(f"Error storing interaction: {e}")
            
        return response, filter_results

# Global response generator instance
response_generator = ResponseGenerator() 