from __future__ import annotations

import re

from foundry.core.config import Settings
from foundry.services.retrieval_tools import RetrievalDocument

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_\uac00-\ud7a3]+", re.UNICODE)


class BGEReranker:
    """BGE reranker wrapper with a deterministic local fallback.

    Loading `BAAI/bge-reranker-v2-m3` can be heavy and may require network/model cache.
    The default path therefore uses lexical overlap scoring. Set
    `RERANKER_LOAD_MODEL=true` to opt into the actual CrossEncoder model.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model_name = settings.reranker_model_name
        self._model: object | None = None
        self._model_unavailable = False

    def rerank(self, query: str, documents: list[RetrievalDocument]) -> list[RetrievalDocument]:
        if not self.settings.reranker_enabled or not documents:
            return documents[: self.settings.final_context_top_k]

        candidates = documents[: self.settings.rerank_top_n]
        scored = [
            self._with_rerank_score(document, self._score(query, document))
            for document in candidates
        ]
        filtered = [
            document
            for document in scored
            if document.rerank_score >= self.settings.rerank_score_threshold
        ]
        ranked = sorted(filtered or scored, key=lambda item: item.rerank_score, reverse=True)
        return ranked[: self.settings.final_context_top_k]

    def _score(self, query: str, document: RetrievalDocument) -> float:
        if self.settings.reranker_load_model and not self._model_unavailable:
            try:
                model = self._cross_encoder()
                raw_score = model.predict([(query, document.content)])[0]
                return self._normalize_score(float(raw_score))
            except Exception:
                self._model_unavailable = True
        return self._lexical_score(query, document)

    def _cross_encoder(self):
        if self._model is not None:
            return self._model
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(self.model_name)
        return self._model

    @staticmethod
    def _normalize_score(score: float) -> float:
        if 0.0 <= score <= 1.0:
            return score
        return 1 / (1 + pow(2.718281828, -score))

    @staticmethod
    def _lexical_score(query: str, document: RetrievalDocument) -> float:
        query_terms = set(TOKEN_PATTERN.findall(query.lower()))
        document_terms = set(TOKEN_PATTERN.findall(document.content.lower()))
        overlap = len(query_terms & document_terms) / len(query_terms) if query_terms else 0.0
        blended = (document.score * 0.45) + (document.dense_score * 0.15) + (
            document.sparse_score * 0.15
        ) + (document.fusion_score * 0.1) + (overlap * 0.15)
        return round(min(1.0, max(0.0, blended)), 6)

    @staticmethod
    def _with_rerank_score(document: RetrievalDocument, score: float) -> RetrievalDocument:
        return RetrievalDocument(
            content=document.content,
            score=document.score,
            dense_score=document.dense_score,
            sparse_score=document.sparse_score,
            fusion_score=document.fusion_score,
            rerank_score=score,
            metadata=document.metadata,
        )
