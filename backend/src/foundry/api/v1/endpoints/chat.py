import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.api.dependencies import get_container, get_session
from foundry.core.container import Container
from foundry.models import Pipeline
from foundry.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> ChatResponse:
    pipeline = await container.pipelines.get(session, payload.pipeline_id)
    chat_session = await container.conversations.ensure(
        session,
        pipeline_id=pipeline.id,
        session_id=payload.session_id,
        title_seed=payload.message,
    )
    history = await container.conversations.history(session, chat_session.id)
    await container.conversations.add_message(
        session,
        session_id=chat_session.id,
        role="user",
        content=payload.message,
    )
    result = await container.orchestrator.invoke(
        session,
        pipeline,
        payload.message,
        payload.strategy or pipeline.strategy,
        history=[(turn.role, turn.content) for turn in history],
    )
    result["session_id"] = chat_session.id
    await container.conversations.add_message(
        session,
        session_id=chat_session.id,
        role="assistant",
        content=str(result["answer"]),
        metadata={
            "strategy": result["strategy"],
            "cached": result["cached"],
            "citations": result["citations"],
            "trace": result["trace"],
            "usage": result["usage"],
        },
    )
    return ChatResponse.model_validate(result)


@router.post("/stream")
async def stream_chat(
    payload: ChatRequest,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> StreamingResponse:
    pipeline = await container.pipelines.get(session, payload.pipeline_id)
    chat_session = await container.conversations.ensure(
        session,
        pipeline_id=pipeline.id,
        session_id=payload.session_id,
        title_seed=payload.message,
    )
    history = await container.conversations.history(session, chat_session.id)
    await container.conversations.add_message(
        session,
        session_id=chat_session.id,
        role="user",
        content=payload.message,
    )
    return StreamingResponse(
        _sse_events(
            container,
            session,
            pipeline,
            payload.message,
            payload.strategy,
            chat_session.id,
            [(turn.role, turn.content) for turn in history],
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _sse_events(
    container: Container,
    session: AsyncSession,
    pipeline: Pipeline,
    message: str,
    strategy: str | None,
    chat_session_id: str,
    history: list[tuple[str, str]],
) -> AsyncIterator[str]:
    async for event in container.orchestrator.stream(
        session,
        pipeline,
        message,
        strategy or pipeline.strategy,
        history=history,
    ):
        if event["type"] == "done":
            event["data"]["session_id"] = chat_session_id
            await container.conversations.add_message(
                session,
                session_id=chat_session_id,
                role="assistant",
                content=str(event["data"]["answer"]),
                metadata={
                    "strategy": event["data"]["strategy"],
                    "cached": event["data"]["cached"],
                    "citations": event["data"]["citations"],
                    "trace": event["data"]["trace"],
                    "usage": event["data"]["usage"],
                },
            )
        data = json.dumps(event["data"], ensure_ascii=False, default=str)
        yield f"event: {event['type']}\ndata: {data}\n\n"
