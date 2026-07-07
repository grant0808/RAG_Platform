# RAG Platform

- [Quick start](#quick-start)
- [PRD](./docs/PRD.md)
- [Requirements specification](./docs/REQUIREMENTS_SPEC.md)
- [Architecture](./docs/ARCHITECTURE.md)
- [Technology stack](./docs/TECH_STACK.md)
- [Interactive mockup](./index.html)
- [Backend PoC](./backend/README.md)
- [Frontend application](./frontend/README.md)
- [API specification](./docs/API_SPEC.md)
- [RAG/RAGAS guide](./docs/RAG_RAGAS_GUIDE.md)
- [ERD](https://dbdiagram.io/d/RAG-6a4a765e4ac62e474c31c8d5)

## Quick start

Backend terminal:

```bash
cd backend
cp .env.example .env
# Add FOUNDRY_OPENAI_API_KEY or FOUNDRY_OPENAI_EMBEDDING_API_KEY to backend/.env.
docker compose up -d postgres
uv sync
uv run foundry-local bootstrap
uv run uvicorn foundry.main:app --reload
```

Frontend terminal:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>. The frontend uses `frontend/.env.local` and points to `http://localhost:8000/api/v1` by default.

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

Validation:

```bash
cd backend && uv run pytest && uv run ruff check src tests
cd ../frontend && npm run verify
```
