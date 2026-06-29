from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.api.dependencies import get_container, get_session
from foundry.core.container import Container
from foundry.schemas import (
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionUpdate,
)

router = APIRouter(prefix="/chat/sessions", tags=["chat"])


@router.post(
    "",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_chat_session(
    payload: ChatSessionCreate,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> ChatSessionResponse:
    await container.pipelines.get(session, payload.pipeline_id)
    chat_session = await container.conversations.create(session, payload)
    return ChatSessionResponse.model_validate(chat_session)


@router.get("", response_model=list[ChatSessionResponse])
async def list_chat_sessions(
    pipeline_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> list[ChatSessionResponse]:
    if pipeline_id is not None:
        await container.pipelines.get(session, pipeline_id)
    chat_sessions = await container.conversations.list(session, pipeline_id)
    return [ChatSessionResponse.model_validate(item) for item in chat_sessions]


@router.get("/{session_id}/messages", response_model=list[ChatMessageResponse])
async def list_chat_messages(
    session_id: str,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> list[ChatMessageResponse]:
    messages = await container.conversations.list_messages(session, session_id)
    return [ChatMessageResponse.model_validate(item) for item in messages]


@router.patch("/{session_id}", response_model=ChatSessionResponse)
async def update_chat_session(
    session_id: str,
    payload: ChatSessionUpdate,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> ChatSessionResponse:
    chat_session = await container.conversations.update(session, session_id, payload)
    return ChatSessionResponse.model_validate(chat_session)


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_chat_session(
    session_id: str,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> Response:
    await container.conversations.delete(session, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
