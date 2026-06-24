from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.api.dependencies import get_container, get_session
from foundry.core.container import Container
from foundry.schemas import DeploymentCreate, DeploymentResponse, DeploymentUpdate

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


@router.patch("/{deployment_id}", response_model=DeploymentResponse)
async def update_deployment(
    deployment_id: str,
    payload: DeploymentUpdate,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> DeploymentResponse:
    deployment = await container.pipelines.update_deployment(session, deployment_id, payload)
    return DeploymentResponse.model_validate(deployment)


@router.post("/{deployment_id}/run", response_model=DeploymentResponse)
async def run_deployment(
    deployment_id: str,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> DeploymentResponse:
    deployment = await container.pipelines.run_deployment(session, deployment_id)
    return DeploymentResponse.model_validate(deployment)


@router.post("/{deployment_id}/stop", response_model=DeploymentResponse)
async def stop_deployment(
    deployment_id: str,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> DeploymentResponse:
    deployment = await container.pipelines.stop_deployment(session, deployment_id)
    return DeploymentResponse.model_validate(deployment)


@router.delete(
    "/{deployment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_deployment(
    deployment_id: str,
    session: AsyncSession = Depends(get_session),
    container: Container = Depends(get_container),
) -> Response:
    await container.pipelines.delete_deployment(session, deployment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
