from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.api.dependencies import get_container, get_session
from foundry.core.container import Container
from foundry.schemas import DeploymentCreate, DeploymentResponse

router = APIRouter(prefix="/deployments", tags=["deployments"])


@router.post(
    "",
    response_model=DeploymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_deployment(
    payload: DeploymentCreate,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> DeploymentResponse:
    deployment = await container.pipelines.create_deployment(session, payload)
    return DeploymentResponse.model_validate(deployment)


@router.get("", response_model=list[DeploymentResponse])
async def list_deployments(
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> list[DeploymentResponse]:
    deployments = await container.pipelines.list_deployments(session)
    return [DeploymentResponse.model_validate(item) for item in deployments]
