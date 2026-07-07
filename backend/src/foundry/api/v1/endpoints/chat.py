import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.api.dependencies import get_container, get_session
from foundry.core.container import Container
from foundry.models import Pipeline
from foundry.schemas import ChatRequest, ChatResponse
from foundry.services.conversations import TokenStatus

router = APIRouter(prefix="/chat", tags=["chat"])
rag_router = APIRouter(prefix="/rag", tags=["rag"])


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
    if _is_status_command(payload.message):
        result = await _status_result(container, session, chat_session.id)
        await container.conversations.add_message(
            session,
            session_id=chat_session.id,
            role="assistant",
            content=str(result["answer"]),
            metadata={
                "strategy": result["strategy"],
                "route": result.get("route"),
                "cached": result["cached"],
                "citations": result["citations"],
                "contexts": result.get("contexts", []),
                "sources": result.get("sources", []),
                "trace": result["trace"],
                "usage": result["usage"],
                "command": "status",
                "token_status": result["token_status"],
                "provider_quota": result["provider_quota"],
            },
        )
        return ChatResponse.model_validate(result)

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
            "route": result.get("route"),
            "contexts": result.get("contexts", []),
            "sources": result.get("sources", []),
            "trace": result["trace"],
            "usage": result["usage"],
        },
    )
    return ChatResponse.model_validate(result)


@router.post("/query", response_model=ChatResponse)
async def query_chat(
    payload: ChatRequest,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> ChatResponse:
    return await chat(payload, session, container)


@rag_router.post("/query", response_model=ChatResponse)
async def query_rag(
    payload: ChatRequest,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> ChatResponse:
    return await chat(payload, session, container)


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
    if _is_status_command(payload.message):
        return StreamingResponse(
            _status_sse_events(container, session, chat_session.id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
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
    try:
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
                        "route": event["data"].get("route"),
                        "cached": event["data"]["cached"],
                        "citations": event["data"]["citations"],
                        "contexts": event["data"].get("contexts", []),
                        "sources": event["data"].get("sources", []),
                        "trace": event["data"]["trace"],
                        "usage": event["data"]["usage"],
                    },
                )
            data = json.dumps(event["data"], ensure_ascii=False, default=str)
            yield f"event: {event['type']}\ndata: {data}\n\n"
    except Exception as exc:
        data = json.dumps(
            {"message": f"Runtime execution failed: {exc}"},
            ensure_ascii=False,
            default=str,
        )
        yield f"event: error\ndata: {data}\n\n"


async def _status_sse_events(
    container: Container,
    session: AsyncSession,
    chat_session_id: str,
) -> AsyncIterator[str]:
    result = await _status_result(container, session, chat_session_id)
    yield f"event: token\ndata: {json.dumps({'text': result['answer']}, ensure_ascii=False)}\n\n"
    await container.conversations.add_message(
        session,
        session_id=chat_session_id,
        role="assistant",
        content=str(result["answer"]),
        metadata={
            "strategy": result["strategy"],
            "cached": result["cached"],
            "citations": result["citations"],
            "trace": result["trace"],
            "usage": result["usage"],
            "command": "status",
            "token_status": result["token_status"],
            "provider_quota": result["provider_quota"],
        },
    )
    data = json.dumps(result, ensure_ascii=False, default=str)
    yield f"event: done\ndata: {data}\n\n"


async def _status_result(
    container: Container,
    session: AsyncSession,
    chat_session_id: str,
) -> dict[str, object]:
    status = await container.conversations.token_status(
        session,
        chat_session_id,
        container.settings.chat_session_token_budget,
    )
    provider_quota = await container.provider_quota.status()
    return {
        "session_id": chat_session_id,
        "answer": _status_answer(status, provider_quota),
        "strategy": "status",
        "provider": "system",
        "model": "local-command",
        "citations": [],
        "trace": [],
        "usage": {},
        "cached": False,
        "token_status": {
            "budget": status.budget,
            "used_total": status.used_total,
            "used_input": status.used_input,
            "used_output": status.used_output,
            "remaining": status.remaining,
            "message_count": status.message_count,
        },
        "provider_quota": provider_quota,
    }


def _status_answer(status: TokenStatus, provider_quota: dict[str, Any]) -> str:
    percent = round((status.used_total / status.budget) * 100, 2) if status.budget else 0
    return (
        "Session token status\n"
        f"- Budget: {status.budget:,} tokens\n"
        f"- Used total: {status.used_total:,} tokens ({percent}%)\n"
        f"- Input tokens: {status.used_input:,}\n"
        f"- Output tokens: {status.used_output:,}\n"
        f"- Remaining: {status.remaining:,} tokens\n"
        f"- Counted assistant responses: {status.message_count}\n\n"
        "Provider quota status\n"
        f"- Period: {_nested(provider_quota, 'period', 'start')} ~ "
        f"{_nested(provider_quota, 'period', 'end')}\n"
        f"- OpenAI: {_provider_status_line(provider_quota.get('openai'))}\n"
        f"- Anthropic: {_provider_status_line(provider_quota.get('anthropic'))}"
    )


def _is_status_command(message: str) -> bool:
    return message.strip().lower() == "/status"


def _provider_status_line(provider: object) -> str:
    if not isinstance(provider, dict):
        return "unavailable"
    if not provider.get("configured"):
        return str(provider.get("reason", "admin key not configured"))

    usage = provider.get("usage") if isinstance(provider.get("usage"), dict) else {}
    cost = provider.get("cost") if isinstance(provider.get("cost"), dict) else {}
    remaining = provider.get("remaining") if isinstance(provider.get("remaining"), dict) else {}

    parts: list[str] = []
    if usage.get("available"):
        parts.append(f"used {_format_number(usage.get('total_tokens'))} tokens")
    else:
        parts.append(f"usage unavailable ({usage.get('error', 'unknown error')})")

    if cost.get("available"):
        parts.append(
            f"cost {_format_number(cost.get('amount'))} {str(cost.get('currency', 'USD'))}"
        )
    else:
        parts.append(f"cost unavailable ({cost.get('error', 'unknown error')})")

    if remaining.get("available"):
        if "remaining_usd" in remaining:
            parts.append(f"remaining {_format_number(remaining.get('remaining_usd'))} USD")
        else:
            parts.append("remaining available")
    else:
        parts.append(f"remaining unavailable ({remaining.get('reason', 'not exposed')})")

    return "; ".join(parts)


def _nested(payload: dict[str, Any], *keys: str) -> object:
    value: object = payload
    for key in keys:
        if not isinstance(value, dict):
            return "-"
        value = value.get(key, "-")
    return value


def _format_number(value: object) -> str:
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.6f}".rstrip("0").rstrip(".")
    return "0"
