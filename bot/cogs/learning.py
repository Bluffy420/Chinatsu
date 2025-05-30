import discord
from discord import app_commands
from discord.ext import commands
import json
import logging
from typing import Dict, Optional
from ..database.models import LearningData, UserRelations
from ..config import GENERATION_LIMITS, OWNER_ID

class LearningCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    def _check_owner(self, interaction: discord.Interaction) -> bool:
        """Check if user is the bot owner"""
        return interaction.user.id == OWNER_ID
        
    @app_commands.command(name="learn_stats")
    async def learning_stats(self, interaction: discord.Interaction):
        """View learning statistics"""
        try:
            # Get word chain stats
            word_chains = LearningData.execute_query(
                "SELECT COUNT(*), COUNT(DISTINCT word1) FROM word_chains",
                fetch=True
            )
            total_chains = word_chains[0][0] if word_chains else 0
            unique_words = word_chains[0][1] if word_chains else 0
            
            # Get response pattern stats
            patterns = LearningData.execute_query(
                """
                SELECT 
                    COUNT(*),
                    AVG(success_rate),
                    SUM(usage_count)
                FROM response_patterns
                """,
                fetch=True
            )
            total_patterns = patterns[0][0] if patterns else 0
            avg_success = patterns[0][1] if patterns else 0
            total_uses = patterns[0][2] if patterns else 0
            
            # Create embed
            embed = discord.Embed(
                title="Learning Statistics",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Word Chains",
                value=f"Total: {total_chains:,}\nUnique Words: {unique_words:,}",
                inline=True
            )
            
            embed.add_field(
                name="Response Patterns",
                value=f"Total: {total_patterns:,}\nSuccess Rate: {avg_success:.1%}\nTotal Uses: {total_uses:,}",
                inline=True
            )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logging.error(f"Error getting learning stats: {e}")
            await interaction.response.send_message("❌ Failed to get learning statistics.", ephemeral=True)
            
    @app_commands.command(name="reset_learning")
    async def reset_learning(self, interaction: discord.Interaction):
        """Reset all learning data (Owner only)"""
        if not self._check_owner(interaction):
            await interaction.response.send_message("❌ This command is restricted to the bot owner.", ephemeral=True)
            return
            
        try:
            # Backup current data first
            await self._backup_learning_data()
            
            # Reset tables
            LearningData.execute_query("DELETE FROM word_chains")
            LearningData.execute_query("DELETE FROM response_patterns")
            LearningData.execute_query("DELETE FROM user_personality")
            
            await interaction.response.send_message("✅ Learning data has been reset. A backup was created first.", ephemeral=True)
            
        except Exception as e:
            logging.error(f"Error resetting learning data: {e}")
            await interaction.response.send_message("❌ Failed to reset learning data.", ephemeral=True)
            
    @app_commands.command(name="export_learning")
    async def export_learning(self, interaction: discord.Interaction):
        """Export learning data (Owner only)"""
        if not self._check_owner(interaction):
            await interaction.response.send_message("❌ This command is restricted to the bot owner.", ephemeral=True)
            return
            
        try:
            # Get all learning data
            word_chains = LearningData.execute_query(
                "SELECT * FROM word_chains",
                fetch=True
            )
            
            patterns = LearningData.execute_query(
                "SELECT * FROM response_patterns",
                fetch=True
            )
            
            personality = LearningData.execute_query(
                "SELECT * FROM user_personality",
                fetch=True
            )
            
            # Create export data structure
            export_data = {
                "word_chains": [
                    {
                        "word1": row[1],
                        "word2": row[2],
                        "next_word": row[3],
                        "frequency": row[4],
                        "context_type": row[5]
                    }
                    for row in (word_chains or [])
                ],
                "response_patterns": [
                    {
                        "input_pattern": row[1],
                        "response_template": row[2],
                        "success_rate": row[3],
                        "usage_count": row[4]
                    }
                    for row in (patterns or [])
                ],
                "personality_data": [
                    {
                        "user_id": row[0],
                        "trait_type": row[1],
                        "trait_value": row[2],
                        "confidence": row[3]
                    }
                    for row in (personality or [])
                ]
            }
            
            # Save to file
            with open("learning_export.json", "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
                
            # Send file
            await interaction.response.send_message(
                "✅ Learning data exported!",
                file=discord.File("learning_export.json"),
                ephemeral=True
            )
            
        except Exception as e:
            logging.error(f"Error exporting learning data: {e}")
            await interaction.response.send_message("❌ Failed to export learning data.", ephemeral=True)
            
    async def _backup_learning_data(self):
        """Create a backup of learning data"""
        try:
            # Create backup tables
            LearningData.execute_query("""
                CREATE TABLE IF NOT EXISTS word_chains_backup AS 
                SELECT * FROM word_chains
            """)
            
            LearningData.execute_query("""
                CREATE TABLE IF NOT EXISTS response_patterns_backup AS 
                SELECT * FROM response_patterns
            """)
            
            LearningData.execute_query("""
                CREATE TABLE IF NOT EXISTS user_personality_backup AS 
                SELECT * FROM user_personality
            """)
            
            return True
        except Exception as e:
            logging.error(f"Error creating learning backup: {e}")
            return False
            
    @app_commands.command(name="learning_health")
    async def learning_health(self, interaction: discord.Interaction):
        """Check the health of the learning system"""
        if not self._check_owner(interaction):
            await interaction.response.send_message("❌ This command is restricted to the bot owner.", ephemeral=True)
            return
            
        try:
            # Check database size
            db_stats = LearningData.execute_query(
                "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()",
                fetch=True
            )
            db_size = db_stats[0][0] if db_stats else 0
            
            # Check pattern quality
            pattern_stats = LearningData.execute_query(
                """
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN success_rate < 0.5 THEN 1 END) as low_success,
                    COUNT(CASE WHEN usage_count < 5 THEN 1 END) as low_usage
                FROM response_patterns
                """,
                fetch=True
            )
            
            # Create health report
            embed = discord.Embed(
                title="Learning System Health",
                color=discord.Color.green()
            )
            
            # Database size
            size_mb = db_size / (1024 * 1024)
            size_status = "🟢" if size_mb < 50 else "🟡" if size_mb < 100 else "🔴"
            embed.add_field(
                name="Database Size",
                value=f"{size_status} {size_mb:.1f}MB",
                inline=False
            )
            
            # Pattern health
            if pattern_stats and pattern_stats[0]:
                total = pattern_stats[0][0]
                low_success = pattern_stats[0][1]
                low_usage = pattern_stats[0][2]
                
                pattern_health = (
                    "🟢 Good" if low_success/total < 0.1 and low_usage/total < 0.3
                    else "🟡 Fair" if low_success/total < 0.2 and low_usage/total < 0.5
                    else "🔴 Poor"
                )
                
                embed.add_field(
                    name="Pattern Health",
                    value=f"{pattern_health}\nLow Success: {low_success:,} ({low_success/total:.1%})\nLow Usage: {low_usage:,} ({low_usage/total:.1%})",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logging.error(f"Error checking learning health: {e}")
            await interaction.response.send_message("❌ Failed to check learning system health.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(LearningCommands(bot)) 