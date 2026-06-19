import hashlib
import math
import re
from collections.abc import Iterable

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore

TOKEN_PATTERN = re.compile(r"[\w가-힣]+", re.UNICODE)


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

    def reset(self) -> None:
        self.vector_store = InMemoryVectorStore(self.embeddings)

    def add_documents(self, documents: Iterable[Document]) -> int:
        items = list(documents)
        if items:
            self.vector_store.add_documents(items)
        return len(items)

    def search(self, query: str, top_k: int) -> list[tuple[Document, float]]:
        return self.vector_store.similarity_search_with_score(query, k=top_k)
