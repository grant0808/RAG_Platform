# Foundry PRD

Foundry는 사용자가 문서 기반 RAG 파이프라인을 구성, 평가, 버전 관리 및 배포하는 LLMOps workbench다.

## 목표

- 문서를 업로드하면 검색 가능한 knowledge index를 자동 생성한다.
- Provider, model, system prompt, top K, similarity threshold를 UI와 API에서 조정한다.
- 채팅 실행 시 답변, citation, LangChain trace, token usage를 함께 확인한다.
- 파이프라인 draft를 immutable version으로 저장하고 deployment slug로 노출한다.

## 주요 기능

| ID | 기능 | 설명 |
| --- | --- | --- |
| FR-01 | Provider 연결 | OpenAI, Anthropic, Ollama provider 연결과 모델 목록 동기화 |
| FR-02 | Source 관리 | TXT, Markdown, JSON, HTML, PDF 업로드·삭제 |
| FR-03 | RAG 실행 | 문서 검색 결과를 context로 사용해 grounded answer 생성 |
| FR-04 | Pipeline 관리 | draft 수정, version 저장, rollback |
| FR-05 | Playground | 일반 채팅과 SSE streaming, citation, trace 표시 |
| FR-06 | Evaluation | 기본 test query 실행과 latency, cost, accuracy 요약 |
| FR-07 | Deployment | preview/production endpoint 생성과 실행 상태 관리 |

## 범위 제외

- 테이블 질의, SQL 생성, 동적 테이블 catalog
- 캐시 기반 답변 전략과 cache lifecycle API
- 자동 전략 라우팅

## 성공 기준

- 문서 업로드 후 RAG 채팅에서 citation이 반환된다.
- SSE stream이 trace, token, citation, done event를 안정적으로 전달한다.
- 저장된 deployment는 생성 시점의 immutable pipeline version을 사용한다.
- backend test와 frontend verify가 통과한다.
