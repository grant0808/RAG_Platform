from dataclasses import dataclass

from foundry.services.knowledge import KnowledgeIndex

RAG_HINTS = {
    "논문",
    "문서",
    "pdf",
    "source",
    "출처",
    "근거",
    "업로드",
    "abstract",
    "introduction",
    "related work",
    "method",
    "방법",
    "방법론",
    "methodology",
    "experiment",
    "실험",
    "result",
    "결과",
    "limitation",
    "한계",
    "한계점",
    "future work",
    "references",
    "chunk",
}
GENERAL_HINTS = {
    "안녕",
    "hello",
    "hi",
    "고마워",
    "사용법",
    "설정",
    "코드 설명",
    "번역",
}
WEB_HINTS = {"최신", "최근", "today", "news", "웹", "인터넷", "검색"}


@dataclass(frozen=True)
class RouteDecision:
    route: str
    reason: str


class RagRouter:
    def __init__(self, knowledge: KnowledgeIndex) -> None:
        self.knowledge = knowledge

    def decide(self, question: str) -> RouteDecision:
        normalized = question.lower()
        if any(hint in normalized for hint in WEB_HINTS):
            return RouteDecision("web_fallback", "Question asks for recent or external web data")
        if any(hint in normalized for hint in RAG_HINTS):
            return RouteDecision(
                "rag",
                "Question explicitly asks for uploaded/source-grounded context",
            )
        if any(hint in normalized for hint in GENERAL_HINTS):
            return RouteDecision("general", "Question appears to be general chat or project usage")
        if self._looks_related_to_index(normalized):
            return RouteDecision("rag", "Question overlaps with indexed source vocabulary")
        return RouteDecision("general", "No source-grounding signal detected")

    def _looks_related_to_index(self, normalized_question: str) -> bool:
        query_terms = set(self.knowledge._tokens(normalized_question))
        if not query_terms or not self.knowledge.documents:
            return False
        known_terms = set(self.knowledge.document_frequencies)
        return len(query_terms & known_terms) >= 2
