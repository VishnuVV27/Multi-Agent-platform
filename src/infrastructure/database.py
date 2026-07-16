from sqlalchemy import create_engine, Engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool

from src.config import settings

# Import ORM models so they register with Base
from src.models.memory import WorkflowMemoryORM

# Declarative base for all ORM models
Base = declarative_base()

# Sync engine for basic operations
_sync_engine: Engine | None = None

# Async engine for async operations
_async_engine: AsyncEngine | None = None

# Async session factory
AsyncSessionLocal = None


def get_db_engine() -> Engine:
    """Get or create the synchronous database engine."""
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(
            settings.DATABASE_URL,
            echo=settings.API_ENVIRONMENT == "development",
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
    return _sync_engine


async def get_async_engine() -> AsyncEngine:
    """Get or create the asynchronous database engine."""
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
            echo=settings.API_ENVIRONMENT == "development",
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            poolclass=NullPool,
        )
    return _async_engine


async def init_db():
    """Initialize database connection and create tables."""
    try:
        engine = await get_async_engine()

        # Create all tables from models
        async with engine.begin() as conn:
            # Enable pgvector extension (for embeddings)
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                print("✅ pgvector extension enabled")
            except Exception as e:
                print(f"⚠️  pgvector extension creation warning: {e}")

            # Create all tables
            await conn.run_sync(Base.metadata.create_all)

            # Create vector index for fast similarity search (HNSW)
            try:
                await conn.execute(
                    text("""
                    CREATE INDEX IF NOT EXISTS workflow_memories_embedding_idx
                    ON workflow_memories USING hnsw (request_embedding vector_cosine_ops)
                    WITH (m=16, ef_construction=64)
                    """)
                )
                print("✅ Vector index created")
            except Exception as e:
                print(f"⚠️  Vector index creation warning: {e}")

        print("✅ Database initialized")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        raise


async def get_async_session() -> AsyncSession:
    """Get an async database session."""
    global AsyncSessionLocal
    if AsyncSessionLocal is None:
        engine = await get_async_engine()
        AsyncSessionLocal = sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    async with AsyncSessionLocal() as session:
        yield session


def get_sync_session():
    """Get a synchronous database session."""
    engine = get_db_engine()
    SessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )
    return SessionLocal()


def get_db():
    """Get a synchronous database session (alias for get_sync_session)."""
    return get_sync_session()
