from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.core.container import Container


def get_container(request: Request) -> Container:
    return request.app.state.container


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    container: Container = request.app.state.container
    async for session in container.database.session():
        yield session
