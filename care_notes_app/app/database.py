from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models import Base

# Database connection URL (using SQLite with aiosqlite driver)
DATABASE_URL = "sqlite+aiosqlite:///./care_notes.db"

# Create an async engine instance for SQLAlchemy
engine = create_async_engine(DATABASE_URL, echo=False)

# Create an async session factory
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    """
    Dependency that provides a new SQLAlchemy AsyncSession for each request.
    Used with FastAPI's Depends system. 
    """
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    """
    Initialize the database by creating all tables defined in the models (if they don't exist).
    Should be called at application startup.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)