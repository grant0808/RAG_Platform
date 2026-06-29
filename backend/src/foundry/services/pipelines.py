from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.core.errors import ConfigurationError, NotFoundError, ValidationError
from foundry.models import Deployment, Pipeline, PipelineVersion
from foundry.schemas import DeploymentCreate, DeploymentUpdate, PipelineCreate, PipelineUpdate
from foundry.services.providers import ProviderService


@dataclass(frozen=True)
class PipelineSnapshot:
    id: str
    current_version: int
    name: str
    strategy: str
    provider: str
    model: str
    system_prompt: str
    top_k: int
    similarity_threshold: float

    @classmethod
    def from_version(cls, pipeline_id: str, version: PipelineVersion) -> PipelineSnapshot:
        config: dict[str, Any] = version.config
        return cls(
            id=pipeline_id,
            current_version=version.version,
            name=str(config["name"]),
            strategy=str(config["strategy"]),
            provider=str(config["provider"]),
            model=str(config["model"]),
            system_prompt=str(config["system_prompt"]),
            top_k=int(config["top_k"]),
            similarity_threshold=float(config["similarity_threshold"]),
        )


def pipeline_config(pipeline: Pipeline) -> dict[str, object]:
    return {
        "name": pipeline.name,
        "strategy": pipeline.strategy,
        "provider": pipeline.provider,
        "model": pipeline.model,
        "system_prompt": pipeline.system_prompt,
        "top_k": pipeline.top_k,
        "similarity_threshold": pipeline.similarity_threshold,
    }


class PipelineService:
    def __init__(self, providers: ProviderService) -> None:
        self.providers = providers

    async def create(self, session: AsyncSession, payload: PipelineCreate) -> Pipeline:
        await self._validate_provider_model(session, payload.provider, payload.model)
        pipeline = Pipeline(**payload.model_dump())
        session.add(pipeline)
        await session.flush()
        session.add(
            PipelineVersion(
                pipeline_id=pipeline.id,
                version=1,
                config=pipeline_config(pipeline),
            )
        )
        await session.flush()
        await session.refresh(pipeline)
        return pipeline

    async def list(self, session: AsyncSession) -> list[Pipeline]:
        result = await session.execute(select(Pipeline).order_by(Pipeline.created_at.desc()))
        return list(result.scalars())

    async def get(self, session: AsyncSession, pipeline_id: str) -> Pipeline:
        pipeline = await session.get(Pipeline, pipeline_id)
        if pipeline is None:
            raise NotFoundError(f"Pipeline not found: {pipeline_id}")
        return pipeline

    async def update(
        self, session: AsyncSession, pipeline_id: str, payload: PipelineUpdate
    ) -> Pipeline:
        pipeline = await self.get(session, pipeline_id)
        provider = payload.provider or pipeline.provider
        model = payload.model or pipeline.model
        await self._validate_provider_model(session, provider, model)
        for name, value in payload.model_dump(exclude_unset=True).items():
            setattr(pipeline, name, value)
        await session.flush()
        await session.refresh(pipeline)
        return pipeline

    async def delete(self, session: AsyncSession, pipeline_id: str) -> None:
        pipeline = await self.get(session, pipeline_id)
        await session.delete(pipeline)
        await session.flush()

    async def save_version(self, session: AsyncSession, pipeline_id: str) -> PipelineVersion:
        pipeline = await self.get(session, pipeline_id)
        await self._validate_provider_model(session, pipeline.provider, pipeline.model)
        pipeline.current_version += 1
        version = PipelineVersion(
            pipeline_id=pipeline.id,
            version=pipeline.current_version,
            config=pipeline_config(pipeline),
        )
        session.add(version)
        await session.flush()
        await session.refresh(version)
        return version

    async def list_versions(self, session: AsyncSession, pipeline_id: str) -> list[PipelineVersion]:
        await self.get(session, pipeline_id)
        result = await session.execute(
            select(PipelineVersion)
            .where(PipelineVersion.pipeline_id == pipeline_id)
            .order_by(PipelineVersion.version.desc())
        )
        return list(result.scalars())

    async def rollback(
        self, session: AsyncSession, pipeline_id: str, version_number: int
    ) -> Pipeline:
        pipeline = await self.get(session, pipeline_id)
        result = await session.execute(
            select(PipelineVersion).where(
                PipelineVersion.pipeline_id == pipeline_id,
                PipelineVersion.version == version_number,
            )
        )
        version = result.scalar_one_or_none()
        if version is None:
            raise NotFoundError(f"Pipeline version not found: {version_number}")
        for name, value in version.config.items():
            if hasattr(pipeline, name):
                setattr(pipeline, name, value)
        # A rollback creates a new immutable head version. Reusing the old version
        # number would make subsequent deployments point at the pre-rollback head.
        pipeline.current_version += 1
        session.add(
            PipelineVersion(
                pipeline_id=pipeline.id,
                version=pipeline.current_version,
                config=pipeline_config(pipeline),
            )
        )
        await session.flush()
        await session.refresh(pipeline)
        return pipeline

    async def create_deployment(
        self, session: AsyncSession, payload: DeploymentCreate
    ) -> Deployment:
        pipeline = await self.get(session, payload.pipeline_id)
        slug = payload.slug or f"{pipeline.name.lower().replace(' ', '-')}-{secrets.token_hex(3)}"
        deployment = Deployment(
            pipeline_id=pipeline.id,
            slug=slug,
            version=pipeline.current_version,
            environment=payload.environment,
            status="running",
        )
        session.add(deployment)
        await session.flush()
        await session.refresh(deployment)
        return deployment

    async def list_deployments(self, session: AsyncSession) -> list[Deployment]:
        result = await session.execute(select(Deployment).order_by(Deployment.created_at.desc()))
        return list(result.scalars())

    async def get_deployment_by_id(self, session: AsyncSession, deployment_id: str) -> Deployment:
        deployment = await session.get(Deployment, deployment_id)
        if deployment is None:
            raise NotFoundError(f"Deployment not found: {deployment_id}")
        return deployment

    async def update_deployment(
        self, session: AsyncSession, deployment_id: str, payload: DeploymentUpdate
    ) -> Deployment:
        deployment = await self.get_deployment_by_id(session, deployment_id)
        for name, value in payload.model_dump(exclude_unset=True).items():
            setattr(deployment, name, value)
        await session.flush()
        await session.refresh(deployment)
        return deployment

    async def run_deployment(self, session: AsyncSession, deployment_id: str) -> Deployment:
        return await self.update_deployment(
            session, deployment_id, DeploymentUpdate(status="running")
        )

    async def stop_deployment(self, session: AsyncSession, deployment_id: str) -> Deployment:
        return await self.update_deployment(
            session, deployment_id, DeploymentUpdate(status="stopped")
        )

    async def delete_deployment(self, session: AsyncSession, deployment_id: str) -> None:
        deployment = await self.get_deployment_by_id(session, deployment_id)
        await session.delete(deployment)
        await session.flush()

    async def get_deployment(self, session: AsyncSession, slug: str) -> Deployment:
        result = await session.execute(select(Deployment).where(Deployment.slug == slug))
        deployment = result.scalar_one_or_none()
        if deployment is None:
            raise NotFoundError(f"Deployment not found: {slug}")
        return deployment

    async def get_deployment_pipeline(
        self, session: AsyncSession, slug: str
    ) -> PipelineSnapshot:
        deployment = await self.get_deployment(session, slug)
        if deployment.status != "running":
            raise ConfigurationError(f"Deployment is stopped: {slug}")
        result = await session.execute(
            select(PipelineVersion).where(
                PipelineVersion.pipeline_id == deployment.pipeline_id,
                PipelineVersion.version == deployment.version,
            )
        )
        version = result.scalar_one_or_none()
        if version is None:
            raise NotFoundError(f"Deployed pipeline version not found: {deployment.version}")
        return PipelineSnapshot.from_version(deployment.pipeline_id, version)

    async def _validate_provider_model(
        self, session: AsyncSession, provider: str, model: str
    ) -> None:
        connection = await self.providers.get(session, provider)
        if connection.models and model not in connection.models:
            raise ValidationError(
                f"Model is not available for the connected {provider} provider: {model}"
            )
