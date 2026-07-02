import hashlib
import logging
import math
import os
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector

from foundry.core.config import Settings
from foundry.core.errors import ConfigurationError

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_\uac00-\ud7a3]+", re.UNICODE)
logger = logging.getLogger("foundry")


@dataclass(frozen=True)
class SearchResult:
    document: Document
    score: float
    dense_score: float = 0.0
    sparse_score: float = 0.0
    fusion_score: float = 0.0
    rerank_score: float = 0.0


class LocalHashEmbeddings(Embeddings):
    """Deterministic embeddings used only for tests and explicit local smoke tests."""

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in TOKEN_PATTERN.findall(text.lower()):
            digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class PostgresVectorDB:
    def __init__(self, settings: Settings, embeddings: Embeddings) -> None:
        self.store = PGVector(
            embeddings=embeddings,
            collection_name=settings.vector_collection_name,
            connection=settings.vector_database_url,
            use_jsonb=True,
        )

    def add_documents(self, documents: list[Document]) -> None:
        self.store.add_documents(
            documents,
            ids=[str(document.metadata["knowledge_id"]) for document in documents],
        )

    def similarity_search_with_score(self, query: str, k: int) -> list[tuple[Document, float]]:
        return self.store.similarity_search_with_score(query, k=k)

    def reset(self) -> None:
        try:
            if hasattr(self.store, "delete_collection"):
                self.store.delete_collection()
        except Exception:
            pass
        if hasattr(self.store, "create_collection"):
            self.store.create_collection()


class ChromaVectorDB:
    def __init__(self, settings: Settings, embeddings: Embeddings) -> None:
        try:
            from langchain_chroma import Chroma
        except ImportError as exc:
            raise ConfigurationError(
                "Chroma vector DB requires the langchain-chroma and chromadb packages. "
                "Run `uv sync` after updating dependencies."
            ) from exc

        self.settings = settings
        self.embeddings = embeddings
        self._chroma_cls = Chroma
        self.store = self._new_store()

    def _new_store(self):
        self.settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        return self._chroma_cls(
            collection_name=self.settings.vector_collection_name,
            embedding_function=self.embeddings,
            persist_directory=str(self.settings.chroma_persist_dir),
        )

    def add_documents(self, documents: list[Document]) -> None:
        self.store.add_documents(
            documents,
            ids=[str(document.metadata["knowledge_id"]) for document in documents],
        )

    def similarity_search_with_score(self, query: str, k: int) -> list[tuple[Document, float]]:
        return self.store.similarity_search_with_score(query, k=k)

    def reset(self) -> None:
        try:
            self.store.delete_collection()
        except Exception:
            pass
        self.store = self._new_store()


class KnowledgeIndex:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.vector_store: InMemoryVectorStore | PostgresVectorDB | ChromaVectorDB | None = None
        self.documents: list[Document] = []
        self.term_frequencies: list[Counter[str]] = []
        self.document_frequencies: Counter[str] = Counter()
        self.average_document_length = 0.0
        self._next_document_id = 0
        self._dense_index_unavailable = False

    def reset(self) -> None:
        if isinstance(self.vector_store, PostgresVectorDB | ChromaVectorDB):
            self.vector_store.reset()
        elif self.vector_store is not None:
            self.vector_store = None
        self.documents = []
        self.term_frequencies = []
        self.document_frequencies = Counter()
        self.average_document_length = 0.0
        self._next_document_id = 0
        self._dense_index_unavailable = False

    def add_documents(self, documents: Iterable[Document]) -> int:
        items = [self._with_document_id(document) for document in documents]
        if items:
            try:
                vector_store = self._vector_store()
                if vector_store is not None:
                    vector_store.add_documents(items)
            except Exception:
                logger.info("Dense vector index unavailable; using sparse index")
                self.vector_store = None
                self._dense_index_unavailable = True
            self.documents.extend(items)
            self._rebuild_sparse_index()
        return len(items)

    def search(
        self,
        query: str,
        top_k: int,
        *,
        candidate_k: int | None = None,
        kind: str | None = None,
    ) -> list[SearchResult]:
        if not self.documents:
            return self._dense_only_search(query, top_k, kind=kind)

        candidate_count = min(len(self.documents), candidate_k or max(top_k * 4, top_k))
        try:
            vector_store = self._vector_store()
            dense_hits = (
                vector_store.similarity_search_with_score(query, k=candidate_count)
                if vector_store is not None
                else []
            )
        except Exception:
            logger.info("Dense vector search unavailable; using sparse index")
            self.vector_store = None
            self._dense_index_unavailable = True
            dense_hits = []
        dense_by_id = {
            self._document_key(document): self._dense_score(score)
            for document, score in dense_hits
            if self._document_key(document) is not None
        }
        dense_rank = {
            self._document_key(document): rank
            for rank, (document, _) in enumerate(dense_hits, start=1)
            if self._document_key(document) is not None
        }

        sparse_scores = self._sparse_scores(query, kind=kind)
        sparse_order = sorted(sparse_scores.items(), key=lambda item: item[1], reverse=True)
        sparse_rank = {
            self._document_key(self.documents[index]): rank
            for rank, (index, score) in enumerate(sparse_order, start=1)
            if score > 0
        }

        document_positions = {
            self._document_key(document): index for index, document in enumerate(self.documents)
        }
        candidate_ids = set(dense_rank) | set(sparse_rank)
        if kind:
            candidate_ids = {
                document_id
                for document_id in candidate_ids
                if self._matches_kind(self._document_by_id(document_id), kind)
            }

        max_dense = max(dense_by_id.values(), default=1.0) or 1.0
        max_sparse = max(sparse_scores.values(), default=1.0) or 1.0
        results: list[SearchResult] = []
        for document in self.documents:
            document_id = self._document_key(document)
            if document_id not in candidate_ids:
                continue
            dense_score = dense_by_id.get(document_id, 0.0) / max_dense
            sparse_score = sparse_scores.get(document_positions[document_id], 0.0) / max_sparse
            fusion_score = self._rrf_score(
                dense_rank.get(document_id),
                sparse_rank.get(document_id),
            )
            rerank_score = self._rerank_score(query, document, dense_score, sparse_score)
            score = (fusion_score * 0.35) + (rerank_score * 0.65)
            results.append(
                SearchResult(
                    document=document,
                    score=score,
                    dense_score=dense_score,
                    sparse_score=sparse_score,
                    fusion_score=fusion_score,
                    rerank_score=rerank_score,
                )
            )

        return sorted(results, key=lambda result: result.score, reverse=True)[:top_k]

    def _dense_only_search(
        self,
        query: str,
        top_k: int,
        *,
        kind: str | None,
    ) -> list[SearchResult]:
        try:
            vector_store = self._vector_store()
            dense_hits = (
                vector_store.similarity_search_with_score(query, k=top_k)
                if vector_store is not None
                else []
            )
        except Exception:
            logger.info("Dense vector search unavailable; using sparse index")
            self.vector_store = None
            self._dense_index_unavailable = True
            return []

        results: list[SearchResult] = []
        for document, raw_score in dense_hits:
            if kind and not self._matches_kind(document, kind):
                continue
            dense_score = self._dense_score(raw_score)
            results.append(
                SearchResult(
                    document=document,
                    score=dense_score,
                    dense_score=dense_score,
                    fusion_score=dense_score,
                    rerank_score=dense_score,
                )
            )
        return results[:top_k]

    def _rebuild_sparse_index(self) -> None:
        self.term_frequencies = []
        self.document_frequencies = Counter()
        lengths: list[int] = []
        for document in self.documents:
            terms = self._tokens(document.page_content)
            frequencies = Counter(terms)
            self.term_frequencies.append(frequencies)
            self.document_frequencies.update(frequencies.keys())
            lengths.append(len(terms))
        self.average_document_length = sum(lengths) / len(lengths) if lengths else 0.0

    def _sparse_scores(self, query: str, *, kind: str | None) -> dict[int, float]:
        query_terms = self._tokens(query)
        if not query_terms:
            return {}
        query_frequencies = Counter(query_terms)
        scores: dict[int, float] = defaultdict(float)
        total_documents = len(self.documents)
        avgdl = self.average_document_length or 1.0
        k1 = 1.5
        b = 0.75
        for index, frequencies in enumerate(self.term_frequencies):
            document = self.documents[index]
            if kind and not self._matches_kind(document, kind):
                continue
            document_length = sum(frequencies.values()) or 1
            for term, query_frequency in query_frequencies.items():
                term_frequency = frequencies.get(term, 0)
                if not term_frequency:
                    continue
                doc_frequency = self.document_frequencies.get(term, 0)
                idf = math.log(
                    1
                    + ((total_documents - doc_frequency + 0.5) / (doc_frequency + 0.5))
                )
                numerator = term_frequency * (k1 + 1)
                denominator = term_frequency + k1 * (1 - b + b * document_length / avgdl)
                scores[index] += idf * (numerator / denominator) * math.sqrt(query_frequency)
        return scores

    @staticmethod
    def _rrf_score(dense_rank: int | None, sparse_rank: int | None, k: int = 60) -> float:
        score = 0.0
        if dense_rank is not None:
            score += 1 / (k + dense_rank)
        if sparse_rank is not None:
            score += 1 / (k + sparse_rank)
        return score

    def _rerank_score(
        self,
        query: str,
        document: Document,
        dense_score: float,
        sparse_score: float,
    ) -> float:
        query_terms = set(self._tokens(query))
        document_terms = set(self._tokens(document.page_content))
        overlap = len(query_terms & document_terms) / len(query_terms) if query_terms else 0.0
        phrase_bonus = 0.15 if query.strip().lower() in document.page_content.lower() else 0.0
        location_bonus = 0.05 if document.metadata.get("location") == "table_catalog" else 0.0
        return min(
            1.0,
            (dense_score * 0.3)
            + (sparse_score * 0.35)
            + (overlap * 0.25)
            + phrase_bonus
            + location_bonus,
        )

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return TOKEN_PATTERN.findall(text.lower())

    @staticmethod
    def _matches_kind(document: Document | None, kind: str) -> bool:
        return bool(document and document.metadata.get("source_kind") == kind)

    @staticmethod
    def _document_key(document: Document) -> str | None:
        value = document.metadata.get("knowledge_id")
        return str(value) if value is not None else None

    def _document_by_id(self, document_id: str | None) -> Document | None:
        return next(
            (
                document
                for document in self.documents
                if self._document_key(document) == document_id
            ),
            None,
        )

    def _with_document_id(self, document: Document) -> Document:
        metadata = dict(document.metadata)
        if metadata.get("knowledge_id") is None:
            metadata["knowledge_id"] = str(self._next_document_id)
            self._next_document_id += 1
        return Document(page_content=document.page_content, metadata=metadata)

    @staticmethod
    def _dense_score(raw_score: float) -> float:
        return 1 / (1 + max(float(raw_score), 0.0))

    def _vector_store(self) -> InMemoryVectorStore | PostgresVectorDB | ChromaVectorDB | None:
        if self._dense_index_unavailable:
            return None
        if self.vector_store is not None:
            return self.vector_store
        if self._should_use_sparse_only_index():
            return None
        embeddings = self._build_embeddings()
        self.vector_store = self._build_vector_store(embeddings)
        return self.vector_store

    def _should_use_sparse_only_index(self) -> bool:
        return (
            self.settings.embedding_provider == "openai"
            and self.settings.openai_embedding_api_key is None
            and self.settings.openai_api_key is None
            and self.settings.openai_admin_api_key is None
            and not os.getenv("OPENAI_API_KEY")
        )

    def _build_embeddings(self) -> Embeddings:
        if self.settings.embedding_provider == "local":
            return LocalHashEmbeddings()
        if self.settings.embedding_provider == "huggingface":
            try:
                from langchain_huggingface import HuggingFaceEmbeddings
            except ImportError as exc:
                raise ConfigurationError(
                    "Hugging Face embeddings require the langchain-huggingface and "
                    "sentence-transformers packages. Run `uv sync` after updating dependencies."
                ) from exc
            return HuggingFaceEmbeddings(model_name=self.settings.huggingface_embedding_model)
        if self.settings.embedding_provider != "openai":
            raise ConfigurationError(
                f"Unsupported embedding provider: {self.settings.embedding_provider}. "
                "Supported values: 'openai', 'huggingface', 'local'."
            )
        api_key = self._configured_openai_api_key()
        if api_key is None:
            raise ConfigurationError(
                "OpenAI embeddings require FOUNDRY_OPENAI_EMBEDDING_API_KEY "
                "or FOUNDRY_OPENAI_API_KEY or FOUNDRY_OPENAI_ADMIN_API_KEY "
                "or OPENAI_API_KEY."
            )
        return OpenAIEmbeddings(
            model=self.settings.openai_embedding_model,
            api_key=api_key,
            chunk_size=1000,
        )

    def _build_vector_store(
        self, embeddings: Embeddings
    ) -> InMemoryVectorStore | PostgresVectorDB | ChromaVectorDB:
        if self.settings.vector_store_provider == "memory":
            return InMemoryVectorStore(embeddings)
        if self.settings.vector_store_provider == "chroma":
            return ChromaVectorDB(self.settings, embeddings)
        if self.settings.vector_store_provider != "postgres":
            raise ConfigurationError(
                f"Unsupported vector store provider: {self.settings.vector_store_provider}. "
                "Supported values: 'chroma', 'postgres', 'memory'."
            )
        return PostgresVectorDB(self.settings, embeddings)

    def _configured_openai_api_key(self) -> str | None:
        for secret in (
            self.settings.openai_embedding_api_key,
            self.settings.openai_api_key,
            self.settings.openai_admin_api_key,
        ):
            if secret is not None and secret.get_secret_value():
                return secret.get_secret_value()
        return os.getenv("OPENAI_API_KEY")
