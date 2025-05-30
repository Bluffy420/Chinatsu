import discord
from discord import app_commands
from discord.ext import commands
import logging
import re
from typing import Dict, Optional, Tuple
from ..database.models import UserRelations, LearningData
from ..config import OWNER_ID

class UserRelationsCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.interaction_weights = {
            "message": 1,
            "reaction": 0.8,
            "command": 2,
            "mention": 1.8
        }
        
        # Sentiment analysis patterns
        self.positive_patterns = {
            r"\b(thanks?|thank you|appreciate|grateful|helpful)\b": 0.8,
            r"\b(love|awesome|amazing|excellent|great|good)\b": 0.5,
            r"\b(nice|cool|sweet|wonderful|fantastic)\b": 0.4,
            r"[<]?3|[❤️💕💖💗💓]": 0.6,
            r"[:;][)]": 0.3,
            r"\b(cute|adorable|lovely|kind|gentle)\b": 0.5,
            r"\b(smart|clever|intelligent|wise)\b": 0.4,
            r"[🥰😊😄😃😀]": 0.5,
            r"\b(friend|bestie|pal)\b": 0.6
        }
        
        self.negative_patterns = {
            r"\b(hate|stupid|dumb|useless|bad)\b": -0.2,
            r"\b(fuck|shit|damn|bitch|ass)\b": -0.3,
            r"\b(wrong|incorrect|error|bug|broken)\b": -0.1,
            r"[:;][(@]": -0.1,
            r"[🤬😠😡👎]": -0.2
        }
        
        # Reputation thresholds and responses
        self.reputation_responses = {
            150: ["You're such a wonderful friend! I really enjoy our time together! 💖", 
                  "You always make my day brighter! Thank you for being so kind! ✨"],
            100: ["I really enjoy our conversations! You're so nice to talk to! 💕",
                  "You're one of my favorite users! Always so pleasant! 😊"],
            50: ["It's always nice talking to you! You're very kind! 💫",
                 "I appreciate your friendly attitude! Makes me happy! 🌟"],
            0: ["Hello friend! Hope you're having a good day! 😊", 
                "Hi there! Nice to see you! ✨"],
            -25: ["I know we can have better conversations! Let's try again! 💫",
                  "Everyone has bad days, but I'm here if you want to chat! 🌟"],
            -50: ["I still believe in you! Let's start fresh! 💕",
                  "I'm sure we can be friends if we try! 😊"]
        }
    
    def _analyze_sentiment(self, message: str) -> Tuple[float, list]:
        """Analyze message sentiment and return score with reasons"""
        score = 0
        reasons = []
        
        # Convert to lowercase for pattern matching
        message_lower = message.lower()
        
        # Check positive patterns
        for pattern, weight in self.positive_patterns.items():
            matches = re.findall(pattern, message_lower)
            if matches:
                score += weight * len(matches)
                reasons.append(f"Positive language: {', '.join(matches)}")
        
        # Check negative patterns
        for pattern, weight in self.negative_patterns.items():
            matches = re.findall(pattern, message_lower)
            if matches:
                score += weight * len(matches)
                reasons.append(f"Negative language: {', '.join(matches)}")
        
        # Add small positive bias to all non-negative messages
        if score >= 0:
            score += 0.1
            
        return score, reasons
    
    def get_reputation_response(self, reputation: int) -> str:
        """Get appropriate response based on reputation level"""
        import random
        
        # Find the closest threshold that's less than or equal to the reputation
        closest_threshold = max((t for t in self.reputation_responses.keys() if t <= reputation), 
                              key=lambda x: abs(x - reputation))
        
        return random.choice(self.reputation_responses[closest_threshold])
        
    @app_commands.command(name="relations")
    @app_commands.describe(user_id="User ID to check relations with (optional)")
    async def view_relations(
        self,
        interaction: discord.Interaction,
        user_id: Optional[str] = None
    ):
        """View relationship stats with a user"""
        try:
            target_id = int(user_id) if user_id else interaction.user.id
            user_data = UserRelations.get_user(target_id)
            
            # Get personality traits
            traits = LearningData.execute_query(
                """
                SELECT trait_type, trait_value, confidence
                FROM user_personality
                WHERE user_id = ?
                ORDER BY confidence DESC
                LIMIT 5
                """,
                (target_id,),
                fetch=True
            )
            
            # Get interaction stats
            interactions = LearningData.execute_query(
                """
                SELECT COUNT(*) as count,
                       SUM(CASE WHEN sentiment_score > 0 THEN 1 ELSE 0 END) as positive_count,
                       SUM(CASE WHEN sentiment_score < 0 THEN 1 ELSE 0 END) as negative_count
                FROM conversation_log
                WHERE user_id = ?
                """,
                (target_id,),
                fetch=True
            )
            
            # Create embed
            embed = discord.Embed(
                title=f"User Relations - {target_id}",
                color=discord.Color.blue()
            )
            
            # Basic stats with reputation response
            reputation_msg = self.get_reputation_response(user_data['reputation'])
            embed.add_field(
                name="Basic Stats",
                value=f"Honor: {user_data['reputation']}\nInteractions: {user_data['interactions']}\nBot's Opinion: {reputation_msg}",
                inline=False
            )
            
            # Personality traits
            if traits:
                traits_text = "\n".join(
                    f"{trait[0]}: {trait[1]} ({trait[2]:.0%} confidence)"
                    for trait in traits
                )
                embed.add_field(
                    name="Personality Traits",
                    value=traits_text,
                    inline=False
                )
            
            # Interaction history with sentiment
            if interactions and interactions[0][0] > 0:
                total = interactions[0][0]
                positive = interactions[0][1] or 0
                negative = interactions[0][2] or 0
                neutral = total - positive - negative
                
                embed.add_field(
                    name="Interaction History",
                    value=f"Total Messages: {total:,}\n"
                          f"😊 Positive: {positive:,} ({positive/total:.1%})\n"
                          f"😐 Neutral: {neutral:,} ({neutral/total:.1%})\n"
                          f"😟 Negative: {negative:,} ({negative/total:.1%})",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logging.error(f"Error viewing relations: {e}")
            await interaction.response.send_message("❌ Failed to get user relations.", ephemeral=True)
            
    async def log_interaction(
        self,
        user_id: int,
        interaction_type: str,
        message_content: str = "",
        success: bool = True
    ):
        """Log an interaction with a user"""
        try:
            # Get base weight for interaction type
            weight = self.interaction_weights.get(interaction_type, 1.0)
            
            # Analyze sentiment if there's message content
            sentiment_score = 0
            if message_content:
                sentiment_score, _ = self._analyze_sentiment(message_content)
                weight += sentiment_score
            
            # Adjust weight based on success
            if not success:
                weight *= 0.5
                
            # Update user relations
            UserRelations.execute_query(
                """
                UPDATE relations_users
                SET interactions = interactions + 1,
                    reputation = reputation + ?,
                    last_interaction = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (weight, user_id)
            )
            
            # Store sentiment score in conversation log
            if message_content:
                LearningData.execute_query(
                    """
                    UPDATE conversation_log
                    SET sentiment_score = ?
                    WHERE user_id = ? AND user_message = ?
                    """,
                    (sentiment_score, user_id, message_content)
                )
            
        except Exception as e:
            logging.error(f"Error logging interaction: {e}")
            
    async def analyze_interaction(
        self,
        user_id: int,
        message_content: str,
        response: str,
        success: bool
    ):
        """Analyze and store interaction data"""
        try:
            # Analyze sentiment
            sentiment_score, sentiment_reasons = self._analyze_sentiment(message_content)
            
            # Store in conversation log with sentiment
            LearningData.execute_query(
                """
                INSERT INTO conversation_log 
                (user_id, user_message, bot_response, sentiment_score, sentiment_reasons)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, message_content, response, sentiment_score, str(sentiment_reasons))
            )
            
            # Update success rate for response pattern
            if success:
                LearningData.execute_query(
                    """
                    UPDATE response_patterns
                    SET success_rate = (success_rate * usage_count + 1.0) / (usage_count + 1),
                        usage_count = usage_count + 1
                    WHERE input_pattern = ?
                    """,
                    (message_content,)
                )
            
            # Extract and update personality traits
            await self._update_personality_traits(user_id, message_content)
            
            # Log the interaction with sentiment
            await self.log_interaction(user_id, "message", message_content, success)
            
        except Exception as e:
            logging.error(f"Error analyzing interaction: {e}")
            
    async def _update_personality_traits(self, user_id: int, message: str):
        """Update personality traits based on message content"""
        try:
            # Simple trait analysis (you can make this more sophisticated)
            traits = {
                "politeness": 0.0,
                "friendliness": 0.0,
                "engagement": 0.0
            }
            
            # Basic analysis
            words = message.lower().split()
            
            # Politeness indicators
            polite_words = {"please", "thank", "thanks", "appreciate", "sorry", "excuse"}
            traits["politeness"] = sum(1 for word in words if word in polite_words) / len(words)
            
            # Friendliness indicators
            friendly_words = {"hello", "hi", "hey", "nice", "good", "great", "awesome", "love"}
            traits["friendliness"] = sum(1 for word in words if word in friendly_words) / len(words)
            
            # Engagement indicators
            engagement_markers = {"?", "!", "what", "how", "why", "tell", "explain"}
            traits["engagement"] = sum(1 for word in words if word in engagement_markers) / len(words)
            
            # Update database
            for trait, value in traits.items():
                if value > 0:
                    LearningData.execute_query(
                        """
                        INSERT INTO user_personality (user_id, trait_type, trait_value, confidence)
                        VALUES (?, ?, ?, 0.1)
                        ON CONFLICT(user_id, trait_type) DO UPDATE SET
                            trait_value = (trait_value * confidence + ? * 0.1) / (confidence + 0.1),
                            confidence = MIN(confidence + 0.1, 1.0)
                        """,
                        (user_id, trait, str(value), value)
                    )
                    
        except Exception as e:
            logging.error(f"Error updating personality traits: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(UserRelationsCommands(bot)) 