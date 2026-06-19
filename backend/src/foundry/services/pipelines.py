import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foundry.core.errors import NotFoundError
from foundry.models import Deployment, Pipeline, PipelineVersion
from foundry.schemas import DeploymentCreate, PipelineCreate, PipelineUpdate


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
    async def create(self, session: AsyncSession, payload: PipelineCreate) -> Pipeline:
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
        for name, value in payload.model_dump(exclude_unset=True).items():
            setattr(pipeline, name, value)
        await session.flush()
        await session.refresh(pipeline)
        return pipeline

    async def save_version(self, session: AsyncSession, pipeline_id: str) -> PipelineVersion:
        pipeline = await self.get(session, pipeline_id)
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
            status=payload.status,
        )
        session.add(deployment)
        await session.flush()
        await session.refresh(deployment)
        return deployment

    async def list_deployments(self, session: AsyncSession) -> list[Deployment]:
        result = await session.execute(select(Deployment).order_by(Deployment.created_at.desc()))
        return list(result.scalars())

    async def get_deployment(self, session: AsyncSession, slug: str) -> Deployment:
        result = await session.execute(select(Deployment).where(Deployment.slug == slug))
        deployment = result.scalar_one_or_none()
        if deployment is None:
            raise NotFoundError(f"Deployment not found: {slug}")
        return deployment
