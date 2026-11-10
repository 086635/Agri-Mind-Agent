from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text
import asyncio
import os

# PostgreSQL 连接配置
# 格式: postgresql+asyncpg://[user]:[password]@[host]:[port]/[dbname]
ASYNC_DATABASE_URL = os.getenv("ASYNC_DATABASE_URL", "postgresql+asyncpg://postgres:123456789@localhost:5432/agri_ai")
SYNC_DATABASE_URL = os.getenv("SYNC_DATABASE_URL", "postgresql://postgres:123456789@localhost:5432/agri_ai")

# 测试数据库连接
async def test_database_connection():
    """测试数据库连接"""
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

# 运行测试
if __name__ == "__main__":
    asyncio.run(test_database_connection())

# 创建异步数据库引擎
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    echo=False,  # 设为 True 可以看到 SQL 日志
    connect_args={
        "command_timeout": 30,
        "ssl": False
    }
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# 创建同步数据库引擎（用于兼容旧代码）
sync_engine = create_engine(
    SYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    connect_args={
        "connect_timeout": 30,
        "sslmode": "disable"
    }
)

# 创建同步会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

# 依赖注入：获取异步数据库会话
async def get_async_db():
    """
    异步数据库会话依赖注入
    使用示例：
        async with get_async_db() as db:
            result = await db.execute(query)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# 依赖注入：获取同步数据库会话（兼容旧代码）
def get_db():
    """
    同步数据库会话依赖注入（兼容旧代码）
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()