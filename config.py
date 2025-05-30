import os
from typing import Dict, Any

# Replit-specific settings
REPLIT_DB_URL = os.getenv("REPLIT_DB_URL", "")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

# Database settings
DB_PATH = os.path.join(os.getcwd(), "chinatsu-brain.db")
DB_BACKUP_PATH = os.path.join(os.getcwd(), "chinatsu-brain.backup.db")

# Performance settings for Replit
DB_SETTINGS = {
    "connection_timeout": 30.0,  # Longer timeout for Replit's environment
    "max_connections": 3,        # Limit connections to save memory
    "journal_mode": "WAL",       # Write-Ahead Logging for better concurrency
    "cache_size": -2 * 1024,    # 2MB cache size (-ve means kibibytes)
    "page_size": 4096,          # Optimal for most systems
    "temp_store": 2,            # Store temp tables in memory
}

# Memory optimization
CACHE_SETTINGS = {
    "max_size": 1000,           # Maximum items in cache
    "ttl": 3600,               # Cache TTL in seconds
    "cleanup_interval": 300     # Cleanup every 5 minutes
}

# Content generation limits
GENERATION_LIMITS = {
    "max_response_length": 2000,  # Discord message limit
    "max_context_length": 4096,   # Limit context to save memory
    "max_learning_entries": 10000  # Limit learning database size
}

# Backup settings
BACKUP_SETTINGS = {
    "interval": 3600,           # Backup every hour
    "keep_backups": 2,          # Number of backups to keep
    "max_backup_size": 50 * 1024 * 1024  # 50MB max backup size
}

def get_db_url() -> str:
    """Get the appropriate database URL based on environment"""
    return REPLIT_DB_URL if REPLIT_DB_URL else f"sqlite:///{DB_PATH}"

def get_db_settings() -> Dict[str, Any]:
    """Get database settings with environment-specific optimizations"""
    settings = DB_SETTINGS.copy()
    
    # Adjust settings if running on Replit
    if REPLIT_DB_URL:
        settings.update({
            "max_connections": 2,  # Even more conservative on Replit
            "cache_size": -1 * 1024,  # 1MB cache on Replit
            "temp_store": 1  # Use files for temp storage on Replit
        })
    
    return settings

def init_replit_storage():
    """Initialize storage directories for Replit environment"""
    try:
        # Ensure base directory exists
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        # Create backup directory if needed
        backup_dir = os.path.dirname(DB_BACKUP_PATH)
        if backup_dir:
            os.makedirs(backup_dir, exist_ok=True)
            
        return True
    except Exception as e:
        print(f"Error initializing Replit storage: {e}")
        return False 