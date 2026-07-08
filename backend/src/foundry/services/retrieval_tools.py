from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from langchain_core.documents import Document
from langchain_core.tools import tool

from foundry.core.config import Settings
from foundry.services.knowledge import KnowledgeIndex, SearchResult
from foundry.services.query_rewriter import QueryRewriteResult

RetrievalToolName = Literal[
    "keyword_search_healthcare_pdf",
    "vector_search_healthcare_pdf",
    "hybrid_search_healthcare_pdf",
    "none",
]


@dataclass(frozen=True)
class RetrievalDocument:
    content: str
    score: float
    metadata: dict[str, object] = field(default_factory=dict)
    dense_score: float = 0.0
    sparse_score: float = 0.0
    fusion_score: float = 0.0
    rerank_score: float = 0.0

    def model_dump(self) -> dict[str, object]:
        return {
            "content": self.content,
            "score": self.score,
            "dense_score": self.dense_score,
            "sparse_score": self.sparse_score,
            "fusion_score": self.fusion_score,
            "rerank_score": self.rerank_score,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class RetrievalToolResult:
    tool: RetrievalToolName
    query: str
    documents: list[RetrievalDocument]

    def model_dump(self) -> dict[str, object]:
        return {
            "tool": self.tool,
            "query": self.query,
            "documents": [document.model_dump() for document in self.documents],
        }


def _normal_metadata(document: Document, retrieval_type: str) -> dict[str, object]:
    metadata = dict(document.metadata)
    source_name = metadata.get("source_name") or metadata.get("source") or "unknown"
    page = metadata.get("page_start") or metadata.get("page") or metadata.get("page_no")
    chunk_id = metadata.get("chunk_id") or metadata.get("knowledge_id")
    metadata.update(
        {
            "source": source_name,
            "page": page,
            "chunk_id": chunk_id,
            "retrieval_type": retrieval_type,
        }
    )
    return metadata


def _from_search_result(hit: SearchResult, retrieval_type: str) -> RetrievalDocument:
    return RetrievalDocument(
        content=hit.document.page_content,
        score=round(float(hit.score), 6),
        dense_score=round(float(hit.dense_score), 6),
        sparse_score=round(float(hit.sparse_score), 6),
        fusion_score=round(float(hit.fusion_score), 6),
        rerank_score=round(float(hit.rerank_score), 6),
        metadata=_normal_metadata(hit.document, retrieval_type),
    )


class HealthcarePdfRetrievalTools:
    """Three independent retrieval tools over indexed AI/CS paper PDF chunks."""

    keyword_tool_name: RetrievalToolName = "keyword_search_healthcare_pdf"
    vector_tool_name: RetrievalToolName = "vector_search_healthcare_pdf"
    hybrid_tool_name: RetrievalToolName = "hybrid_search_healthcare_pdf"

    def __init__(self, settings: Settings, knowledge: KnowledgeIndex) -> None:
        self.settings = settings
        self.knowledge = knowledge

    def keyword_search_healthcare_pdf(
        self,
        query: str,
        top_k: int | None = None,
    ) -> RetrievalToolResult:
        limit = top_k or self.settings.rag_top_k
        hits = self.knowledge.keyword_search(query, limit)
        return RetrievalToolResult(
            tool="keyword_search_healthcare_pdf",
            query=query,
            documents=[_from_search_result(hit, "keyword") for hit in hits],
        )

    def vector_search_healthcare_pdf(
        self,
        query: str,
        top_k: int | None = None,
    ) -> RetrievalToolResult:
        limit = top_k or self.settings.rag_top_k
        hits = self.knowledge.vector_search(query, limit)
        return RetrievalToolResult(
            tool="vector_search_healthcare_pdf",
            query=query,
            documents=[_from_search_result(hit, "vector") for hit in hits],
        )

    def hybrid_search_healthcare_pdf(
        self,
        query: str,
        top_k: int | None = None,
    ) -> RetrievalToolResult:
        limit = top_k or self.settings.rag_top_k
        hits = self.knowledge.hybrid_search(query, limit, candidate_k=max(limit * 4, limit))
        return RetrievalToolResult(
            tool="hybrid_search_healthcare_pdf",
            query=query,
            documents=[_from_search_result(hit, "hybrid") for hit in hits],
        )

    def select_tool(
        self,
        rewrite: QueryRewriteResult | None = None,
        *,
        rewritten_query: str | None = None,
        search_intent: str = "general",
        keywords: list[str] | None = None,
    ) -> RetrievalToolName:
        """Rule-based fallback selector for environments without an LLM tool-calling agent."""
        if rewrite is not None:
            original_query = rewrite.original_query
            rewritten_query = rewrite.rewritten_query
            search_intent = rewrite.search_intent
            keywords = rewrite.keywords
        else:
            original_query = rewritten_query or ""
            keywords = keywords or []
        query = f"{original_query} {rewritten_query or ''} {' '.join(keywords)}".lower()
        if search_intent in {"definition"} or any(
            word in query for word in ["개념", "의미", "설명", "what is", "why"]
        ):
            return "vector_search_healthcare_pdf"
        exact_signal = bool(
            re.search(r"\b(?!RAG\b)[A-Z][A-Z0-9_\-]{2,}\b", original_query)
            or re.search(r"(표|table|equation|수식|dataset|데이터셋|bert|gpt|llama|mmlu)", query)
        )
        if exact_signal:
            return "keyword_search_healthcare_pdf"
        return "hybrid_search_healthcare_pdf"

    def run(
        self,
        tool_name: RetrievalToolName,
        query: str,
        top_k: int | None = None,
    ) -> RetrievalToolResult:
        if tool_name == "keyword_search_healthcare_pdf":
            return self.keyword_search_healthcare_pdf(query, top_k)
        if tool_name == "vector_search_healthcare_pdf":
            return self.vector_search_healthcare_pdf(query, top_k)
        if tool_name == "hybrid_search_healthcare_pdf":
            return self.hybrid_search_healthcare_pdf(query, top_k)
        return RetrievalToolResult(tool="none", query=query, documents=[])

    def langchain_tools(self):
        """Expose the three retrieval functions as LangChain Tools."""

        @tool("keyword_search_healthcare_pdf")
        def keyword_search_healthcare_pdf(query: str) -> dict[str, object]:
            """BM25/Kiwi keyword search over indexed healthcare/AI paper PDF chunks."""
            return self.keyword_search_healthcare_pdf(query).model_dump()

        @tool("vector_search_healthcare_pdf")
        def vector_search_healthcare_pdf(query: str) -> dict[str, object]:
            """Chroma vector search over indexed healthcare/AI paper PDF chunks."""
            return self.vector_search_healthcare_pdf(query).model_dump()

        @tool("hybrid_search_healthcare_pdf")
        def hybrid_search_healthcare_pdf(query: str) -> dict[str, object]:
            """BM25 + Chroma + RRF hybrid search over indexed healthcare/AI paper PDFs."""
            return self.hybrid_search_healthcare_pdf(query).model_dump()

        return [
            keyword_search_healthcare_pdf,
            vector_search_healthcare_pdf,
            hybrid_search_healthcare_pdf,
        ]


PaperRetrievalTools = HealthcarePdfRetrievalTools
