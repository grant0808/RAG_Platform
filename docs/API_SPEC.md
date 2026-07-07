# Foundry API Specification

Base URL: `/api/v1`

## 공통 오류

애플리케이션 오류는 다음 형식을 사용한다.

```json
{
  "error": {
    "code": "validation_error",
    "message": "Unsupported file type: .csv"
  }
}
```

## Provider

- `GET /providers`
- `PUT /providers/{provider}`
- `POST /providers/{provider}/refresh-models`
- `DELETE /providers/{provider}`

지원 provider는 `openai`, `anthropic`, `ollama`다.

## Sources

- `GET /sources`
- `POST /sources/upload`
- `POST /sources/papers`
- `POST /sources/index`
- `GET /sources/{source_id}`
- `DELETE /sources/{source_id}`

지원 확장자는 `.txt`, `.md`, `.json`, `.html`, `.pdf`다.

`POST /sources/papers`는 AI/컴퓨터 관련 논문 PDF 업로드용 alias이며 PDF만 허용한다. 업로드 후 Docling 기반 text extraction, metadata 정리, chunking, embedding, Chroma indexing이 실행된다.

## Pipelines

- `GET /pipelines`
- `POST /pipelines`
- `GET /pipelines/{pipeline_id}`
- `PATCH /pipelines/{pipeline_id}`
- `DELETE /pipelines/{pipeline_id}`
- `POST /pipelines/{pipeline_id}/versions`
- `GET /pipelines/{pipeline_id}/versions`
- `POST /pipelines/{pipeline_id}/rollback/{version}`

`strategy`는 `rag`만 허용한다.

## Chat

- `POST /chat`
- `POST /chat/query`
- `POST /chat/stream`
- `POST /rag/query`
- `POST /rag/index`
- `GET /rag/sources`

`/chat/stream`은 `trace`, `token`, `citation`, `done`, `error` SSE event를 반환한다.

`/chat/query`는 `/chat`과 동일한 request/response 계약을 사용하는 명시적 query endpoint다. 응답에는 `route`가 포함된다.
`/rag/query`도 같은 계약을 사용하되 LangGraph 기반 RAG 질의 endpoint로 노출한다.
요청은 기존 `session_id`/`message`와 새 `conversation_id`/`query`를 모두 지원한다.

- `general`: RAG가 필요 없는 일반 질문
- `rag`: 업로드 문서/source 기반 질문
- `web_fallback`: RAG 검색 결과가 없거나 threshold 미만이거나 최신/외부 자료가 필요한 질문

응답에는 LangGraph 실행 결과가 포함된다.

```json
{
  "conversation_id": "chat-session-id",
  "message_id": "assistant-message-id",
  "query": "논문에서 method와 result를 비교해줘",
  "rewritten_query": "method result comparison",
  "route": "rag",
  "selected_tool": "hybrid_search_healthcare_pdf",
  "contexts": [
    {
      "content": "chunk text",
      "score": 0.82,
      "rerank_score": 0.64,
      "metadata": {
        "source": "paper.pdf",
        "page": 4,
        "chunk_id": "42"
      }
    }
  ],
  "web_results": [],
  "sources": [
    {
      "type": "pdf",
      "source": "paper.pdf",
      "page": 4,
      "chunk_id": "42"
    }
  ],
  "embedding_model": "BAAI/bge-m3",
  "reranker_model": "BAAI/bge-reranker-v2-m3",
  "memory_used": true,
  "history_count": 4,
  "created_at": "2026-07-07T00:00:00Z"
}
```

검색 도구는 다음 3개로 분리되어 LangChain Tool 형태로도 노출된다.

- `keyword_search_healthcare_pdf`: BM25/Kiwi 기반 keyword search
- `vector_search_healthcare_pdf`: Chroma vector search
- `hybrid_search_healthcare_pdf`: BM25 + Chroma + RRF hybrid search

LangGraph 노드 흐름은 다음과 같다.

```text
analyze_query
→ route_question
→ rewrite_query
→ select_retrieval_tool
→ retrieve_documents
→ rerank_documents
→ grade_context
→ generate_rag_answer 또는 web_search_fallback 또는 generate_general_answer
→ finalize_response
```

`grade_context`가 context 부족으로 판단하면 `DuckDuckGoSearchRun` 기반 web fallback이 실행된다.

## Chat Sessions

- `POST /chat/sessions`
- `GET /chat/sessions`
- `PATCH /chat/sessions/{session_id}`
- `DELETE /chat/sessions/{session_id}`
- `GET /chat/sessions/{session_id}/messages`

`/conversations` alias도 제공한다.

- `POST /conversations`
- `GET /conversations`
- `GET /conversations/{conversation_id}/messages`

Message 응답은 `message_id`, `conversation_id`, `role`, `content`, `route`, `selected_tool`, `sources`, `created_at`을 포함한다. `conversation_id`는 현재 내부 `chat_sessions.id`와 동일하다.

Conversation memory는 `FOUNDRY_MEMORY_ENABLED=true`, `FOUNDRY_MEMORY_WINDOW_SIZE=6`이 기본값이다. 전체 history를 무한정 prompt에 넣지 않고 최근 window만 query rewrite와 답변 prompt에 사용한다.

## Evaluation

- `POST /evaluations/run`
- `POST /evaluations/ragas`
- `GET /evaluations/ragas`
- `POST /rag/evaluate`
- `GET /rag/evaluations`

`POST /evaluations/ragas`와 `POST /rag/evaluate`는 같은 기능이다. RAGAS 호환 dataset을 받아 pipeline을 실행하고 평가 결과 JSON을 `.data/evaluations`에 저장한다.

```json
{
  "pipeline_id": "pipeline-id",
  "run_name": "bge-m3-baseline",
  "dataset": [
    {
      "question": "이 논문의 핵심 contribution은?",
      "ground_truth": "기준 답변",
      "contexts": []
    }
  ]
}
```

## Deployments

- `GET /deployments`
- `POST /deployments`
- `PATCH /deployments/{deployment_id}`
- `POST /deployments/{deployment_id}/run`
- `POST /deployments/{deployment_id}/stop`
- `DELETE /deployments/{deployment_id}`
- `POST /public/{slug}/chat`
