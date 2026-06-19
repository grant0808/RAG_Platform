from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.api.dependencies import get_container, get_session
from foundry.core.container import Container
from foundry.schemas import ChatResponse, PublicChatRequest

router = APIRouter(prefix="/public", tags=["public"])


@router.post("/{slug}/chat", response_model=ChatResponse)
async def public_chat(
    slug: str,
    payload: PublicChatRequest,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> ChatResponse:
    deployment = await container.pipelines.get_deployment(session, slug)
    pipeline = await container.pipelines.get(session, deployment.pipeline_id)
    result = await container.orchestrator.invoke(
        session, pipeline, payload.message, payload.strategy or pipeline.strategy
    )
    return ChatResponse.model_validate(result)
