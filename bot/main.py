import discord
from discord.ext import commands
import os
import logging
from pathlib import Path
from .database.models import LearningData
from .services.dialogue_training import DialogueTrainer

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('chinatsu')

class ChinatsuBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=commands.DefaultHelpCommand()
        )
        
        self.dialogue_trainer = DialogueTrainer()
        self.ready = False
        
    async def setup_hook(self):
        """Setup hook that runs before the bot starts"""
        # Load all cogs
        await self.load_extensions()
        
        # Initialize database
        await self.init_database()
        
    async def load_extensions(self):
        """Load all cog extensions"""
        cogs_dir = Path(__file__).parent / 'cogs'
        for cog_file in cogs_dir.glob('*.py'):
            if cog_file.stem != '__init__':
                try:
                    await self.load_extension(f'bot.cogs.{cog_file.stem}')
                    logger.info(f'Loaded extension: {cog_file.stem}')
                except Exception as e:
                    logger.error(f'Failed to load extension {cog_file.stem}: {e}')
    
    async def init_database(self):
        """Initialize the database connection and tables"""
        try:
            await LearningData.init_db()
            logger.info('Database initialized successfully')
        except Exception as e:
            logger.error(f'Failed to initialize database: {e}')
    
    async def on_ready(self):
        """Event handler for when the bot is ready"""
        if self.ready:
            return
            
        self.ready = True
        logger.info(f'Logged in as {self.user.name} (ID: {self.user.id})')
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="and learning! | !help"
            )
        )
    
    async def on_message(self, message):
        """Event handler for processing messages"""
        # Ignore messages from the bot itself
        if message.author == self.user:
            return
            
        # Process commands first
        await self.process_commands(message)
        
        # If not a command and not in DMs, process as dialogue
        if not message.content.startswith(self.command_prefix) and message.guild:
            # Add message to learning data if appropriate
            if message.content and len(message.content) > 3:
                self.dialogue_trainer.add_dialogue_entry(
                    context="general",
                    dialogue=message.content
                )

def run_bot():
    """Initialize and run the bot"""
    bot = ChinatsuBot()
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        raise ValueError("No Discord token found in environment variables!")
    bot.run(token, log_handler=None)  # Disable default discord.py logging 