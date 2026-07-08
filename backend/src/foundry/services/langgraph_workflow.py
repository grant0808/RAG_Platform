from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, TypedDict

from foundry.core.config import Settings
from foundry.models import Pipeline
from foundry.schemas import Citation, TraceEvent
from foundry.services.bge_reranker import BGEReranker
from foundry.services.duckduckgo_search import DuckDuckGoSearchFallback
from foundry.services.query_rewriter import QueryRewriter, QueryRewriteResult
from foundry.services.rag_router import RagRouter
from foundry.services.retrieval_tools import (
    HealthcarePdfRetrievalTools,
    RetrievalDocument,
    RetrievalToolName,
)
from foundry.services.web_search import WebSearchProvider, WebSearchResult

RouteName = Literal["general", "rag", "web_fallback"]


class RagGraphState(TypedDict, total=False):
    query: str
    conversation_id: str
    history: list[tuple[str, str]]
    route: RouteName
    route_reason: str
    rewrite: QueryRewriteResult
    rewritten_query: str
    selected_tool: RetrievalToolName
    retrieved_documents: list[RetrievalDocument]
    contexts: list[RetrievalDocument]
    web_results: list[WebSearchResult]
    context_sufficient: bool
    context: str
    citations: list[Citation]
    sources: list[dict[str, Any]]
    trace: list[TraceEvent]
    answer_mode: str
    memory_used: bool
    history_count: int


@dataclass
class GraphPreparedContext:
    context: str
    citations: list[Citation] = field(default_factory=list)
    trace: list[TraceEvent] = field(default_factory=list)
    route: str = "rag"
    route_reason: str = ""
    contexts: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    rewritten_query: str | None = None
    selected_tool: str = "none"
    web_results: list[dict[str, Any]] = field(default_factory=list)
    memory_used: bool = False
    history_count: int = 0


class LangGraphRagWorkflow:
    """LangGraph question-processing workflow for route-aware RAG."""

    def __init__(
        self,
        settings: Settings,
        router: RagRouter,
        retrieval_tools: HealthcarePdfRetrievalTools,
        reranker: BGEReranker,
        web_search: WebSearchProvider,
        query_rewriter: QueryRewriter | None = None,
    ) -> None:
        self.settings = settings
        self.router = router
        self.retrieval_tools = retrieval_tools
        self.reranker = reranker
        self.web_search = web_search
        self.duckduckgo = DuckDuckGoSearchFallback(settings)
        self.query_rewriter = query_rewriter or QueryRewriter()
        self._compiled_graph = self._compile_graph()

    async def prepare(
        self,
        pipeline: Pipeline,
        query: str,
        history: list[tuple[str, str]] | None = None,
        conversation_id: str | None = None,
    ) -> GraphPreparedContext:
        trimmed_history = (history or [])[-self.settings.memory_window_size :]
        initial_state: RagGraphState = {
            "query": query,
            "conversation_id": conversation_id or "",
            "history": trimmed_history,
            "trace": [],
            "selected_tool": "none",
            "retrieved_documents": [],
            "contexts": [],
            "web_results": [],
            "sources": [],
            "citations": [],
            "memory_used": self.settings.memory_enabled and bool(trimmed_history),
            "history_count": len(trimmed_history) if self.settings.memory_enabled else 0,
        }
        state = await self._compiled_graph.ainvoke(
            {
                **initial_state,
                "_pipeline_top_k": pipeline.top_k,
                "_pipeline_threshold": pipeline.similarity_threshold,
            }
        )
        return self._prepared(state)

    def analyze_query(self, state: RagGraphState) -> RagGraphState:
        started = time.perf_counter()
        decision = self.router.decide(state["query"])
        route = decision.route if self.settings.rag_enabled else "general"
        return {
            **state,
            "route": route,
            "route_reason": decision.reason,
            "trace": [
                *state.get("trace", []),
                self._trace(
                    "analyze_query",
                    started,
                    {
                        "route": route,
                        "reason": decision.reason,
                        "memory_used": state.get("memory_used", False),
                        "history_count": state.get("history_count", 0),
                    },
                ),
            ],
        }

    def route_question(self, state: RagGraphState) -> RagGraphState:
        return {
            **state,
            "trace": [
                *state.get("trace", []),
                TraceEvent(
                    step="rag_router",
                    status="completed",
                    duration_ms=0,
                    metadata={"route": state.get("route"), "reason": state.get("route_reason")},
                ),
                TraceEvent(
                    step="route_question",
                    status="completed",
                    duration_ms=0,
                    metadata={"route": state.get("route"), "reason": state.get("route_reason")},
                ),
            ],
        }

    def rewrite_query(self, state: RagGraphState) -> RagGraphState:
        started = time.perf_counter()
        history = state.get("history", []) if self.settings.memory_enabled else []
        rewrite = self.query_rewriter.rewrite(state["query"], history=history)
        return {
            **state,
            "rewrite": rewrite,
            "rewritten_query": rewrite.rewritten_query,
            "trace": [
                *state.get("trace", []),
                self._trace(
                    "rewrite_query",
                    started,
                    {
                        "rewritten_query": rewrite.rewritten_query,
                        "english_query": rewrite.english_query,
                        "keywords": rewrite.keywords,
                        "search_intent": rewrite.search_intent,
                        "requires_history": rewrite.requires_history,
                        "history_count": state.get("history_count", 0),
                    },
                ),
            ],
        }

    def select_retrieval_tool(self, state: RagGraphState) -> RagGraphState:
        rewrite = state["rewrite"]
        selected_tool = self.retrieval_tools.select_tool(rewrite)
        return {
            **state,
            "selected_tool": selected_tool,
            "trace": [
                *state.get("trace", []),
                TraceEvent(
                    step="select_retrieval_tool",
                    status="completed",
                    duration_ms=0,
                    metadata={"selected_tool": selected_tool, "selector": "rule_based_fallback"},
                ),
            ],
        }

    def retrieve_documents(self, state: RagGraphState) -> RagGraphState:
        started = time.perf_counter()
        query = self._search_query(state)
        result = self.retrieval_tools.run(state["selected_tool"], query)
        return {
            **state,
            "retrieved_documents": result.documents,
            "trace": [
                *state.get("trace", []),
                self._trace(
                    "retriever",
                    started,
                    {
                        "node": "retrieve_documents",
                        "tool": result.tool,
                        "query": result.query,
                        "documents": len(result.documents),
                    },
                ),
                self._trace(
                    "retrieve_documents",
                    started,
                    {
                        "tool": result.tool,
                        "query": result.query,
                        "documents": len(result.documents),
                    },
                ),
            ],
        }

    def rerank_documents(self, state: RagGraphState) -> RagGraphState:
        started = time.perf_counter()
        query = self._search_query(state)
        contexts = self.reranker.rerank(query, state.get("retrieved_documents", []))
        return {
            **state,
            "contexts": contexts,
            "trace": [
                *state.get("trace", []),
                self._trace(
                    "rerank_documents",
                    started,
                    {
                        "model": self.settings.reranker_model_name,
                        "load_model": self.settings.reranker_load_model,
                        "documents": len(contexts),
                        "scores": [document.rerank_score for document in contexts],
                    },
                ),
            ],
        }

    def grade_context(self, state: RagGraphState) -> RagGraphState:
        contexts = state.get("contexts", [])
        best_score = max((document.rerank_score for document in contexts), default=0.0)
        source_count = len({str(document.metadata.get("source")) for document in contexts})
        sufficient = bool(
            contexts
            and (
                len(contexts) >= self.settings.min_context_count
                or best_score
                >= max(self.settings.rerank_score_threshold, self.settings.rag_score_threshold)
            )
        )
        if not contexts and self.settings.web_fallback_on_empty_context:
            sufficient = False
        route: RouteName = "rag" if sufficient else "web_fallback"
        return {
            **state,
            "route": route,
            "context_sufficient": sufficient,
            "trace": [
                *state.get("trace", []),
                TraceEvent(
                    step="grade_context",
                    status="completed",
                    duration_ms=0,
                    metadata={
                        "sufficient": sufficient,
                        "context_count": len(contexts),
                        "best_rerank_score": best_score,
                        "source_count": source_count,
                    },
                ),
            ],
        }

    def generate_rag_answer(self, state: RagGraphState) -> RagGraphState:
        contexts = state.get("contexts", [])
        return {
            **state,
            "answer_mode": "rag",
            "context": self._documents_context(contexts),
            "citations": [self._document_citation(document) for document in contexts],
            "sources": [self._document_source(document) for document in contexts],
        }

    async def web_search_fallback(self, state: RagGraphState) -> RagGraphState:
        started = time.perf_counter()
        if not self.settings.web_fallback_enabled:
            results: list[WebSearchResult] = []
        else:
            query = self._web_search_query(state)
            if self.settings.web_fallback_provider.lower() == "duckduckgo":
                results = await self.duckduckgo.search(
                    query,
                    max_results=self.settings.duckduckgo_max_results,
                )
            else:
                results = []
            if not results and self.settings.web_search_provider.lower() != "duckduckgo":
                try:
                    results = await self.web_search.search(
                        query,
                        max_results=self.settings.duckduckgo_max_results,
                    )
                except Exception:
                    results = []
        return {
            **state,
            "route": "web_fallback",
            "answer_mode": "web_fallback",
            "web_results": results,
            "context": self._fallback_context(state.get("contexts", []), results),
            "citations": [
                *[self._document_citation(document) for document in state.get("contexts", [])],
                *[self._web_citation(result) for result in results],
            ],
            "sources": [
                *[self._document_source(document) for document in state.get("contexts", [])],
                *[self._web_source(result) for result in results],
            ],
            "trace": [
                *state.get("trace", []),
                self._trace(
                    "web_search_fallback",
                    started,
                    {
                        "provider": results[0].provider if results else "none",
                        "results": len(results),
                        "query": self._web_search_query(state),
                    },
                ),
                self._trace(
                    "web_search",
                    started,
                    {
                        "provider": results[0].provider if results else "none",
                        "results": len(results),
                        "query": self._web_search_query(state),
                    },
                ),
            ],
        }

    def generate_general_answer(self, state: RagGraphState) -> RagGraphState:
        return {
            **state,
            "answer_mode": "general",
            "selected_tool": "none",
            "context": "No retrieved context was requested for this general question.",
            "contexts": [],
            "citations": [],
            "sources": [],
        }

    def finalize_response(self, state: RagGraphState) -> RagGraphState:
        return {
            **state,
            "trace": [
                *state.get("trace", []),
                TraceEvent(
                    step="finalize_response",
                    status="completed",
                    duration_ms=0,
                    metadata={
                        "route": state.get("route"),
                        "selected_tool": state.get("selected_tool", "none"),
                        "memory_used": state.get("memory_used", False),
                        "history_count": state.get("history_count", 0),
                        "created_at": datetime.now(UTC).isoformat(),
                    },
                ),
            ],
        }

    def _compile_graph(self):
        try:
            from langgraph.graph import END, StateGraph
        except Exception:
            return _FallbackGraph(self)

        graph = StateGraph(RagGraphState)
        graph.add_node("analyze_query", self.analyze_query)
        graph.add_node("route_question", self.route_question)
        graph.add_node("rewrite_query", self.rewrite_query)
        graph.add_node("select_retrieval_tool", self.select_retrieval_tool)
        graph.add_node("retrieve_documents", self.retrieve_documents)
        graph.add_node("rerank_documents", self.rerank_documents)
        graph.add_node("grade_context", self.grade_context)
        graph.add_node("generate_rag_answer", self.generate_rag_answer)
        graph.add_node("web_search_fallback", self.web_search_fallback)
        graph.add_node("generate_general_answer", self.generate_general_answer)
        graph.add_node("finalize_response", self.finalize_response)

        graph.set_entry_point("analyze_query")
        graph.add_edge("analyze_query", "route_question")
        graph.add_conditional_edges(
            "route_question",
            lambda state: state.get("route", "general"),
            {
                "general": "generate_general_answer",
                "rag": "rewrite_query",
                "web_fallback": "rewrite_query",
            },
        )
        graph.add_conditional_edges(
            "rewrite_query",
            lambda state: "web_fallback" if state.get("route") == "web_fallback" else "rag",
            {
                "rag": "select_retrieval_tool",
                "web_fallback": "web_search_fallback",
            },
        )
        graph.add_edge("select_retrieval_tool", "retrieve_documents")
        graph.add_edge("retrieve_documents", "rerank_documents")
        graph.add_edge("rerank_documents", "grade_context")
        graph.add_conditional_edges(
            "grade_context",
            lambda state: "rag" if state.get("context_sufficient") else "web_fallback",
            {
                "rag": "generate_rag_answer",
                "web_fallback": "web_search_fallback",
            },
        )
        graph.add_edge("generate_rag_answer", "finalize_response")
        graph.add_edge("web_search_fallback", "finalize_response")
        graph.add_edge("generate_general_answer", "finalize_response")
        graph.add_edge("finalize_response", END)
        return graph.compile()

    def _prepared(self, state: RagGraphState) -> GraphPreparedContext:
        contexts = [
            self._context_payload(document)
            for document in state.get("contexts", [])
            if isinstance(document, RetrievalDocument)
        ]
        web_results = [
            {
                "title": result.title,
                "url": result.url,
                "snippet": result.snippet,
                "provider": result.provider,
            }
            for result in state.get("web_results", [])
        ]
        return GraphPreparedContext(
            context=state.get("context") or "No relevant context was found.",
            citations=state.get("citations", []),
            trace=state.get("trace", []),
            route=state.get("route", "rag"),
            route_reason=state.get("route_reason", ""),
            contexts=contexts,
            sources=state.get("sources", []),
            rewritten_query=state.get("rewritten_query"),
            selected_tool=state.get("selected_tool", "none"),
            web_results=web_results,
            memory_used=state.get("memory_used", False),
            history_count=state.get("history_count", 0),
        )

    @staticmethod
    def _search_query(state: RagGraphState) -> str:
        rewrite = state.get("rewrite")
        if rewrite and rewrite.rewritten_query:
            return rewrite.rewritten_query
        if rewrite and rewrite.english_query:
            return rewrite.english_query
        return state["query"]

    @staticmethod
    def _web_search_query(state: RagGraphState) -> str:
        rewrite = state.get("rewrite")
        if rewrite and rewrite.english_query:
            return rewrite.english_query
        if rewrite and rewrite.rewritten_query:
            return rewrite.rewritten_query
        return state["query"]

    @staticmethod
    def _documents_context(documents: list[RetrievalDocument]) -> str:
        return "\n\n".join(
            (
                f"Source: {document.metadata.get('source')} "
                f"(page={document.metadata.get('page')}, "
                f"chunk={document.metadata.get('chunk_id')})\n"
                f"{document.content}"
            )
            for document in documents
        )

    @staticmethod
    def _web_context(results: list[WebSearchResult]) -> str:
        return "\n\n".join(
            f"Web Source: {result.title} ({result.url})\n{result.snippet}" for result in results
        ) or "Uploaded documents and web search did not return usable context."

    @classmethod
    def _fallback_context(
        cls,
        documents: list[RetrievalDocument],
        results: list[WebSearchResult],
    ) -> str:
        parts: list[str] = []
        if documents:
            parts.append(
                "[PDF context found but graded insufficient]\n"
                + cls._documents_context(documents)
            )
        parts.append(cls._web_context(results))
        return "\n\n".join(parts)

    @staticmethod
    def _document_citation(document: RetrievalDocument) -> Citation:
        return Citation(
            source_id=str(document.metadata.get("source_id") or document.metadata.get("source")),
            source_name=str(document.metadata.get("source") or "unknown"),
            location=str(document.metadata.get("location") or document.metadata.get("page") or ""),
            score=round(float(document.rerank_score), 4),
        )

    @staticmethod
    def _web_citation(result: WebSearchResult) -> Citation:
        return Citation(
            source_id=result.url or "web",
            source_name=result.title,
            location="web",
            score=None,
            url=result.url,
            provider=result.provider,
        )

    @staticmethod
    def _document_source(document: RetrievalDocument) -> dict[str, Any]:
        return {
            "type": "pdf",
            "source": document.metadata.get("source"),
            "page": document.metadata.get("page"),
            "chunk_id": document.metadata.get("chunk_id"),
            "score": document.score,
            "rerank_score": document.rerank_score,
            "retrieval_type": document.metadata.get("retrieval_type"),
        }

    @staticmethod
    def _web_source(result: WebSearchResult) -> dict[str, Any]:
        return {
            "type": "web",
            "title": result.title,
            "url": result.url,
            "snippet": result.snippet,
            "provider": result.provider,
        }

    @staticmethod
    def _context_payload(document: RetrievalDocument) -> dict[str, Any]:
        return {
            "content": document.content,
            "score": document.score,
            "rerank_score": document.rerank_score,
            "metadata": document.metadata,
        }

    @staticmethod
    def _trace(step: str, started: float, metadata: dict[str, Any]) -> TraceEvent:
        return TraceEvent(
            step=step,
            status="completed",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            metadata=metadata,
        )


class _FallbackGraph:
    """Manual runner used only if langgraph is unavailable in a minimal local install."""

    def __init__(self, workflow: LangGraphRagWorkflow) -> None:
        self.workflow = workflow

    async def ainvoke(self, state: RagGraphState) -> RagGraphState:
        state = self.workflow.analyze_query(state)
        state = self.workflow.route_question(state)
        if state.get("route") == "general":
            state = self.workflow.generate_general_answer(state)
            return self.workflow.finalize_response(state)
        state = self.workflow.rewrite_query(state)
        if state.get("route") == "web_fallback":
            state = await self.workflow.web_search_fallback(state)
            return self.workflow.finalize_response(state)
        state = self.workflow.select_retrieval_tool(state)
        state = self.workflow.retrieve_documents(state)
        state = self.workflow.rerank_documents(state)
        state = self.workflow.grade_context(state)
        if state.get("context_sufficient"):
            state = self.workflow.generate_rag_answer(state)
        else:
            state = await self.workflow.web_search_fallback(state)
        return self.workflow.finalize_response(state)
