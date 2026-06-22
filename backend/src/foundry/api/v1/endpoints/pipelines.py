from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.api.dependencies import get_container, get_session
from foundry.core.container import Container
from foundry.schemas import (
    PipelineCreate,
    PipelineResponse,
    PipelineUpdate,
    PipelineVersionResponse,
)

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


@router.post(
    "",
    response_model=PipelineResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_pipeline(
    payload: PipelineCreate,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> PipelineResponse:
    pipeline = await container.pipelines.create(session, payload)
    return PipelineResponse.model_validate(pipeline)


@router.get("", response_model=list[PipelineResponse])
async def list_pipelines(
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> list[PipelineResponse]:
    return [
        PipelineResponse.model_validate(item) for item in await container.pipelines.list(session)
    ]


@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(
    pipeline_id: str,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> PipelineResponse:
    return PipelineResponse.model_validate(await container.pipelines.get(session, pipeline_id))


@router.patch("/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: str,
    payload: PipelineUpdate,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> PipelineResponse:
    pipeline = await container.pipelines.update(session, pipeline_id, payload)
    return PipelineResponse.model_validate(pipeline)


@router.post(
    "/{pipeline_id}/versions",
    response_model=PipelineVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def save_pipeline_version(
    pipeline_id: str,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> PipelineVersionResponse:
    version = await container.pipelines.save_version(session, pipeline_id)
    return PipelineVersionResponse.model_validate(version)


@router.get(
    "/{pipeline_id}/versions",
    response_model=list[PipelineVersionResponse],
)
async def list_pipeline_versions(
    pipeline_id: str,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> list[PipelineVersionResponse]:
    versions = await container.pipelines.list_versions(session, pipeline_id)
    return [PipelineVersionResponse.model_validate(item) for item in versions]


@router.post(
    "/{pipeline_id}/rollback/{version_number}",
    response_model=PipelineResponse,
)
async def rollback_pipeline(
    pipeline_id: str,
    version_number: int,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> PipelineResponse:
    pipeline = await container.pipelines.rollback(session, pipeline_id, version_number)
    return PipelineResponse.model_validate(pipeline)
