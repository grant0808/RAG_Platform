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
- LangChain Runnable, Retriever, ChatModel, Tool
- LangGraph StateGraph
- SSE streaming

## AI/RAG

- Embeddings: Hugging Face `BAAI/bge-m3` 기본 고정
- Vector store: Chroma, collection 기본값 `healthcare_pdf_papers`
- Keyword search: BM25, Kiwi tokenizer optional
- Hybrid search: BM25 + Chroma + Reciprocal Rank Fusion
- Query rewrite: rule-based fallback, LLM rewrite는 후속 작업
- Retrieval tools: `keyword_search_healthcare_pdf`, `vector_search_healthcare_pdf`, `hybrid_search_healthcare_pdf`
- Reranker: `BAAI/bge-reranker-v2-m3` 설정, 기본은 lexical fallback, `RERANKER_LOAD_MODEL=true`에서 CrossEncoder 로딩
- Providers: OpenAI, Anthropic, Ollama
- PDF parser: Docling 우선, fallback parser로 pypdf 지원
- Web fallback: LangChain `DuckDuckGoSearchRun` 우선, dummy/Tavily graceful fallback
- Evaluation: RAGAS 호환 JSON dataset/result, proxy metric scorer

## Storage

- Metadata DB: PostgreSQL
- Uploaded files: local filesystem
- Credential encryption: local master key 기반 암호화

## Local Development

- Backend package manager: uv
- Frontend package manager: npm
- Test: pytest, ruff, Next.js lint/typecheck/build

## Deployment Baseline

- Docker Compose: API + PostgreSQL
- Preview/production deployment metadata는 API DB에 저장한다.
