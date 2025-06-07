"""Async SQLModel session helpers."""

from __future__ import annotations

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlmodel import SQLModel, Session


DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/vibe",
)

if DATABASE_URL.startswith("sqlite"):  # fallback to sync driver for tests
    # create synchronous engine and wrap in async interface
    _sync_engine = create_engine(DATABASE_URL, echo=False, future=True)
    _sync_sessionmaker = sessionmaker(_sync_engine, expire_on_commit=False, class_=Session)

    class FakeAsyncSession:
        """Minimal async wrapper around a sync Session."""

        def __init__(self) -> None:
            self._session = _sync_sessionmaker()

        async def __aenter__(self) -> "FakeAsyncSession":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            self._session.close()

        def add(self, *args, **kwargs) -> None:  # pragma: no cover - passthrough
            self._session.add(*args, **kwargs)

        async def commit(self) -> None:
            self._session.commit()

        async def refresh(self, obj) -> None:
            self._session.refresh(obj)

        async def exec(self, statement):
            return self._session.exec(statement)

    def async_session_maker() -> FakeAsyncSession:  # noqa: D401 - factory
        """Return a new ``FakeAsyncSession``."""

        return FakeAsyncSession()

    async def init_db() -> None:
        SQLModel.metadata.create_all(_sync_engine)

    async def get_session() -> AsyncGenerator[FakeAsyncSession, None]:
        async with FakeAsyncSession() as session:
            yield session

    engine = _sync_engine
else:
    engine = create_async_engine(DATABASE_URL, echo=False, future=True)

    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async def init_db() -> None:
        from packages.core import models as _m  # noqa: WPS433

        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    async def get_session() -> AsyncGenerator[AsyncSession, None]:
        async with async_session_maker() as session:
            yield session


__all__ = ["engine", "async_session_maker", "init_db", "get_session"]

