from __future__ import annotations

import re
from dataclasses import dataclass, field

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_\-\uac00-\ud7a3]+", re.UNICODE)


@dataclass(frozen=True)
class QueryRewriteResult:
    original_query: str
    rewritten_query: str
    keywords: list[str] = field(default_factory=list)
    english_query: str = ""
    search_intent: str = "general"


class QueryRewriter:
    """Search-oriented query rewrite with deterministic fallback.

    The class is intentionally rule-based for the default local environment. It can be
    replaced with an LLM-backed rewriter later without changing the LangGraph state shape.
    """

    _intent_terms = {
        "method": {"method", "방법", "방법론", "architecture", "algorithm", "모델", "기법"},
        "experiment": {"experiment", "실험", "dataset", "benchmark", "데이터셋", "평가"},
        "result": {"result", "결과", "성능", "performance", "score", "metric"},
        "limitation": {"limitation", "한계", "제약", "future", "향후", "문제점"},
        "comparison": {"compare", "comparison", "비교", "차이", "versus", "vs"},
        "definition": {"정의", "개념", "무엇", "what", "define", "definition"},
    }

    _stopwords = {
        "이",
        "그",
        "저",
        "좀",
        "please",
        "알려줘",
        "설명해줘",
        "해줘",
        "논문에서",
        "문서에서",
        "pdf에서",
        "source",
        "기준으로",
        "근거로",
    }

    _english_hints = {
        "방법": "method",
        "방법론": "methodology",
        "실험": "experiment",
        "결과": "result",
        "한계": "limitation",
        "기여": "contribution",
        "성능": "performance",
        "비교": "comparison",
        "데이터셋": "dataset",
        "논문": "paper",
        "요약": "summary",
    }

    def rewrite(self, query: str) -> QueryRewriteResult:
        tokens = [token for token in TOKEN_PATTERN.findall(query) if token.strip()]
        lowered = [token.lower() for token in tokens]
        keywords = [
            token
            for token in lowered
            if len(token) > 1 and token not in self._stopwords and not token.isdigit()
        ]
        keywords = list(dict.fromkeys(keywords))[:12]
        intent = self._intent(query, keywords)
        english_terms = [self._english_hints.get(token, token) for token in keywords]
        english_query = " ".join(dict.fromkeys(english_terms))
        if intent != "general" and intent not in english_query:
            english_query = f"{english_query} {intent}".strip()
        rewritten_query = " ".join(keywords) or query.strip()
        return QueryRewriteResult(
            original_query=query,
            rewritten_query=rewritten_query,
            keywords=keywords,
            english_query=english_query or rewritten_query,
            search_intent=intent,
        )

    def _intent(self, query: str, keywords: list[str]) -> str:
        value = query.lower()
        keyword_set = set(keywords)
        for intent, terms in self._intent_terms.items():
            if any(term in value or term in keyword_set for term in terms):
                return intent
        return "general"
