from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text
import asyncio
import os

ASYNC_DATABASE_URL = os.getenv("ASYNC_DATABASE_URL", "postgresql+asyncpg://postgres:Ysw%4088516251@localhost:5432/agri_ai")
SYNC_DATABASE_URL = os.getenv("SYNC_DATABASE_URL", "postgresql://postgres:Ysw%4088516251@localhost:5432/agri_ai")

async def test_database_connection():
    try:
        print("[TEST] 测试异步数据库连接...")
        async with create_async_engine(ASYNC_DATABASE_URL).connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            print(f"[TEST] 异步连接成功: {result.scalar()}")
    except Exception as e:
        print(f"[TEST] 异步连接失败: {e}")
    
    try:
        print("[TEST] 测试同步数据库连接...")
        with create_engine(SYNC_DATABASE_URL).connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print(f"[TEST] 同步连接成功: {result.scalar()}")
    except Exception as e:
        print(f"[TEST] 同步连接失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_database_connection())

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    echo=False,
    connect_args={
        "command_timeout": 30,
        "ssl": False
    }
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

sync_engine = create_engine(
    SYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    connect_args={
        "connect_timeout": 30,
        "sslmode": "disable"
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

async def get_async_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
