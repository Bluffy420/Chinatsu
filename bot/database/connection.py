import sqlite3
import threading
import time
import logging
from typing import Optional, Dict
from contextlib import contextmanager
from ..config import get_db_settings, DB_PATH

class DatabaseConnectionManager:
    """Thread-safe database connection manager optimized for Replit"""
    
    def __init__(self):
        self._connections: Dict[int, sqlite3.Connection] = {}
        self._lock = threading.Lock()
        self._settings = get_db_settings()
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutes
        
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection with optimized settings"""
        conn = sqlite3.connect(
            DB_PATH,
            timeout=self._settings["connection_timeout"]
        )
        
        # Optimize connection settings
        conn.execute(f"PRAGMA journal_mode = {self._settings['journal_mode']}")
        conn.execute(f"PRAGMA cache_size = {self._settings['cache_size']}")
        conn.execute(f"PRAGMA page_size = {self._settings['page_size']}")
        conn.execute(f"PRAGMA temp_store = {self._settings['temp_store']}")
        conn.execute("PRAGMA synchronous = NORMAL")
        
        return conn
        
    def _cleanup_old_connections(self):
        """Clean up unused connections to free memory"""
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return
            
        with self._lock:
            for thread_id in list(self._connections.keys()):
                try:
                    self._connections[thread_id].execute("SELECT 1")
                except (sqlite3.Error, Exception):
                    try:
                        self._connections[thread_id].close()
                    except Exception:
                        pass
                    del self._connections[thread_id]
            
        self._last_cleanup = current_time
        
    @contextmanager
    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection for the current thread"""
        thread_id = threading.get_ident()
        
        # Clean up old connections periodically
        self._cleanup_old_connections()
        
        with self._lock:
            # Check if we need to create a new connection
            if thread_id not in self._connections:
                # Limit total connections
                if len(self._connections) >= self._settings["max_connections"]:
                    # Remove oldest connection if we're at the limit
                    oldest_thread = next(iter(self._connections))
                    try:
                        self._connections[oldest_thread].close()
                    except Exception:
                        pass
                    del self._connections[oldest_thread]
                
                # Create new connection
                self._connections[thread_id] = self._create_connection()
            
            connection = self._connections[thread_id]
        
        try:
            yield connection
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                # Handle database locks gracefully
                logging.warning("Database lock detected, retrying operation...")
                time.sleep(1)
                yield connection
            else:
                raise
        except Exception as e:
            logging.error(f"Database error: {e}")
            raise
        finally:
            # Commit any pending transactions
            try:
                connection.commit()
            except Exception as e:
                logging.error(f"Error committing transaction: {e}")
                
    def close_all(self):
        """Close all database connections"""
        with self._lock:
            for conn in self._connections.values():
                try:
                    conn.close()
                except Exception:
                    pass
            self._connections.clear()
            
# Global connection manager instance
db_manager = DatabaseConnectionManager() 