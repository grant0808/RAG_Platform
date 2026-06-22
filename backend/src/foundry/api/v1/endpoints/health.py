from fastapi import APIRouter, Depends

from foundry import __version__
from foundry.api.dependencies import get_container
from foundry.core.container import Container
from foundry.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health(container: Container = Depends(get_container)) -> HealthResponse:
    return HealthResponse(service=container.settings.app_name, version=__version__)
