import argparse
import asyncio
import os
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

Foundry is a LangChain learning platform for RAG pipelines.
The target first response latency is p95 three seconds and answers should cite sources.
""",
}


async def initialize_database(settings: Settings | None = None) -> None:
    container = Container.build(settings or get_settings())
    try:
        await container.database.create_schema()
    finally:
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
                provider_key = _openai_provider_key(app_settings)
                provider = await container.providers.connect(
                    session,
                    "openai",
                    provider_key,
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
            if "Local RAG Demo" not in pipelines:
                pipelines["Local RAG Demo"] = await container.pipelines.create(
                    session,
                    PipelineCreate(
                        name="Local RAG Demo",
                        strategy="rag",
                        provider="openai",
                        model=(
                            "gpt-local-demo"
                            if app_settings.fake_llm_enabled
                            else app_settings.openai_chat_model
                        ),
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


def _openai_provider_key(settings: Settings) -> str:
    for secret in (
        settings.openai_api_key,
        settings.openai_embedding_api_key,
        settings.openai_admin_api_key,
    ):
        if secret is not None and secret.get_secret_value():
            return secret.get_secret_value()
    return os.getenv("OPENAI_API_KEY") or LOCAL_PROVIDER_KEY


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
