import os
import logging
from pathlib import Path

logger = logging.getLogger('chinatsu.replit')

def setup_replit_env():
    """Setup Replit-specific environment"""
    # Ensure data directory exists
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    # Set up environment variables if not already set
    if not os.getenv('DISCORD_TOKEN'):
        logger.warning("DISCORD_TOKEN not found in environment variables!")
        
    return True

def get_replit_db_url():
    """Get Replit database URL if available"""
    return os.getenv('REPLIT_DB_URL')

def is_replit_env():
    """Check if running in Replit environment"""
    return bool(os.getenv('REPL_ID') and os.getenv('REPL_OWNER')) 