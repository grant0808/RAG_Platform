# RAG Platform

- [Quick start](#quick-start)
- [PRD](./PRD.md)
- [Architecture](./ARCHITECTURE.md)
- [Technology stack](./TECH_STACK.md)
- [Interactive mockup](./index.html)
- [Backend PoC](./backend/README.md)
- [Frontend application](./frontend/README.md)
- [API specification](./API_SPEC.md)
- [ERD](./ERD.md)

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

Validation:

```bash
cd backend && uv run pytest && uv run ruff check src tests
cd ../frontend && npm run verify
```
