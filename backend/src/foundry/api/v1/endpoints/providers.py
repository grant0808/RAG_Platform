from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.api.dependencies import get_container, get_session
from foundry.core.container import Container
from foundry.schemas import ProviderConnectRequest, ProviderResponse

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=list[ProviderResponse])
async def list_providers(
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> list[ProviderResponse]:
    return [
        ProviderResponse.model_validate(item) for item in await container.providers.list(session)
    ]


@router.put(
    "/{provider}",
    response_model=ProviderResponse,
)
async def connect_provider(
    provider: str,
    payload: ProviderConnectRequest,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> ProviderResponse:
    connection = await container.providers.connect(
        session,
        provider,
        payload.api_key.get_secret_value(),
        validate_connection=payload.validate_connection,
    )
    return ProviderResponse.model_validate(connection)


@router.post(
    "/{provider}/refresh-models",
    response_model=ProviderResponse,
)
async def refresh_provider_models(
    provider: str,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> ProviderResponse:
    connection = await container.providers.refresh_models(session, provider)
    return ProviderResponse.model_validate(connection)


@router.delete(
    "/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def disconnect_provider(
    provider: str,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> Response:
    await container.providers.disconnect(session, provider)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
