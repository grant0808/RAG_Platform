from dataclasses import dataclass

from sqlalchemy import text

from foundry.core.config import Settings
from foundry.core.crypto import CredentialCipher
from foundry.core.database import Database
from foundry.services.conversations import ConversationService
from foundry.services.knowledge import KnowledgeIndex
from foundry.services.orchestrator import Orchestrator
from foundry.services.pipelines import PipelineService
from foundry.services.provider_quota import ProviderQuotaService
from foundry.services.providers import ProviderClient, ProviderService
from foundry.services.sources import SourceService


@dataclass
class Container:
    settings: Settings
    database: Database
    providers: ProviderService
    provider_client: ProviderClient
    provider_quota: ProviderQuotaService
    conversations: ConversationService
    pipelines: PipelineService
    sources: SourceService
    orchestrator: Orchestrator

    @classmethod
    def build(cls, settings: Settings) -> "Container":
        settings.prepare_directories()
        database = Database(settings.database_url)
        cipher = CredentialCipher(settings.master_key_path)
        provider_client = ProviderClient(
            settings.provider_timeout_seconds,
            settings.ollama_base_url,
        )
        provider_quota = ProviderQuotaService(settings)
        providers = ProviderService(cipher, provider_client, settings)
        conversations = ConversationService()
        knowledge = KnowledgeIndex(settings)
        sources = SourceService(settings, knowledge)
        pipelines = PipelineService(providers)
        orchestrator = Orchestrator(settings, providers, knowledge)
        return cls(
            settings=settings,
            database=database,
            providers=providers,
            provider_client=provider_client,
            provider_quota=provider_quota,
            conversations=conversations,
            pipelines=pipelines,
            sources=sources,
            orchestrator=orchestrator,
        )

    async def startup(self) -> None:
        await self.database.create_schema()
        async for session in self.database.session():
            if not self.settings.fake_llm_enabled:
                await session.execute(
                    text(
                        "UPDATE pipelines SET model = :model "
                        "WHERE provider = 'openai' AND model IN "
                        "('gpt-5.4-mini', 'gpt-local-demo')"
                    ),
                    {"model": self.settings.openai_chat_model},
                )
            if self.settings.rebuild_index_on_startup:
                await self.sources.rebuild(session)

    async def shutdown(self) -> None:
        await self.database.dispose()
