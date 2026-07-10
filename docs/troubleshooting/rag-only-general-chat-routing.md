# RAG-only 구현에서 일반 인사/대화가 답변되지 않는 문제

## 증상

초기 RAG 기본 기능만 구현했을 때 Playground에서 다음처럼 문서 근거가 필요 없는 입력을 보내면 답변하지 못하는 현상이 발생했다.

```text
안녕
```

대표적인 실패 양상:

- RAG 검색을 항상 실행한다.
- 단순 인사에는 관련 chunk가 없으므로 검색 결과가 0건이거나 threshold 미만이다.
- 검색 context가 없다는 이유로 답변 생성이 중단된다.
- 사용자는 일반 대화도 불가능한 것처럼 보인다.

## 원인

RAG-only 구조에서는 모든 질문을 같은 pipeline으로 처리한다.

```text
사용자 질문
→ vector search
→ context 없음
→ 답변 불가 또는 fallback error
```

이 구조의 문제는 질문 유형을 구분하지 않는다는 점이다.

- “논문에서 method 설명해줘”는 source-grounded RAG 질문이다.
- “안녕”은 retrieval이 필요 없는 일반 대화다.
- “최신 모델 가격 알려줘”는 업로드 문서보다 웹 검색이 필요한 질문이다.

그런데 RAG-only 구조에서는 세 질문이 모두 검색 pipeline으로 들어간다. 따라서 일반 질문도 “검색 실패”로 처리된다.

## 해결 방향

LangGraph 기반 질문 처리 workflow를 추가해서 질문을 먼저 분석하고 route를 분기한다.

현재 처리 흐름:

```text
사용자 질문
→ analyze_query
→ route_question
→ general 또는 rag 또는 web_fallback
→ general이면 검색 없이 일반 LLM 답변
→ rag이면 query rewrite + retrieval + rerank + context grading
→ context 부족 또는 외부 최신 정보 필요 시 web_fallback
→ finalize_response
```

핵심은 RAG를 “항상 실행”하지 않고, 필요한 질문에서만 실행하는 것이다.

## 구현된 해결책

### 1. RagRouter로 질문 유형 판단

`RagRouter`는 질문에 문서/source 근거가 필요한지 판단한다.

일반 route 예시:

- `안녕`
- `고마워`
- `이 서비스 어떻게 써?`
- source 기반이 아닌 일반 코딩 질문

RAG route 예시:

- `논문에서 contribution을 설명해줘`
- `업로드한 PDF 기준으로 method와 result를 비교해줘`
- `source 근거와 함께 알려줘`

Web fallback route 예시:

- `최신 정보 찾아줘`
- `웹에서 검색해줘`
- 업로드 문서에 없는 외부 자료가 필요한 질문

관련 파일:

- `backend/src/foundry/services/rag_router.py`

### 2. LangGraph workflow로 분기 명시

LangGraph workflow는 다음 노드를 기준으로 질문 처리 경로를 분리한다.

```text
analyze_query
route_question
rewrite_query
select_retrieval_tool
retrieve_documents
rerank_documents
grade_context
generate_rag_answer
web_search_fallback
generate_general_answer
finalize_response
```

`route_question` 결과가 `general`이면 retrieval을 건너뛰고 `generate_general_answer`로 이동한다.

관련 파일:

- `backend/src/foundry/services/langgraph_workflow.py`

### 3. Orchestrator에서 general context 준비

일반 질문은 검색 context 없이 provider chat model을 호출한다.

이때 내부 context는 다음처럼 명확히 표시된다.

```text
No retrieved context was requested for this general question.
```

따라서 “안녕” 같은 입력은 source 검색 실패가 아니라 일반 대화로 처리된다.

관련 파일:

- `backend/src/foundry/services/orchestrator.py`

## 기대 동작

### 입력: 일반 인사

```text
안녕
```

기대 route:

```json
{
  "route": "general",
  "selected_tool": "none",
  "contexts": []
}
```

동작:

- RAG 검색 미실행
- vector DB context 요구하지 않음
- 일반 LLM 답변 생성

### 입력: 논문 기반 질문

```text
업로드한 논문에서 method를 설명해줘
```

기대 route:

```json
{
  "route": "rag",
  "selected_tool": "hybrid_search_healthcare_pdf"
}
```

동작:

- query rewrite
- retrieval tool 선택
- BM25/Chroma/Hybrid 검색
- BGE reranker
- context 충분성 판단
- source 포함 답변 생성

### 입력: RAG context 부족

```text
이 주제의 최신 연구 동향을 웹에서 찾아줘
```

기대 route:

```json
{
  "route": "web_fallback"
}
```

동작:

- 업로드 문서 검색 결과가 없거나 부족하면 DuckDuckGo fallback 실행
- PDF source와 web source를 구분해 반환

## 확인 방법

backend 실행 후 Playground 또는 API로 확인한다.

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"안녕"}'
```

응답에서 다음을 확인한다.

- `route`가 `general`
- `contexts`가 비어 있음
- `selected_tool`이 없거나 `none`
- 답변이 정상 생성됨

stream endpoint 확인:

```bash
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"안녕"}'
```

## 재발 방지 체크리스트

- RAG 검색을 모든 질문의 기본 경로로 두지 않는다.
- 질문 처리 앞단에 route 판단을 둔다.
- `general`, `rag`, `web_fallback` route를 응답 schema에 명시한다.
- 일반 질문 테스트를 RAG 테스트와 별도로 둔다.
- RAG context가 없어도 general route는 실패로 처리하지 않는다.
- context 부족은 `rag` 내부 실패가 아니라 `web_fallback` 후보로 처리한다.

## 관련 문서

- `docs/RAG_RAGAS_GUIDE.md`
- `docs/API_SPEC.md`
- `docs/ARCHITECTURE.md`
- `docs/FUNCTIONAL_SPEC.md`

