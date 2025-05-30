import aiosqlite
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger('chinatsu.db')

class AsyncDatabase:
    def __init__(self, db_path: str = "data/chinatsu.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._connection: Optional[aiosqlite.Connection] = None
        
    async def connect(self):
        """Create database connection"""
        if not self._connection:
            try:
                self._connection = await aiosqlite.connect(self.db_path)
                self._connection.row_factory = aiosqlite.Row
                logger.info(f"Connected to database at {self.db_path}")
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                raise
                
    async def disconnect(self):
        """Close database connection"""
        if self._connection:
            await self._connection.close()
            self._connection = None
            
    async def execute(self, query: str, params: tuple = ()):
        """Execute a query"""
        if not self._connection:
            await self.connect()
        try:
            async with self._connection.cursor() as cursor:
                await cursor.execute(query, params)
                await self._connection.commit()
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
            
    async def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Fetch a single row"""
        if not self._connection:
            await self.connect()
        try:
            async with self._connection.cursor() as cursor:
                result = await cursor.execute(query, params)
                row = await result.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to fetch row: {e}")
            raise
            
    async def fetch_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Fetch all rows"""
        if not self._connection:
            await self.connect()
        try:
            async with self._connection.cursor() as cursor:
                result = await cursor.execute(query, params)
                rows = await result.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to fetch rows: {e}")
            raise 