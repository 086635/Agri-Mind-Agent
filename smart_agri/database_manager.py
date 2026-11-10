import aiosqlite
import os
from typing import Optional, Dict, Any

class DatabaseManager:
    _instance: Optional['DatabaseManager'] = None
    _db_path: str
    _connection: Optional[aiosqlite.Connection] = None
    
    def __new__(cls, db_path: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            if db_path:
                cls._instance._db_path = db_path
            else:
                cls._instance._db_path = os.path.join(os.path.dirname(__file__), "SQL", "farm_data.db")
        return cls._instance
    
    async def connect(self):
        if self._connection is None or self._connection._conn is None:
            self._connection = await aiosqlite.connect(self._db_path)
            await self._init_tables()
        return self._connection
    
    async def _init_tables(self):
        conn = await self.connect()
        await conn.execute('''
        CREATE TABLE IF NOT EXISTS sensor_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            temp REAL,
            humid REAL,
            light REAL,
            soil_status INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        await conn.commit()
    
    async def execute(self, query: str, params: tuple = ()) -> aiosqlite.Cursor:
        conn = await self.connect()
        return await conn.execute(query, params)
    
    async def executemany(self, query: str, params: list) -> aiosqlite.Cursor:
        conn = await self.connect()
        return await conn.executemany(query, params)
    
    async def fetchone(self, query: str, params: tuple = ()) -> Optional[tuple]:
        cursor = await self.execute(query, params)
        return await cursor.fetchone()
    
    async def fetchall(self, query: str, params: tuple = ()) -> list:
        cursor = await self.execute(query, params)
        return await cursor.fetchall()
    
    async def commit(self):
        if self._connection:
            await self._connection.commit()
    
    async def close(self):
        if self._connection:
            await self._connection.close()
            self._connection = None

# 创建全局实例
db_manager = DatabaseManager()
