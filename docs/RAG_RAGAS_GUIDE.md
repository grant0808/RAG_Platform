# RAG / RAGAS Guide

## 구현 범위

현재 구현은 FastAPI 기반 최소 동작 범위다.

- AI/컴퓨터 논문 PDF source 업로드: `POST /api/v1/sources/papers`
- Parser: Docling 기본값, pypdf fallback 가능
- Chunking: Docling `HybridChunker` 또는 LangChain `RecursiveCharacterTextSplitter`
- Embedding: Hugging Face `BAAI/bge-m3` 기본 고정
- Vector DB: Chroma 기본값
- Query workflow: LangGraph 기반 `analyze_query → route_question → rewrite_query → select_retrieval_tool → retrieve_documents → rerank_documents → grade_context`
- Conversation memory: `chat_sessions`/`chat_messages` 기반 최근 N개 message window를 query rewrite와 답변 prompt에 반영
- Query route: `general`, `rag`, `web_fallback`
- Retrieval tools: `keyword_search_healthcare_pdf`, `vector_search_healthcare_pdf`, `hybrid_search_healthcare_pdf`
- Hybrid search: BM25/Kiwi optional tokenizer + Chroma vector search + RRF
- Reranker: `BAAI/bge-reranker-v2-m3` 설정, 기본은 lightweight lexical fallback, `RERANKER_LOAD_MODEL=true`에서 CrossEncoder 로딩
- Web fallback: LangChain `DuckDuckGoSearchRun` 우선, Tavily 또는 `none` provider 설정 지원
- RAGAS 평가: JSON/CSV dataset 입력, JSON result 저장, RAGAS metric 실행 또는 proxy fallback

## 환경 변수

| 설정값 | 기본값 | 설명 |
| --- | --- | --- |
| `FOUNDRY_HUGGINGFACE_EMBEDDING_MODEL` | `BAAI/bge-m3` | 고정 embedding model |
| `EMBEDDING_MODEL_NAME` | `BAAI/bge-m3` | non-prefixed alias |
| `FOUNDRY_VECTOR_STORE_PROVIDER` | `chroma` | `chroma`, `postgres`, `memory` |
| `VECTOR_STORE_TYPE` | `chroma` | non-prefixed alias |
| `FOUNDRY_CHROMA_PERSIST_DIR` | `.data/chroma` | Chroma persist directory |
| `VECTOR_STORE_DIR` | `.data/chroma` | non-prefixed alias |
| `FOUNDRY_SOURCE_PAPER_DIR` | `source/papers` | 논문 PDF source directory |
| `FOUNDRY_RAG_ENABLED` | `true` | 조건부 RAG 활성화 |
| `FOUNDRY_RAG_TOP_K` | `10` | Retrieval top-k |
| `FOUNDRY_FINAL_CONTEXT_TOP_K` | `5` | rerank 후 최종 context 수 |
| `FOUNDRY_RAG_SCORE_THRESHOLD` | `0.35` | Context 충분성 threshold |
| `FOUNDRY_RAG_CHUNK_SIZE` | `1000` | Text splitter chunk size |
| `FOUNDRY_RAG_CHUNK_OVERLAP` | `150` | Text splitter overlap |
| `FOUNDRY_BM25_INDEX_DIR` | `.data/bm25` | BM25 index/cache directory |
| `FOUNDRY_KIWI_ENABLED` | `true` | Kiwi tokenizer 사용. 미설치 시 regex fallback |
| `FOUNDRY_RRF_K` | `60` | Reciprocal Rank Fusion k |
| `FOUNDRY_RERANKER_ENABLED` | `true` | reranker 단계 활성화 |
| `FOUNDRY_RERANKER_MODEL_NAME` | `BAAI/bge-reranker-v2-m3` | reranker 모델명 |
| `FOUNDRY_RERANKER_LOAD_MODEL` | `false` | 실제 CrossEncoder 모델 로딩 여부 |
| `FOUNDRY_RERANK_TOP_N` | `10` | reranker 입력 후보 수 |
| `FOUNDRY_RERANK_SCORE_THRESHOLD` | `0.2` | rerank 결과 필터 threshold |
| `FOUNDRY_MIN_CONTEXT_COUNT` | `2` | 충분한 context 최소 개수 |
| `FOUNDRY_WEB_FALLBACK_PROVIDER` | `duckduckgo` | 주 web fallback provider |
| `FOUNDRY_WEB_SEARCH_PROVIDER` | `duckduckgo` | 보조 web search provider. `tavily` 사용 시 API key 필요 |
| `FOUNDRY_DUCKDUCKGO_MAX_RESULTS` | `5` | DuckDuckGo 검색 결과 수 |
| `FOUNDRY_TAVILY_API_KEY` | empty | Tavily 사용 시 필요 |
| `FOUNDRY_RAGAS_RESULTS_DIR` | `.data/evaluations` | 평가 결과 JSON 저장 위치 |
| `FOUNDRY_LANGGRAPH_TRACE_ENABLED` | `false` | LangGraph trace 확장 옵션 |
| `FOUNDRY_MEMORY_ENABLED` | `true` | conversation memory 사용 여부 |
| `FOUNDRY_MEMORY_WINDOW_SIZE` | `6` | prompt와 rewrite에 반영할 최근 message 수 |
| `FOUNDRY_MEMORY_SUMMARY_ENABLED` | `false` | 장기 memory summary 예약 설정. 현재는 window memory만 사용 |
| `FOUNDRY_OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama base URL |

`BAAI/bge-m3`는 한국어/영어를 모두 다루는 multilingual embedding model이라 논문/기술문서 검색 기본값으로 사용한다. 로컬 장비에서 무거우면 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`로 바꿀 수 있지만, baseline 비교를 위해 한 번 정한 모델은 평가 run 단위에서 고정해야 한다.

## RAG 처리 흐름

```text
사용자 질문
→ user message 저장
→ 최근 conversation history load(window 제한)
→ analyze_query
→ route_question
→ general 또는 rag/web_fallback route 선택
→ rewrite_query(history가 필요한 후속 질문이면 최근 user turn 키워드 보강)
→ select_retrieval_tool
→ retrieve_documents
→ rerank_documents
→ context 충분성 판단
→ 충분하면 RAG 답변
→ 부족하면 DuckDuckGoSearchRun web fallback
→ assistant message 저장
→ 최종 답변 + conversation_id/message_id/sources/memory metadata 반환
```

RAG router는 “논문에서”, “문서 기준”, “source”, “근거”, “업로드한 PDF” 같은 표현이 있으면 RAG를 실행한다. 단순 인사, 설정/사용법, 일반 대화는 `general`로 처리한다. “최신”, “웹”, “인터넷 검색” 같은 표현은 바로 `web_fallback`으로 보낸다.

## 검색 도구 선택

| Tool | 기술 | 사용 상황 |
| --- | --- | --- |
| `keyword_search_healthcare_pdf` | BM25 + Kiwi optional tokenizer | 모델명, 데이터셋명, 표/수식 번호, 정확한 용어 검색 |
| `vector_search_healthcare_pdf` | Chroma vector search + `BAAI/bge-m3` | 개념 설명, 유사 표현, 의미 기반 검색 |
| `hybrid_search_healthcare_pdf` | BM25 + Chroma + RRF | 논문 핵심 내용, 실험 결과, 한계점, 비교 분석 |

Tool 선택은 현재 rule-based selector로 동작한다. 추후 provider key와 tool-calling model 정책이 정해지면 LLM Agent selector로 교체할 수 있다.

## API 예시

```bash
curl -F "file=@paper.pdf" http://localhost:8000/api/v1/sources/papers
curl -X POST http://localhost:8000/api/v1/sources/index
```

```bash
curl -X POST http://localhost:8000/api/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{"pipeline_id":"PIPELINE_ID","message":"이 논문의 핵심 contribution을 설명해줘"}'
```

```bash
curl -X POST http://localhost:8000/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{"pipeline_id":"PIPELINE_ID","message":"논문에서 method와 result를 비교해줘"}'
```

## RAGAS 평가 dataset

```json
[
  {
    "question": "이 논문의 핵심 contribution은?",
    "answer": "",
    "contexts": [],
    "ground_truth": "기준 답변"
  }
]
```

`answer`와 `contexts`가 비어 있으면 평가 실행 시 현재 pipeline으로 답변과 context를 생성한다.

```bash
curl -X POST http://localhost:8000/api/v1/evaluations/ragas \
  -H "Content-Type: application/json" \
  -d '{"pipeline_id":"PIPELINE_ID","run_name":"bge-m3-baseline","dataset":[{"question":"핵심 방법론은?","ground_truth":"기준 답변"}]}'
```

결과는 `.data/evaluations/{run_id}.json`에 저장된다. CSV dataset은 `question`, `answer`, `contexts`, `ground_truth` 컬럼을 사용하며, `contexts`는 JSON 배열 문자열 또는 `||` 구분 문자열을 허용한다.

## 후속 작업

- 평가 dataset CRUD와 UI
- 논문별 authors/venue/DOI/arXiv metadata 고정밀 추출
- LLM Agent 기반 retrieval tool selector
- `RERANKER_LOAD_MODEL=true` 운영 환경에서 BGE reranker latency/memory 검증
- Tavily 외 Brave/SerpAPI provider 추가
