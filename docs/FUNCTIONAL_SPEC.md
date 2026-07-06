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

## 지원 Source

- `.txt`
- `.md`
- `.json`
- `.html`
- `.pdf`

지원하지 않는 파일 형식은 HTTP 422 validation error를 반환한다.

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
2. Knowledge index에서 hybrid search를 실행한다.
3. score threshold 이상인 문서를 context로 구성한다.
4. Provider chat model을 호출한다.
5. 답변, citation, trace, usage metadata를 반환한다.

## API 범위

- `/api/v1/health`
- `/api/v1/providers`
- `/api/v1/sources`
- `/api/v1/pipelines`
- `/api/v1/chat`
- `/api/v1/chat/stream`
- `/api/v1/chat/sessions`
- `/api/v1/evaluations/run`
- `/api/v1/deployments`
- `/api/v1/public/{slug}/chat`
