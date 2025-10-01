"""
Goal: Minimal async SQLite setup with SQLAlchemy 2.0 types that make mypy happy.
We expose:
  - engine: AsyncEngine
  - SessionLocal: async_sessionmaker[AsyncSession]
  - Base: Declarative base with proper typing
  - KV model (tiny key/value table for local settings)
  - init_db(): create tables on startup
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.ext.asyncio import (AsyncEngine, AsyncSession,
                                    async_sessionmaker, create_async_engine)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.settings import DB_PATH

# --- Declarative base with proper typing -------------------------------------


class Base(DeclarativeBase):
    """Typed declarative base."""


# --- Example tiny model (handy for future flags/secrets metadata) ------------


class KV(Base):
    __tablename__ = "kv"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# --- Engine + sessionmaker (async) -------------------------------------------

# Ensure the folder exists (DB_PATH is a file path)
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

engine: AsyncEngine = create_async_engine(
    f"sqlite+aiosqlite:///{DB_PATH}",
    future=True,
    echo=False,
)

# Typed async session factory
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


# --- Lifecycle ---------------------------------------------------------------


async def init_db() -> None:
    """Create tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
