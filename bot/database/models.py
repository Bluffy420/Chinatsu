from typing import List, Dict, Any, Optional
from pathlib import Path
import sqlite3
import json
import time

class Database:
    def __init__(self, db_path: str = "chinatsu.db"):
        self.db_path = db_path
        self.setup_database()
        
    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection with proper settings"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
        
    def setup_database(self):
        """Create database tables if they don't exist"""
        with self.get_connection() as conn:
            # User relations table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS relations_users (
                    user_id INTEGER PRIMARY KEY,
                    reputation INTEGER DEFAULT 0,
                    interactions INTEGER DEFAULT 0,
                    last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Conversation log with sentiment
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    user_message TEXT,
                    bot_response TEXT,
                    sentiment_score REAL DEFAULT 0,
                    sentiment_reasons TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES relations_users(user_id)
                )
            """)
            
            # User personality traits
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_personality (
                    user_id INTEGER,
                    trait_type TEXT,
                    trait_value TEXT,
                    confidence REAL DEFAULT 0.1,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, trait_type),
                    FOREIGN KEY (user_id) REFERENCES relations_users(user_id)
                )
            """)
            
            # Response patterns
            conn.execute("""
                CREATE TABLE IF NOT EXISTS response_patterns (
                    input_pattern TEXT PRIMARY KEY,
                    response_template TEXT,
                    success_rate REAL DEFAULT 0.0,
                    usage_count INTEGER DEFAULT 0,
                    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Dialogue patterns from manga
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dialogue_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    context_type TEXT,
                    input_pattern TEXT,
                    response_template TEXT,
                    emotion TEXT DEFAULT 'neutral',
                    usage_count INTEGER DEFAULT 1,
                    source TEXT DEFAULT 'blue_box',
                    chapter INTEGER,
                    page INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(input_pattern, response_template)
                )
            """)
            
            # Character traits and personality
            conn.execute("""
                CREATE TABLE IF NOT EXISTS character_traits (
                    trait_type TEXT,
                    trait_name TEXT,
                    trait_value REAL DEFAULT 0.5,
                    confidence REAL DEFAULT 1.0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (trait_type, trait_name)
                )
            """)
            
            conn.commit()

class UserRelations(Database):
    """Model for user relations and reputation"""
    
    @classmethod
    def get_user(cls, user_id: int) -> Dict[str, Any]:
        """Get user data, creating if doesn't exist"""
        with cls().get_connection() as conn:
            # Try to get existing user
            result = conn.execute(
                "SELECT * FROM relations_users WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            
            if not result:
                # Create new user
                conn.execute(
                    "INSERT INTO relations_users (user_id) VALUES (?)",
                    (user_id,)
                )
                conn.commit()
                result = conn.execute(
                    "SELECT * FROM relations_users WHERE user_id = ?",
                    (user_id,)
                ).fetchone()
                
            return dict(result)
            
    @classmethod
    def execute_query(cls, query: str, params: tuple = ()):
        """Execute a database query"""
        with cls().get_connection() as conn:
            result = conn.execute(query, params)
            conn.commit()
            return result

class LearningData(Database):
    """Model for bot's learning data"""
    
    @classmethod
    def execute_query(cls, query: str, params: tuple = (), fetch: bool = False):
        """Execute a database query with optional fetch"""
        with cls().get_connection() as conn:
            result = conn.execute(query, params)
            conn.commit()
            return result.fetchall() if fetch else result

class ServerSettings(Database):
    """Model for server-specific settings"""
    
    @classmethod
    def initialize_tables(cls):
        # Server activation status
        cls.execute_query('''
            CREATE TABLE IF NOT EXISTS server_activation (
                server_id TEXT PRIMARY KEY,
                active INTEGER DEFAULT 1,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Channel activation status
        cls.execute_query('''
            CREATE TABLE IF NOT EXISTS channel_activation (
                channel_id TEXT PRIMARY KEY,
                active INTEGER DEFAULT 1,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Content filter settings
        cls.execute_query('''
            CREATE TABLE IF NOT EXISTS filter_settings (
                server_id TEXT PRIMARY KEY,
                filter_enabled INTEGER DEFAULT 1,
                mature_enabled INTEGER DEFAULT 0,
                mature_level INTEGER DEFAULT 1,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

def initialize_database():
    """Initialize all database tables"""
    UserRelations.execute_query('''
        CREATE TABLE IF NOT EXISTS relations_users (
            user_id INTEGER PRIMARY KEY,
            reputation INTEGER DEFAULT 0,
            interactions INTEGER DEFAULT 0,
            last_interaction DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    LearningData.execute_query('''
        CREATE TABLE IF NOT EXISTS word_chains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word1 TEXT,
            word2 TEXT,
            next_word TEXT,
            frequency INTEGER DEFAULT 1,
            context_type TEXT DEFAULT 'general',
            UNIQUE(word1, word2, next_word, context_type)
        )
    ''')
    ServerSettings.execute_query('''
        CREATE TABLE IF NOT EXISTS response_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            input_pattern TEXT,
            response_template TEXT,
            success_rate REAL DEFAULT 0.0,
            usage_count INTEGER DEFAULT 0,
            last_used DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    ServerSettings.execute_query('''
        CREATE TABLE IF NOT EXISTS user_personality (
            user_id INTEGER,
            trait_type TEXT,
            trait_value TEXT,
            confidence REAL DEFAULT 1.0,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, trait_type)
        )
    ''')
    ServerSettings.execute_query("CREATE INDEX IF NOT EXISTS idx_word_chains ON word_chains(word1, word2)")
    ServerSettings.execute_query("CREATE INDEX IF NOT EXISTS idx_patterns ON response_patterns(input_pattern)")
    ServerSettings.execute_query('''
        CREATE TABLE IF NOT EXISTS server_activation (
            server_id TEXT PRIMARY KEY,
            active INTEGER DEFAULT 1,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    ServerSettings.execute_query('''
        CREATE TABLE IF NOT EXISTS channel_activation (
            channel_id TEXT PRIMARY KEY,
            active INTEGER DEFAULT 1,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    ServerSettings.execute_query('''
        CREATE TABLE IF NOT EXISTS filter_settings (
            server_id TEXT PRIMARY KEY,
            filter_enabled INTEGER DEFAULT 1,
            mature_enabled INTEGER DEFAULT 0,
            mature_level INTEGER DEFAULT 1,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    ServerSettings.execute_query('''
        CREATE TABLE IF NOT EXISTS conversation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_message TEXT,
            bot_response TEXT,
            sentiment_score REAL DEFAULT 0,
            sentiment_reasons TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES relations_users(user_id)
        )
    ''') 