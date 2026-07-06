# LangChain 기반 RAG 플랫폼 기술 스택

## Frontend

- Next.js App Router
- React
- TypeScript
- CSS modules/global stylesheet

## Backend

- FastAPI
- Pydantic
- SQLAlchemy async
- LangChain Runnable, Retriever, ChatModel
- SSE streaming

## AI/RAG

- Embeddings: Hugging Face, OpenAI, local hash embedding
- Vector store: PostgreSQL + pgvector 또는 in-memory
- Providers: OpenAI, Anthropic, Ollama

## Storage

- Metadata DB: PostgreSQL 또는 SQLite
- Uploaded files: local filesystem
- Credential encryption: local master key 기반 암호화

## Local Development

- Backend package manager: uv
- Frontend package manager: npm
- Test: pytest, ruff, Next.js lint/typecheck/build

## Deployment Baseline

- Docker Compose: API + PostgreSQL
- Preview/production deployment metadata는 API DB에 저장한다.
