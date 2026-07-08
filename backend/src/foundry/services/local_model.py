from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk


class LocalFakeChatModel:
    """Deterministic chat model used only when local fake mode is explicitly enabled."""

    async def ainvoke(self, messages: list[Any]) -> AIMessage:
        del messages
        return AIMessage(
            content=(
                "로컬 deterministic 테스트 모델의 응답입니다. API, 검색 컨텍스트, citation, "
                "trace, 공통 응답 계약이 정상 동작하는지 확인했습니다."
            ),
            usage_metadata={"input_tokens": 24, "output_tokens": 18, "total_tokens": 42},
        )

    async def astream(self, messages: list[Any]):
        del messages
        yield AIMessageChunk(content="로컬 테스트 모델이 ")
        yield AIMessageChunk(
            content="deterministic 응답을 스트리밍하고 있습니다.",
            usage_metadata={"input_tokens": 24, "output_tokens": 10, "total_tokens": 34},
        )
