import hashlib
import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_\uac00-\ud7a3]+", re.UNICODE)


@dataclass(frozen=True)
class SearchResult:
    document: Document
    score: float
    dense_score: float = 0.0
    sparse_score: float = 0.0
    fusion_score: float = 0.0
    rerank_score: float = 0.0


class LocalHashEmbeddings(Embeddings):
    """Deterministic local embeddings for a zero-infrastructure PoC.

    This is intentionally simple and must be replaced by a provider embedding model
    before evaluating semantic retrieval quality.
    """

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


class KnowledgeIndex:
    def __init__(self) -> None:
        self.embeddings = LocalHashEmbeddings()
        self.vector_store = InMemoryVectorStore(self.embeddings)
        self.documents: list[Document] = []
        self.term_frequencies: list[Counter[str]] = []
        self.document_frequencies: Counter[str] = Counter()
        self.average_document_length = 0.0

    def reset(self) -> None:
        self.vector_store = InMemoryVectorStore(self.embeddings)
        self.documents = []
        self.term_frequencies = []
        self.document_frequencies = Counter()
        self.average_document_length = 0.0

    def add_documents(self, documents: Iterable[Document]) -> int:
        items = list(documents)
        if items:
            self.vector_store.add_documents(items)
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
            return []

        candidate_count = min(len(self.documents), candidate_k or max(top_k * 4, top_k))
        dense_hits = self.vector_store.similarity_search_with_score(query, k=candidate_count)
        dense_by_id = {id(document): float(score) for document, score in dense_hits}
        dense_rank = {id(document): rank for rank, (document, _) in enumerate(dense_hits, start=1)}

        sparse_scores = self._sparse_scores(query, kind=kind)
        sparse_order = sorted(sparse_scores.items(), key=lambda item: item[1], reverse=True)
        sparse_rank = {
            id(self.documents[index]): rank
            for rank, (index, score) in enumerate(sparse_order, start=1)
            if score > 0
        }

        document_positions = {id(document): index for index, document in enumerate(self.documents)}
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
            document_id = id(document)
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

    def _document_by_id(self, document_id: int) -> Document | None:
        return next((document for document in self.documents if id(document) == document_id), None)
