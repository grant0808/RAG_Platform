from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.api.dependencies import get_container, get_session
from foundry.core.container import Container
from foundry.schemas import SourceResponse

router = APIRouter(prefix="/sources", tags=["sources"])


@router.post(
    "/upload",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_source(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> SourceResponse:
    source = await container.sources.ingest(session, file)
    return SourceResponse.model_validate(source)


@router.get("", response_model=list[SourceResponse])
async def list_sources(
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> list[SourceResponse]:
    return [SourceResponse.model_validate(item) for item in await container.sources.list(session)]


@router.delete(
    "/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_source(
    source_id: str,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> Response:
    await container.sources.delete(session, source_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
