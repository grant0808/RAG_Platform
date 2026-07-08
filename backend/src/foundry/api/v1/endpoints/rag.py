from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.api.dependencies import get_container, get_session
from foundry.core.container import Container
from foundry.schemas import ChatRequest, ChatResponse, SourceResponse

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/query", response_model=ChatResponse)
async def query_rag(
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
    user_message = await container.conversations.add_message(
        session,
        session_id=chat_session.id,
        role="user",
        content=str(payload.message),
        metadata={"route": "pending", "selected_tool": "none", "sources": []},
    )
    history = await container.conversations.history(
        session,
        chat_session.id,
        limit=container.settings.memory_window_size,
        exclude_message_id=user_message.id,
    )
    result = await container.orchestrator.invoke(
        session,
        pipeline,
        str(payload.message),
        payload.strategy or pipeline.strategy,
        history=[(turn.role, turn.content) for turn in history],
    )
    result["session_id"] = chat_session.id
    result["conversation_id"] = chat_session.id
    message = await container.conversations.add_message(
        session,
        session_id=chat_session.id,
        role="assistant",
        content=str(result["answer"]),
        metadata={
            "strategy": result["strategy"],
            "route": result.get("route"),
            "selected_tool": result.get("selected_tool"),
            "cached": result["cached"],
            "citations": result["citations"],
            "contexts": result.get("contexts", []),
            "web_results": result.get("web_results", []),
            "sources": result.get("sources", []),
            "trace": result["trace"],
            "usage": result["usage"],
            "memory_used": result.get("memory_used", False),
            "history_count": result.get("history_count", 0),
        },
    )
    result["message_id"] = message.id
    return ChatResponse.model_validate(result)


@router.post("/index", status_code=status.HTTP_202_ACCEPTED)
async def index_rag_sources(
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> dict[str, str]:
    await container.sources.rebuild(session)
    return {"status": "accepted"}


@router.get("/sources", response_model=list[SourceResponse])
async def list_rag_sources(
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> list[SourceResponse]:
    return [SourceResponse.model_validate(item) for item in await container.sources.list(session)]
