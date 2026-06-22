import argparse
import asyncio
from io import BytesIO
from typing import Any

from fastapi import UploadFile
from sqlalchemy import select

from foundry.core.config import Settings, get_settings
from foundry.core.container import Container
from foundry.models import Deployment, Pipeline, ProviderConnection, Source
from foundry.schemas import DeploymentCreate, PipelineCreate

LOCAL_PROVIDER_KEY = "sk-local-test-only-not-a-real-key"

SAMPLE_FILES = {
    "foundry-guide.md": b"""# Foundry guide

Foundry is a LangChain learning platform for RAG, TAG, and CAG pipelines.
The target first response latency is p95 three seconds and answers should cite sources.
""",
    "support-metrics.csv": (
        b"product,tickets,satisfaction\n"
        b"Atlas Pro,1284,0.91\n"
        b"Nova,410,0.88\n"
        b"Orbit,275,0.86\n"
    ),
}


async def initialize_database(settings: Settings | None = None) -> None:
    container = Container.build(settings or get_settings())
    try:
        await container.database.create_schema()
    finally:
        container.tables.close()
        await container.database.dispose()


async def bootstrap_local(settings: Settings | None = None) -> dict[str, Any]:
    app_settings = settings or get_settings()
    container = Container.build(app_settings)
    summary: dict[str, Any] = {}
    try:
        await container.startup()
        async for session in container.database.session():
            provider = await session.scalar(
                select(ProviderConnection).where(ProviderConnection.provider == "openai")
            )
            if provider is None:
                provider = await container.providers.connect(
                    session,
                    "openai",
                    LOCAL_PROVIDER_KEY,
                    validate_connection=False,
                )
            summary["provider"] = provider.provider

            source_names = set(await session.scalars(select(Source.name)))
            for filename, content in SAMPLE_FILES.items():
                if filename not in source_names:
                    await container.sources.ingest(
                        session,
                        UploadFile(file=BytesIO(content), filename=filename),
                    )
            source_result = await session.scalars(select(Source.name).order_by(Source.name))
            summary["sources"] = list(source_result)

            pipelines = {
                pipeline.name: pipeline
                for pipeline in await session.scalars(select(Pipeline).order_by(Pipeline.name))
            }
            for strategy in ("rag", "tag", "cag"):
                name = f"Local {strategy.upper()} Demo"
                if name not in pipelines:
                    pipelines[name] = await container.pipelines.create(
                        session,
                        PipelineCreate(
                            name=name,
                            strategy=strategy,
                            provider="openai",
                            model="gpt-local-demo",
                            similarity_threshold=0,
                        ),
                    )

            deployment = await session.scalar(
                select(Deployment).where(Deployment.slug == "local-rag-preview")
            )
            if deployment is None:
                deployment = await container.pipelines.create_deployment(
                    session,
                    DeploymentCreate(
                        pipeline_id=pipelines["Local RAG Demo"].id,
                        slug="local-rag-preview",
                    ),
                )
            summary["pipelines"] = sorted(pipelines)
            summary["deployment_slug"] = deployment.slug
        return summary
    finally:
        await container.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(description="Foundry local database utilities")
    parser.add_argument(
        "command",
        choices=("init-db", "bootstrap"),
        help="Create an empty schema or create idempotent local demo data",
    )
    args = parser.parse_args()

    if args.command == "init-db":
        asyncio.run(initialize_database())
        print("Local database schema is ready.")
        return

    summary = asyncio.run(bootstrap_local())
    print(f"Provider: {summary['provider']}")
    print(f"Sources: {', '.join(summary['sources'])}")
    print(f"Pipelines: {', '.join(summary['pipelines'])}")
    print(f"Deployment: {summary['deployment_slug']}")


if __name__ == "__main__":
    main()
