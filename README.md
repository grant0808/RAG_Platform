# RAG Platform

Foundry는 문서와 테이블 데이터를 업로드하고 RAG, TAG, CAG 전략으로 질의 실행, trace 확인, 버전 관리, 배포 테스트까지 해볼 수 있는 LangChain 기반 PoC입니다.

이 저장소는 FastAPI 백엔드와 Next.js 프론트엔드를 함께 포함합니다.

## 주요 기능

- Source 업로드: TXT, Markdown, JSON, HTML, PDF, CSV, XLSX, XLSM
- 다중 파일 업로드: Sources 화면에서 여러 파일 선택 또는 드래그 앤 드롭
- PDF 처리: 논문 PDF 같은 긴 문서를 chunk로 분할하고 citation metadata 생성
- RAG: 문서 검색 기반 답변, citation, retriever/reranker trace
- TAG: CSV/Excel을 DuckDB 테이블로 적재하고 read-only SQL 검증
- CAG: 질문 단위 TTL cache, miss 시 RAG fallback
- Provider 관리: OpenAI, Anthropic API key 등록, 마스킹 저장, 모델 목록 갱신
- OpenAI key 연동: Provider에 OpenAI key를 입력하면 embedding key로도 사용
- Streaming Playground: SSE token, citation, trace event 표시
- Provider quota 대응: OpenAI quota 429 발생 시 local model fallback
- Pipeline 관리: draft 수정, immutable version 저장, rollback
- Deployment: preview/production slug와 public chat endpoint 생성

## 구조

```text
backend/   FastAPI, SQLAlchemy, LangChain runtime, DuckDB, source ingestion
frontend/  Next.js App Router workbench UI
journal/   로컬 테스트용 PDF 자료
```

주요 문서:

- [PRD](./docs/PRD.md)
- [Requirements specification](./docs/REQUIREMENTS_SPEC.md)
- [Architecture](./docs/ARCHITECTURE.md)
- [Functional specification](./docs/FUNCTIONAL_SPEC.md)
- [Technology stack](./docs/TECH_STACK.md)
- [API specification](./docs/API_SPEC.md)
- [RAG/RAGAS guide](./docs/RAG_RAGAS_GUIDE.md)
- [ERD (Interactive mockup)](./index.html)
- [ERD (dbdiagram)](https://dbdiagram.io/d/RAG-6a4a765e4ac62e474c31c8d5)
- [Backend README](./backend/README.md)
- [Frontend README](./frontend/README.md)


## 빠른 실행

터미널 1, 백엔드:

```bash
cd backend
cp .env.example .env
# Add FOUNDRY_OPENAI_API_KEY or FOUNDRY_OPENAI_EMBEDDING_API_KEY to backend/.env.
docker compose up -d postgres
uv sync
uv run foundry-local bootstrap
uv run uvicorn foundry.main:app --reload
```

터미널 2, 프론트엔드:

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

브라우저에서 <http://localhost:3000>을 엽니다.

- Backend API: <http://localhost:8000/api/v1>
- OpenAPI: <http://localhost:8000/docs>
- Health: <http://localhost:8000/api/v1/health>

### Local RAG 구성 가이드
For a local Ollama-backed RAG run, keep `backend/.env` on `FOUNDRY_EMBEDDING_PROVIDER=huggingface`, `FOUNDRY_VECTOR_STORE_PROVIDER=chroma`, and `FOUNDRY_PDF_PARSER=docling`, run Ollama locally, and register the Ollama provider in the UI with `http://localhost:11434`. For an OpenAI-backed run, switch `FOUNDRY_EMBEDDING_PROVIDER=openai` and register the OpenAI provider. For a key-free smoke run, switch backend `.env` to `FOUNDRY_FAKE_LLM_ENABLED=true`, `FOUNDRY_EMBEDDING_PROVIDER=local`, `FOUNDRY_VECTOR_STORE_PROVIDER=memory`, `FOUNDRY_PDF_PARSER=pypdf`, and `FOUNDRY_DATABASE_URL=sqlite+aiosqlite:///./.data/foundry.db`.

Paper RAG entrypoints:

```bash
curl -F "file=@paper.pdf" http://localhost:8000/api/v1/sources/papers
curl -X POST http://localhost:8000/api/v1/rag/index
curl -X POST http://localhost:8000/api/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{"pipeline_id":"PIPELINE_ID","message":"이 논문의 핵심 contribution을 설명해줘"}'
curl -X POST http://localhost:8000/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"pipeline_id":"PIPELINE_ID","conversation_id":null,"query":"논문에서 method와 result를 비교해줘"}'
```

RAG query는 LangGraph 기반으로 `analyze_query → route_question → rewrite_query → select_retrieval_tool → retrieve_documents → rerank_documents → grade_context`를 실행한다. `conversation_id`가 있으면 최근 `FOUNDRY_MEMORY_WINDOW_SIZE`개 메시지를 query rewrite와 답변 prompt에 보조 맥락으로 반영한다. Context가 부족하면 `DuckDuckGoSearchRun` web fallback을 사용하며, fallback을 끄려면 `FOUNDRY_WEB_FALLBACK_PROVIDER=none`을 설정한다.

## 기본 로컬 모드

`backend/.env.example`은 외부 Provider 비용 없이 실행되는 로컬 모드를 기본으로 둡니다.

```env
FOUNDRY_FAKE_LLM_ENABLED=true
FOUNDRY_DATABASE_URL=sqlite+aiosqlite:///./.data/foundry.db
```

이 모드에서는 deterministic local model을 사용하므로 OpenAI 또는 Anthropic API key가 없어도 업로드, 검색, trace, citation, streaming 흐름을 검증할 수 있습니다.

## 실제 OpenAI 사용

실제 OpenAI 응답을 사용하려면:

1. `backend/.env`에서 `FOUNDRY_FAKE_LLM_ENABLED=false`로 변경
2. 백엔드 재시작
3. 프론트 Providers 화면에서 OpenAI API key 등록
4. Pipeline의 model이 `gpt-4o-mini` 또는 사용 가능한 모델인지 확인

주의:

- ChatGPT Plus 구독은 OpenAI API 크레딧이 아닙니다.
- API 사용은 <https://platform.openai.com>의 별도 billing/quota를 사용합니다.
- API quota가 없으면 OpenAI는 `429 insufficient_quota`를 반환합니다.
- 이 프로젝트는 quota 초과 시 PoC 테스트가 멈추지 않도록 local model로 fallback하고 trace에 `fallback: "local_model"`을 남깁니다.

## 사용 흐름

1. Providers에서 OpenAI 또는 Anthropic key 연결
2. Sources에서 문서/PDF/테이블 파일 업로드
3. Pipeline에서 RAG, TAG, CAG 전략과 model 설정
4. Playground에서 질문 실행
5. Trace rail에서 retriever, tool, cache, model 단계 확인
6. 필요하면 Pipeline version 저장 또는 rollback
7. Deployments에서 preview/production endpoint 생성

## Source 업로드

Sources 화면은 여러 파일을 한 번에 받을 수 있습니다.

- 파일 선택 창에서 여러 파일 선택
- 드롭존에 여러 파일 드래그 앤 드롭
- 각 파일은 기존 `/api/v1/sources/upload` API로 순차 업로드
- 일부 파일이 실패해도 나머지 파일 업로드는 계속 진행

PDF 업로드는 `pypdf` 기반 텍스트 추출 후 chunking합니다. `journal/2024.emnlp-main.981.pdf`는 로컬 검증 기준 118 chunks로 업로드됩니다.

## API 예시

Provider 연결:

```bash
curl -X PUT http://localhost:8000/api/v1/providers/openai \
  -H 'Content-Type: application/json' \
  -d '{"api_key":"sk-...","validate_connection":false}'
```

Source 업로드:

```bash
curl -X POST http://localhost:8000/api/v1/sources/upload \
  -F 'file=@./journal/2024.emnlp-main.981.pdf'
```

Chat 실행:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"pipeline_id":"<PIPELINE_ID>","message":"RAG best practices는?"}'
```

Public deployment chat:

```bash
curl -X POST http://localhost:8000/api/v1/public/local-rag-preview/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Foundry의 응답 속도 목표는?"}'
```

## 상태 확인

Playground에서 `/status`를 입력하면 현재 chat session의 내부 token 사용량과 Provider quota 조회 결과를 볼 수 있습니다.

Admin usage/cost 조회가 필요하면 `backend/.env`에 별도 Admin key를 설정합니다.

```env
FOUNDRY_OPENAI_ADMIN_API_KEY=
FOUNDRY_ANTHROPIC_ADMIN_API_KEY=
```

이 key는 Providers 화면에 입력하는 inference key와 별개입니다.

## 검증

백엔드:

```bash
cd backend
uv run pytest
uv run ruff check src tests
```

프론트엔드:

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```

## Docker

```bash
cd backend
docker compose up --build
```

컨테이너에서 seed 데이터를 넣으려면:

```bash
docker compose exec api uv run foundry-local bootstrap
```

## 보안 주의

이 프로젝트는 학습용 PoC입니다.

- 인증, 권한, tenant 격리가 없습니다.
- Provider API key는 암호화 저장되지만 API 호출자는 key 교체와 채팅 실행을 할 수 있습니다.
- 인터넷에 직접 공개하지 마세요.
- 운영 배포 전 인증, RBAC, migration, object storage, secret manager, rate limit을 추가해야 합니다.

## 현재 제약

- Source index와 CAG cache는 프로세스 메모리 기반입니다.
- SQLite와 로컬 파일 저장이 기본 개발 경로입니다.
- pgvector, Redis, MinIO/GCS 같은 운영 구성은 후속 작업 대상입니다.
- TAG는 업로드된 CSV/Excel에 대한 안전한 read-only 질의에 초점을 둡니다.
- Provider quota 초과 시 local fallback은 개발 편의를 위한 동작이며 실제 모델 품질 평가에는 사용할 수 없습니다.
