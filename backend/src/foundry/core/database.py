from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create_schema(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            if connection.dialect.name == "postgresql":
                await connection.execute(
                    text(
                        "ALTER TABLE deployments ADD COLUMN IF NOT EXISTS "
                        "environment VARCHAR(24) DEFAULT 'preview'"
                    )
                )
            else:
                try:
                    await connection.execute(
                        text(
                            "ALTER TABLE deployments "
                            "ADD COLUMN environment VARCHAR(24) DEFAULT 'preview'"
                        )
                    )
                except (OperationalError, ProgrammingError):
                    pass
            await connection.execute(
                text(
                    "UPDATE deployments SET environment = status "
                    "WHERE status IN ('preview', 'production')"
                )
            )
            await connection.execute(
                text(
                    "UPDATE deployments SET status = 'running' "
                    "WHERE status IN ('preview', 'production')"
                )
            )

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def dispose(self) -> None:
        await self.engine.dispose()
