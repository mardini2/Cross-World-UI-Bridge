"""
Goal: Provide a tiny SQLite database using SQLAlchemy (async) for settings and recent commands.
We keep it simple and safe.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.settings import DB_PATH

# Build async engine pointing to our local DB file
engine: AsyncEngine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}", echo=False, future=True)
Base = declarative_base()
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String, nullable=False)

class RecentCommand(Base):
    __tablename__ = "recent_commands"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

async def init_db() -> None:
    # One-shot table create; fine for local usage
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
