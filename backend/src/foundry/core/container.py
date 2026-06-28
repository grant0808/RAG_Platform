from dataclasses import dataclass

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
from foundry.services.tables import TableStore


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
    tables: TableStore

    @classmethod
    def build(cls, settings: Settings) -> "Container":
        settings.prepare_directories()
        database = Database(settings.database_url)
        cipher = CredentialCipher(settings.master_key_path)
        provider_client = ProviderClient(settings.provider_timeout_seconds)
        provider_quota = ProviderQuotaService(settings)
        providers = ProviderService(cipher, provider_client)
        conversations = ConversationService()
        knowledge = KnowledgeIndex(settings)
        tables = TableStore(settings.data_dir / "tables.duckdb")
        sources = SourceService(settings, knowledge, tables)
        pipelines = PipelineService(providers)
        orchestrator = Orchestrator(settings, providers, knowledge, tables)
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
            tables=tables,
        )

    async def startup(self) -> None:
        await self.database.create_schema()
        async for session in self.database.session():
            await self.sources.rebuild(session)

    async def shutdown(self) -> None:
        self.tables.close()
        await self.database.dispose()
