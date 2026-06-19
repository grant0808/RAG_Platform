# Foundry Backend PoC

LangChain으로 RAG, TAG, CAG를 학습하기 위한 인증 없는 FastAPI PoC입니다.

> 경고: 인증과 권한 검사가 없습니다. 인터넷에 직접 공개하지 마세요. Provider API 키는 암호화 저장되지만 모든 API 호출자가 키 교체·삭제와 채팅 실행을 수행할 수 있습니다.

## 구현 범위

- OpenAI·Anthropic API 키 연결, 마스킹, 모델 목록 동기화
- TXT, Markdown, JSON, HTML, PDF, CSV, XLSX 업로드
- LangChain Runnable 기반 RAG·TAG·CAG
- 로컬 hash embedding과 InMemoryVectorStore 기반 RAG
- DuckDB와 read-only SQL 검증 기반 TAG
- TTL cache와 RAG fallback 기반 CAG
- 파이프라인 설정, 버전 저장, rollback
- Preview·Production deployment slug
- 일반 JSON 채팅과 SSE streaming
- 실행 trace, citation, token usage 응답

## 로컬 실행

```bash
cd backend
cp .env.example .env
uv sync
uv run uvicorn foundry.main:app --reload
```

- OpenAPI: <http://localhost:8000/docs>
- Health: <http://localhost:8000/api/v1/health>

Docker:

```bash
cd backend
docker compose up --build
```

## 빠른 사용 순서

1. `PUT /api/v1/providers/openai` 또는 `/anthropic`에 API 키 등록
2. `POST /api/v1/sources/upload`로 문서나 테이블 업로드
3. `POST /api/v1/pipelines`로 전략과 모델 설정
4. `POST /api/v1/chat` 또는 `/chat/stream` 실행
5. `POST /api/v1/pipelines/{id}/versions`로 설정 snapshot 저장
6. `POST /api/v1/deployments`로 공개 slug 생성

SSE event 형식:

```text
event: trace
data: {"step":"retriever","status":"completed",...}

event: token
data: {"text":"..."}

event: citation
data: {"source_id":"...",...}

event: done
data: {"answer":"...",...}
```

## 테스트

```bash
cd backend
uv run pytest
uv run ruff check src tests
```

테스트는 외부 Provider 호출을 fake model로 대체하며 API 키 원문 비노출, RAG citation, TAG SQL 보호, CAG cache, deployment endpoint를 검증합니다.

## PoC 제약

- 인증·RBAC·tenant 격리를 의도적으로 제외했습니다.
- 로컬 hash embedding은 학습 편의를 위한 구현이며 의미 검색 품질 평가용이 아닙니다.
- Source index와 CAG cache는 프로세스 메모리에 있습니다.
- SQLite와 로컬 파일 저장이 기본값입니다.
- GCE 배포 전 PostgreSQL+pgvector, Redis, MinIO Adapter와 migration을 추가해야 합니다.
- TAG는 생성 SQL을 검증하지만 운영 데이터베이스 연결 기능은 아직 없습니다.

