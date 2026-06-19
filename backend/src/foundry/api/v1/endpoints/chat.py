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
    result = await container.orchestrator.invoke(
        session, pipeline, payload.message, payload.strategy or pipeline.strategy
    )
    return ChatResponse.model_validate(result)


@router.post("/stream")
async def stream_chat(
    payload: ChatRequest,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> StreamingResponse:
    pipeline = await container.pipelines.get(session, payload.pipeline_id)
    return StreamingResponse(
        _sse_events(container, session, pipeline, payload.message, payload.strategy),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _sse_events(
    container: Container,
    session: AsyncSession,
    pipeline: Pipeline,
    message: str,
    strategy: str | None,
) -> AsyncIterator[str]:
    async for event in container.orchestrator.stream(
        session, pipeline, message, strategy or pipeline.strategy
    ):
        data = json.dumps(event["data"], ensure_ascii=False, default=str)
        yield f"event: {event['type']}\ndata: {data}\n\n"
