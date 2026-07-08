from typing import Any

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
conversation_router = APIRouter(prefix="/conversations", tags=["conversations"])


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


@conversation_router.post("", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ChatSessionCreate,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    chat_session = await create_chat_session(payload, session, container)
    return {
        "conversation_id": chat_session.id,
        "session_id": chat_session.id,
        "pipeline_id": chat_session.pipeline_id,
        "title": chat_session.title,
        "created_at": chat_session.created_at,
        "updated_at": chat_session.updated_at,
    }


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


@conversation_router.get("")
async def list_conversations(
    pipeline_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> list[dict[str, Any]]:
    chat_sessions = await list_chat_sessions(pipeline_id, session, container)
    return [
        {
            "conversation_id": item.id,
            "session_id": item.id,
            "pipeline_id": item.pipeline_id,
            "title": item.title,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
        for item in chat_sessions
    ]


@router.get("/{session_id}/messages", response_model=list[ChatMessageResponse])
async def list_chat_messages(
    session_id: str,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> list[ChatMessageResponse]:
    messages = await container.conversations.list_messages(session, session_id)
    return [_message_response(item) for item in messages]


@conversation_router.get("/{conversation_id}/messages", response_model=list[ChatMessageResponse])
async def list_conversation_messages(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> list[ChatMessageResponse]:
    return await list_chat_messages(conversation_id, session, container)


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


def _message_response(message: Any) -> ChatMessageResponse:
    metadata = message.message_metadata or {}
    return ChatMessageResponse(
        id=message.id,
        message_id=message.id,
        session_id=message.session_id,
        conversation_id=message.session_id,
        role=message.role,
        content=message.content,
        message_metadata=metadata,
        route=metadata.get("route") if isinstance(metadata.get("route"), str) else None,
        selected_tool=metadata.get("selected_tool")
        if isinstance(metadata.get("selected_tool"), str)
        else None,
        sources=metadata.get("sources") if isinstance(metadata.get("sources"), list) else [],
        created_at=message.created_at,
    )
