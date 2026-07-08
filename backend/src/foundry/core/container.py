from dataclasses import dataclass

from sqlalchemy import text

from foundry.core.config import Settings
from foundry.core.crypto import CredentialCipher
from foundry.core.database import Database
from foundry.services.bge_reranker import BGEReranker
from foundry.services.conversations import ConversationService
from foundry.services.knowledge import KnowledgeIndex
from foundry.services.langgraph_workflow import LangGraphRagWorkflow
from foundry.services.orchestrator import Orchestrator
from foundry.services.pipelines import PipelineService
from foundry.services.provider_quota import ProviderQuotaService
from foundry.services.providers import ProviderClient, ProviderService
from foundry.services.rag_router import RagRouter
from foundry.services.ragas_evaluation import RagasEvaluationService
from foundry.services.retrieval_tools import HealthcarePdfRetrievalTools
from foundry.services.sources import SourceService
from foundry.services.web_search import WebSearchProvider, build_web_search_provider


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
    rag_router: RagRouter
    web_search: WebSearchProvider
    retrieval_tools: HealthcarePdfRetrievalTools
    reranker: BGEReranker
    ragas_evaluation: RagasEvaluationService
    langgraph_workflow: LangGraphRagWorkflow

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
        rag_router = RagRouter(knowledge)
        web_search = build_web_search_provider(settings)
        retrieval_tools = HealthcarePdfRetrievalTools(settings, knowledge)
        reranker = BGEReranker(settings)
        langgraph_workflow = LangGraphRagWorkflow(
            settings,
            rag_router,
            retrieval_tools,
            reranker,
            web_search,
        )
        pipelines = PipelineService(providers)
        orchestrator = Orchestrator(
            settings,
            providers,
            knowledge,
            rag_router,
            web_search,
            langgraph_workflow,
        )
        ragas_evaluation = RagasEvaluationService(settings, orchestrator)
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
            rag_router=rag_router,
            web_search=web_search,
            retrieval_tools=retrieval_tools,
            reranker=reranker,
            ragas_evaluation=ragas_evaluation,
            langgraph_workflow=langgraph_workflow,
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
