# Foundry Functional Specification

## 개요

Foundry는 문서 기반 RAG 파이프라인을 만들고 검증하는 인증 없는 FastAPI/Next.js PoC다.

## 기능 목록

| ID | 기능 | 우선순위 | 상태 |
| --- | --- | --- | --- |
| FS-001 | Provider 연결과 모델 동기화 | Must | 구현 |
| FS-002 | 문서 업로드와 index 생성 | Must | 구현 |
| FS-003 | Pipeline draft 생성·수정 | Must | 구현 |
| FS-004 | Pipeline version 저장·rollback | Must | 구현 |
| FS-005 | RAG 채팅 실행 | Must | 구현 |
| FS-006 | SSE streaming | Must | 구현 |
| FS-007 | Citation과 trace 반환 | Must | 구현 |
| FS-008 | Evaluation 실행 | Should | 구현 |
| FS-009 | Deployment endpoint 관리 | Should | 구현 |
| FS-010 | Chat session 관리 | Should | 구현 |
| FS-011 | RAG route 판단 | Must | 구현 |
| FS-012 | Web search fallback | Must | 구현 |
| FS-013 | RAGAS 호환 평가 | Must | 부분 구현 |

## 지원 Source

- `.txt`
- `.md`
- `.json`
- `.html`
- `.pdf`

지원하지 않는 파일 형식은 HTTP 422 validation error를 반환한다.

논문 PDF는 `POST /sources/papers`로도 업로드할 수 있다. 이 endpoint는 PDF만 허용하며, Docling parser를 우선 사용한다. Metadata는 가능한 범위에서 title, authors, abstract, keywords, publication year, section path, page range, source filename, chunk id를 저장한다. 추출이 어려운 항목은 비워두고 filename/page/chunk metadata를 최소 보장한다.

## Pipeline 설정

| 필드 | 설명 |
| --- | --- |
| name | Pipeline 이름 |
| strategy | `rag` 고정 |
| provider | `openai`, `anthropic`, `ollama` |
| model | Provider별 model id |
| system_prompt | 답변 생성 system prompt |
| top_k | 검색 결과 개수 |
| similarity_threshold | 검색 score threshold |

## RAG 실행 흐름

1. 사용자가 pipeline과 질문을 지정한다.
2. LangGraph `analyze_query`와 `route_question`이 질문을 `general`, `rag`, `web_fallback` 중 하나로 분류한다.
3. `general`이면 검색 없이 Provider chat model을 호출한다.
4. `rag`이면 `rewrite_query`로 검색 질의를 정리하고 `select_retrieval_tool`이 keyword/vector/hybrid Tool 중 하나를 선택한다.
5. `retrieve_documents`가 BM25/Kiwi, Chroma, 또는 Hybrid RRF 검색을 실행한다.
6. `rerank_documents`가 BGE reranker wrapper로 후보를 재정렬한다.
7. `grade_context`가 context 충분성을 판단한다.
8. 충분하면 RAG context로 답변하고, 부족하면 `DuckDuckGoSearchRun` web fallback을 실행한다.
9. 답변, route, selected_tool, contexts, web_results, sources, citation, trace, usage metadata를 반환한다.

## RAGAS 평가

`POST /api/v1/evaluations/ragas`는 `question`, `answer`, `contexts`, `ground_truth` 형식의 dataset을 받는다. `ragas`와 judge LLM 설정이 사용 가능하면 Faithfulness, Answer Relevancy, Context Precision, Context Recall을 RAGAS로 계산한다. RAGAS 실행이 불가능한 로컬/테스트 환경에서는 동일한 필드명으로 내부 proxy scorer를 사용해 JSON 결과를 저장한다.

## API 범위

- `/api/v1/health`
- `/api/v1/providers`
- `/api/v1/sources`
- `/api/v1/pipelines`
- `/api/v1/chat`
- `/api/v1/chat/query`
- `/api/v1/chat/stream`
- `/api/v1/rag/query`
- `/api/v1/rag/index`
- `/api/v1/rag/sources`
- `/api/v1/chat/sessions`
- `/api/v1/evaluations/run`
- `/api/v1/deployments`
- `/api/v1/public/{slug}/chat`
