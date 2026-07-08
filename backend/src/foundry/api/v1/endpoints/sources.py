from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.api.dependencies import get_container, get_session
from foundry.core.container import Container
from foundry.core.errors import ValidationError
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


@router.post(
    "/papers",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_paper_source(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> SourceResponse:
    if not (file.filename or "").lower().endswith(".pdf"):
        raise ValidationError("Paper source uploads only support PDF files")
    source = await container.sources.ingest(session, file)
    return SourceResponse.model_validate(source)


@router.post("/index", status_code=status.HTTP_202_ACCEPTED)
async def rebuild_source_index(
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> dict[str, str]:
    await container.sources.rebuild(session)
    return {"status": "accepted"}


@router.get("", response_model=list[SourceResponse])
async def list_sources(
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> list[SourceResponse]:
    return [SourceResponse.model_validate(item) for item in await container.sources.list(session)]


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: str,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> SourceResponse:
    return SourceResponse.model_validate(await container.sources.get(session, source_id))


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
