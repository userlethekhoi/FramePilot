from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.exceptions import DatabaseError
from app.infrastructure.config.settings import SettingsManager


class DatabaseEngine:
    """Manages the lifecycle of asynchronous connections to the SQLite database."""

    def __init__(self, settings_manager: SettingsManager) -> None:
        self._settings = settings_manager
        self._db_url = self._settings.get("database.url", "sqlite+aiosqlite:///mediaflow.db")
        self._echo = self._settings.get("database.echo", False)
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    def initialize(self) -> None:
        """Initializes the async engine and session factory."""
        if self._engine is not None:
            return

        try:
            # Special setup for SQLite to enable foreign keys and multithreading
            connect_args = {}
            if self._db_url.startswith("sqlite"):
                connect_args = {"check_same_thread": False}

            self._engine = create_async_engine(
                self._db_url,
                echo=self._echo,
                connect_args=connect_args,
                pool_pre_ping=True,
            )

            self._session_factory = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        except Exception as e:
            raise DatabaseError(f"Failed to initialize database connection: {e}") from e

    async def close(self) -> None:
        """Closes all database connections and disposes of the engine."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession]:
        """Provides an async context manager for safe database session operations.

        Yields:
            An active SQLAlchemy AsyncSession instance.
        """
        if self._session_factory is None:
            self.initialize()

        assert self._session_factory is not None
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise DatabaseError(f"Database transaction failed, changes rolled back: {e}") from e

    async def create_tables(self, base_metadata: Any) -> None:
        """Utility function to create database tables (useful for setup and testing)."""
        if self._engine is None:
            self.initialize()

        assert self._engine is not None
        try:
            async with self._engine.begin() as conn:
                await conn.run_sync(base_metadata.create_all)
        except Exception as e:
            raise DatabaseError(f"Failed to create database tables: {e}") from e


# Using typing import Any for base_metadata parameter validation
