# Foundry 기능명세서

## 1. 문서 정보

| 항목 | 내용 |
|---|---|
| 제품명 | Foundry — LLMOps 기반 개인화 AI 챗봇 플랫폼 |
| 문서 버전 | v1.0 |
| 기준 문서 | `PRD.md` v1.3, `ARCHITECTURE.md` v1.3, `TECH_STACK.md`, UI 목업 |
| 기준 구현 | `backend/` FastAPI PoC |
| 대상 독자 | 기획자, 백엔드·프론트엔드 개발자, QA, 운영 담당자 |
| 작성 목적 | 제품 기능, 입출력, 처리 규칙, 예외 및 인수 조건 정의 |

### 1.1 상태 정의

| 상태 | 의미 |
|---|---|
| 구현 완료 | 현재 backend에서 핵심 흐름과 API가 동작하고 테스트가 존재함 |
| 부분 구현 | PoC 수준으로 동작하지만 운영 요구사항 또는 일부 입력 방식이 빠져 있음 |
| 미구현 | 명세에는 필요하지만 현재 backend에 구현되지 않음 |

## 2. 제품 개요

Foundry는 사용자가 문서와 테이블 데이터를 연결하고 RAG·TAG·CAG 전략을 선택하여 AI 챗봇 파이프라인을 구성, 평가, 버전 관리 및 배포하는 플랫폼이다.

핵심 사용자 흐름은 다음과 같다.

`Provider 연결 → 데이터 소스 등록 → 파이프라인 구성 → Playground 테스트 → 평가 → 버전 저장 → 배포 → 모니터링`

## 3. 사용자 및 권한

| 역할 | 주요 권한 | 현재 상태 |
|---|---|---|
| Workspace Admin | Provider 키 관리, 사용자·권한 관리, 모든 리소스 관리 | 미구현 |
| Developer | 데이터 소스, 파이프라인, 평가, 배포 관리 | 미구현 |
| Viewer | 설정과 실행 결과 조회 | 미구현 |
| Public User | 배포된 챗봇 질의 | 부분 구현 |

현재 backend는 인증이 없는 PoC다. 운영 환경에서는 JWT 인증, 역할 기반 접근 제어, `tenant_id` 기반 데이터 격리를 모든 관리 API에 적용해야 한다.

## 4. 기능 목록

| 기능 ID | 기능명 | 우선순위 | 상태 |
|---|---|---:|---|
| FS-001 | Provider 연결 관리 | Must | 부분 구현 |
| FS-002 | Provider 모델 탐색 | Must | 구현 완료 |
| FS-003 | 파일 데이터 소스 등록 | Must | 부분 구현 |
| FS-004 | Web·Notion 데이터 소스 연결 | Must | 미구현 |
| FS-005 | 문서 처리 및 인덱싱 | Must | 부분 구현 |
| FS-006 | 테이블 등록 및 Catalog 생성 | Must | 구현 완료 |
| FS-007 | 파이프라인 생성·조회·수정 | Must | 구현 완료 |
| FS-008 | 파이프라인 버전 관리·롤백 | Must | 구현 완료 |
| FS-009 | RAG 질의 실행 | Must | 부분 구현 |
| FS-010 | TAG 질의 실행 | Must | 구현 완료 |
| FS-011 | CAG 질의 및 캐시 관리 | Must | 부분 구현 |
| FS-012 | Playground 일반 응답 | Must | 구현 완료 |
| FS-013 | Playground 스트리밍 응답 | Must | 구현 완료 |
| FS-014 | 파이프라인 평가 | Should | 부분 구현 |
| FS-015 | 챗봇 배포 및 공개 질의 | Must | 부분 구현 |
| FS-016 | 실행 추적 및 사용량 수집 | Must | 부분 구현 |
| FS-017 | 운영 모니터링 | Should | 미구현 |
| FS-018 | 인증·RBAC·테넌트 격리 | Must | 미구현 |
| FS-019 | 감사 로그 | Must | 미구현 |
| FS-020 | 비동기 동기화 및 재시도 | Must | 미구현 |

## 5. 상세 기능 명세

### FS-001 Provider 연결 관리

사용자는 OpenAI 또는 Anthropic API 키를 등록, 교체, 조회 및 삭제할 수 있다.

| 항목 | 명세 |
|---|---|
| 사용자 | Workspace Admin |
| 선행 조건 | 인증 및 Admin 권한 보유 |
| 입력 | Provider, API 키, 연결 검증 여부 |
| 출력 | Provider, 연결 상태, 마스킹된 키, 모델 목록, 마지막 검증 시각 |
| 저장 규칙 | 키 원문 대신 암호화된 ciphertext만 저장 |
| 노출 규칙 | 응답·로그·trace에 원문 키를 반환하지 않음 |
| 교체 규칙 | 동일 Provider에 다시 등록하면 기존 암호문과 마스킹 정보를 갱신 |
| 지원 Provider | `openai`, `anthropic` |

API:

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/v1/providers` | 연결 목록 조회 |
| PUT | `/api/v1/providers/{provider}` | 키 등록 또는 교체 |
| DELETE | `/api/v1/providers/{provider}` | 연결 삭제 |

예외:

- 지원하지 않는 Provider는 `422 validation_error`를 반환한다.
- Provider가 키를 거부하거나 모델 API 호출에 실패하면 `502 provider_error`를 반환한다.
- 존재하지 않는 연결 조회·삭제는 `404 not_found`를 반환한다.

인수 조건:

- 등록 응답과 목록 응답에 API 키 원문이 포함되지 않는다.
- 저장된 암호문은 master key 없이는 복호화할 수 없다.
- 운영 환경에서는 Admin 이외 사용자의 등록·교체·삭제 요청을 거부한다.

현재 차이: 암호화 및 마스킹은 구현됐지만 인증, RBAC, 감사 로그, 키 버전 rollback window는 미구현이다.

### FS-002 Provider 모델 탐색

연결된 API 키 권한으로 사용 가능한 모델 목록을 Provider API에서 조회한다.

| Method | Path | 설명 |
|---|---|---|
| POST | `/api/v1/providers/{provider}/refresh-models` | 모델 목록 갱신 |

처리 규칙:

- OpenAI는 모델 API 결과 중 GPT 및 o-series 모델을 대상으로 한다.
- Anthropic은 모델 API의 모델 ID를 정규화하여 저장한다.
- 모델 목록이 존재하면 파이프라인 저장 시 선택 모델이 목록에 포함되는지 검증한다.
- 검증을 생략한 개발용 연결은 빈 모델 목록을 허용한다.

인수 조건:

- 잘못된 키로 모델 갱신 시 안전한 Provider 오류를 반환한다.
- 사용 불가능한 모델은 파이프라인에 저장할 수 없다.

### FS-003 파일 데이터 소스 등록

사용자는 파일을 업로드하여 검색 또는 테이블 질의용 데이터 소스로 등록한다.

| 항목 | 명세 |
|---|---|
| 지원 형식 | TXT, Markdown, JSON, HTML, PDF, CSV, XLSX, XLSM |
| 최대 크기 | 기본 20 MiB, 설정으로 변경 가능 |
| 파일명 처리 | 경로를 제거한 안전한 basename만 사용 |
| 원본 저장 | 서버 데이터 디렉터리의 uploads 영역 |
| 결과 상태 | `ready` 또는 실패 상태 |

API:

| Method | Path | 설명 |
|---|---|---|
| POST | `/api/v1/sources/upload` | 파일 업로드 및 즉시 처리 |
| GET | `/api/v1/sources` | 소스 목록 조회 |
| DELETE | `/api/v1/sources/{source_id}` | 원본·인덱스 삭제 |

예외:

- 빈 파일, 초과 크기, 지원하지 않는 확장자는 `422`를 반환한다.
- 파싱 가능한 텍스트가 없거나 JSON 형식이 잘못된 경우 `422`를 반환한다.
- 없는 소스 삭제는 `404`를 반환한다.

인수 조건:

- 성공 응답에서 소스 ID, 이름, 종류, 상태, 크기, chunk 수를 확인할 수 있다.
- 소스 삭제 후 해당 소스 문서가 검색 인덱스에서 제거된다.

현재 차이: 처리가 API 요청 안에서 동기 실행되며 MinIO, 작업 큐, 재시도 및 실패 단계 기록은 미구현이다.

### FS-004 Web·Notion 데이터 소스 연결

사용자는 URL 또는 Notion 연결 정보를 등록하고 동기화할 수 있어야 한다.

필수 입력:

- Web: URL, 수집 범위, 동기화 주기
- Notion: 암호화된 연결 자격증명, page/database ID, 동기화 주기

처리 규칙:

- 외부 콘텐츠를 로드하여 정규화한 뒤 FS-005 문서 처리 흐름으로 전달한다.
- 마지막 동기화 시각, 다음 동기화 시각, 처리 상태 및 오류를 기록한다.
- 변경된 콘텐츠는 content hash로 식별하고 필요한 문서만 다시 임베딩한다.

현재 상태: 미구현.

### FS-005 문서 처리 및 인덱싱

비정형 문서를 파싱, 청킹, 임베딩하여 검색 인덱스에 저장한다.

처리 흐름:

1. 원문 파싱 및 텍스트 정규화
2. 문단·문장 경계를 고려한 재귀 청킹
3. source ID, source name, chunk index, 위치 메타데이터 부착
4. 임베딩 생성
5. Vector Store 저장

기본 설정:

| 설정 | 기본값 |
|---|---:|
| chunk size | 900 characters |
| chunk overlap | 120 characters |
| local embedding dimension | 384 |

인수 조건:

- 인덱스 문서마다 원본을 식별할 수 있는 citation 메타데이터가 존재한다.
- 서버 재시작 시 저장된 소스를 기반으로 인덱스를 재구성한다.
- 삭제된 소스는 검색 결과에 포함되지 않는다.

현재 차이: 로컬 hash embedding과 메모리 Vector Store를 사용한다. 운영 목표인 PostgreSQL+pgvector, content hash, tenant namespace, 증분 재색인은 미구현이다.

### FS-006 테이블 등록 및 Catalog 생성

CSV·Excel 파일을 DuckDB 테이블로 등록하고 TAG용 Catalog를 생성한다.

처리 규칙:

- 시스템이 안전한 테이블명을 생성한다.
- CSV는 타입을 자동 추론한다.
- Excel은 첫 번째 sheet와 첫 행을 헤더로 사용한다.
- 중복 헤더는 고유 이름으로 정규화한다.
- Catalog에는 테이블명, 컬럼·타입, 최대 3개의 샘플 행을 포함한다.

인수 조건:

- 등록 결과에서 생성된 table name을 확인할 수 있다.
- Catalog를 RAG 검색과 TAG SQL 생성 문맥에서 사용할 수 있다.

### FS-007 파이프라인 생성·조회·수정

사용자는 전략, 모델, prompt 및 검색 설정으로 챗봇 Draft를 구성한다.

API:

| Method | Path | 설명 |
|---|---|---|
| POST | `/api/v1/pipelines` | 파이프라인 생성 |
| GET | `/api/v1/pipelines` | 목록 조회 |
| GET | `/api/v1/pipelines/{pipeline_id}` | 상세 조회 |
| PATCH | `/api/v1/pipelines/{pipeline_id}` | Draft 설정 수정 |

설정 항목:

| 필드 | 규칙 |
|---|---|
| name | 1~120자 |
| strategy | `rag`, `tag`, `cag` |
| provider | `openai`, `anthropic` |
| model | 1~120자, 연결된 모델 Catalog와 일치 |
| system_prompt | 1~10,000자 |
| top_k | 1~20 |
| similarity_threshold | 0~1 |

인수 조건:

- 연결되지 않은 Provider로 파이프라인을 생성할 수 없다.
- 모델 Catalog가 존재하면 목록 밖 모델을 저장할 수 없다.
- Draft 수정은 기존에 저장된 Pipeline Version을 변경하지 않는다.

### FS-008 파이프라인 버전 관리·롤백

파이프라인 설정을 불변 버전으로 저장하고 과거 설정으로 롤백한다.

| Method | Path | 설명 |
|---|---|---|
| POST | `/api/v1/pipelines/{id}/versions` | 현재 Draft를 새 버전으로 저장 |
| GET | `/api/v1/pipelines/{id}/versions` | 버전 목록 조회 |
| POST | `/api/v1/pipelines/{id}/rollback/{version}` | 선택 버전 설정으로 롤백 |

버전 스냅샷:

- 이름, 전략, Provider, 모델
- system prompt
- top-k, similarity threshold

처리 규칙:

- 파이프라인 생성 시 Version 1을 자동 생성한다.
- 버전 번호는 파이프라인별로 단조 증가한다.
- 저장된 버전 config는 수정하지 않는다.
- 롤백은 대상 config를 Draft에 복원하고 새로운 head version을 생성한다.

인수 조건:

- 롤백 이후 생성한 배포가 롤백된 설정의 새로운 head version을 참조한다.
- 기존 배포 결과는 Draft 수정이나 롤백에 의해 바뀌지 않는다.

### FS-009 RAG 질의 실행

질문과 의미적으로 관련된 문서를 검색하여 LLM 문맥으로 제공한다.

처리 규칙:

1. 질문을 임베딩한다.
2. `top_k` 후보를 검색한다.
3. `similarity_threshold` 미만 결과를 제거한다.
4. 검색 문서와 출처를 prompt 문맥에 포함한다.
5. 선택 Provider 모델로 답변을 생성한다.
6. 답변, citation, trace, token usage를 공통 형식으로 반환한다.

안전 규칙:

- 검색 문맥을 신뢰할 수 없는 데이터로 취급하고 내부 지시로 실행하지 않는다.
- 충분한 문맥이 없으면 모른다고 답하도록 system prompt에 명시한다.

현재 차이: 2-step RAG는 구현됐지만 hybrid search, reranker, pgvector, tenant filter 및 검색 품질 평가셋은 미구현이다.

### FS-010 TAG 질의 실행

자연어 질문을 읽기 전용 DuckDB SQL로 변환하여 테이블 결과를 기반으로 답변한다.

처리 규칙:

1. 등록 테이블 Catalog를 모델에 제공한다.
2. 모델은 정확히 하나의 DuckDB `SELECT` 문을 생성한다.
3. SQL AST를 파싱하고 쓰기·DDL 명령을 거부한다.
4. 등록된 테이블 allowlist 밖의 접근을 거부한다.
5. 외부 파일·DB scan 함수를 거부한다.
6. 최종 결과를 기본 100행으로 제한한다.
7. SQL 결과를 문맥으로 제공하여 최종 답변을 생성한다.

금지 동작:

- INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, MERGE
- ATTACH, INSTALL, LOAD 및 임의 Command
- `read_*`, `scan_*`, sqlite·postgres·mysql 외부 scan 함수
- 다중 SQL 문장

인수 조건:

- 허용 테이블의 단일 SELECT만 실행된다.
- 실행 trace에 SQL과 반환 행 수가 기록된다.
- 응답 citation에 사용 테이블과 원본 파일이 표시된다.

### FS-011 CAG 질의 및 캐시 관리

동일 파이프라인 버전과 질문의 답변을 TTL cache에서 재사용한다.

자동 질의 처리:

- cache key는 pipeline ID, version, 정규화 질문으로 구성한다.
- hit이면 LLM을 호출하지 않고 저장된 답변을 반환한다.
- miss이면 제한된 RAG를 실행하고 생성 답변을 cache에 저장한다.
- 기본 TTL은 300초다.

관리 API:

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/v1/cag/cache` | 유효 cache 목록 조회 |
| POST | `/api/v1/cag/cache` | cache 수동 생성 |
| DELETE | `/api/v1/cag/cache/{key}` | cache 삭제 |

현재 차이: 프로세스 메모리 cache를 사용하며 재시작 시 소실된다. 운영 환경의 Redis, tenant prefix, cache version, 갱신 작업 및 Admin 권한은 미구현이다.

### FS-012 Playground 일반 응답

| Method | Path | 설명 |
|---|---|---|
| POST | `/api/v1/chat` | 완성된 JSON 응답 반환 |

입력:

- `pipeline_id`: 실행할 Draft 파이프라인
- `message`: 사용자 질문
- `strategy`: 선택값. 없으면 파이프라인 기본 전략 사용

출력:

- answer, strategy, provider, model
- citations
- 단계별 trace
- token usage
- cached 여부

### FS-013 Playground 스트리밍 응답

| Method | Path | 설명 |
|---|---|---|
| POST | `/api/v1/chat/stream` | SSE 응답 스트림 반환 |

SSE 이벤트:

| 이벤트 | 데이터 |
|---|---|
| `trace` | 단계, 상태, 지연시간, 메타데이터 |
| `token` | 생성된 텍스트 조각 |
| `citation` | 원본 ID, 이름, 위치, 검색 점수 |
| `done` | 최종 공통 응답 |

인수 조건:

- 응답 media type은 `text/event-stream`이다.
- 프록시 buffering을 방지하는 헤더를 반환한다.
- 정상 실행은 반드시 `done` 이벤트로 종료된다.

### FS-014 파이프라인 평가

| Method | Path | 설명 |
|---|---|---|
| POST | `/api/v1/evaluations/run` | 여러 질문으로 파이프라인 평가 실행 |

현재 입력:

- pipeline ID
- 테스트 질문 목록

현재 출력:

- 질문별 전략, 지연시간, 예상 비용, grounding proxy
- 평균 지연시간, 총 예상 비용, 평균 grounding proxy

운영 목표 명세:

- 평가 case는 질문, 기대 답변 또는 평가 rubric, 필수 source를 포함한다.
- retrieval은 Recall@K, MRR, NDCG로 generation과 분리해 측정한다.
- generation은 승인된 evaluator 또는 human label로 정확도를 계산한다.
- Provider usage와 가격표 버전을 사용해 실제 비용을 계산한다.
- 정확도 85% 이상 등 승인 기준을 통과한 버전만 Production 배포 후보가 된다.

현재 차이: 정확도 대신 citation 존재 여부를 결정적 grounding proxy로 사용하고 비용은 고정 추정값이다. 결과 영속화와 승인 workflow도 미구현이다.

### FS-015 챗봇 배포 및 공개 질의

| Method | Path | 설명 |
|---|---|---|
| POST | `/api/v1/deployments` | Preview 또는 Production 배포 생성 |
| GET | `/api/v1/deployments` | 배포 목록 조회 |
| POST | `/api/v1/public/{slug}/chat` | 배포된 챗봇 공개 질의 |

처리 규칙:

- 배포는 pipeline ID와 생성 시점의 불변 version을 참조한다.
- 이후 Draft를 수정해도 기존 배포의 실행 설정은 변경되지 않는다.
- slug는 3~80자의 영문자, 숫자, 하이픈으로 구성한다.
- 상태는 `preview` 또는 `production`이다.
- 공개 질의는 배포가 참조하는 version snapshot으로 실행한다.

현재 차이: API 인증정보 발급, 배포 상태 변경·중지·삭제, rate limit, 공개 SSE, Production 승인 조건은 미구현이다.

### FS-016 실행 추적 및 사용량 수집

각 질의 실행은 최소 다음 정보를 수집한다.

| 정보 | 설명 |
|---|---|
| trace ID | 요청 단위 상관관계 ID |
| pipeline/version | 실행 설정 식별자 |
| strategy | RAG, TAG, CAG |
| 단계 | retriever, cache retriever, safe SQL tool, chat model |
| 지연시간 | 단계별 및 전체 실행시간 |
| usage | 입력·출력·전체 token |
| 비용 | Provider·모델 가격 기준 추정 비용 |
| 오류 | 안전하게 정규화된 오류 code와 단계 |
| citation | 사용한 원본과 위치 |

현재 차이: 응답 내부 trace와 일부 token usage는 구현됐지만 trace ID, DB 저장, OpenTelemetry, 비용 집계 및 대시보드는 미구현이다.

### FS-017 운영 모니터링

Overview 화면에서 다음 지표를 기간·Provider·모델·파이프라인별로 조회한다.

- 요청 수, 성공률, 오류율
- p50·p95 최초 token 및 전체 응답 지연시간
- 입력·출력 token과 비용
- RAG hit rate, CAG hit rate, TAG 실패율
- Provider 오류·rate limit·timeout
- 배포 상태와 최근 실행 시각

현재 상태: UI 목업만 존재하며 backend 집계 API는 미구현이다.

### FS-018 인증·RBAC·테넌트 격리

운영 환경의 모든 요청은 JWT 인증 컨텍스트에서 `user_id`, `tenant_id`, role을 확인한다.

필수 통제:

- 관리 API에 JWT 인증 적용
- Workspace Admin, Developer, Viewer 권한 검사
- PostgreSQL row 및 pgvector namespace에 tenant filter 강제
- 원본 object key와 Redis key에 tenant prefix 사용
- 공개 API key 또는 deployment token 검증과 rate limit 적용
- 다른 tenant의 ID를 전달해도 존재 여부가 노출되지 않도록 처리

현재 상태: 미구현. 인터넷에 현재 backend를 직접 공개하면 안 된다.

### FS-019 감사 로그

다음 이벤트를 비밀 원문 없이 기록한다.

- Provider 키 등록, 검증, 교체, 삭제
- 파이프라인 버전 저장 및 롤백
- Preview·Production 배포 및 중지
- 사용자·역할 변경

필수 필드: event ID, tenant ID, actor ID, action, resource type·ID, Provider, 결과, 시각, trace ID.

현재 상태: 미구현.

### FS-020 비동기 동기화 및 재시도

문서 수집, 임베딩, cache refresh 및 평가는 API 실시간 경로와 분리된 Worker에서 수행한다.

상태 흐름:

`pending → processing → ready` 또는 `pending → processing → retrying → failed`

필수 기능:

- Job ID와 진행률 조회
- 지수 backoff 및 최대 재시도 횟수
- idempotency key와 content hash 중복 방지
- 최대 재시도 초과 시 DLQ 또는 운영자 확인 목록 이동
- 실패 단계와 안전한 오류 메시지 표시

현재 상태: 미구현.

## 6. 공통 오류 계약

도메인 오류는 다음 형식으로 반환한다.

```json
{
  "error": {
    "code": "validation_error",
    "message": "요청을 처리할 수 없는 이유"
  }
}
```

| HTTP | code | 사용 조건 |
|---:|---|---|
| 404 | `not_found` | 리소스 또는 연결이 없음 |
| 409 | `configuration_error` | 실행에 필요한 설정이나 데이터가 없음 |
| 422 | `validation_error` | 입력 또는 생성 SQL이 유효하지 않음 |
| 502 | `provider_error` | 외부 Provider 호출 실패 |
| 500 | `internal_error` | 예상하지 못한 서버 오류 |

보안 규칙:

- 500 응답에는 내부 stack trace, 경로, SQL, API 키를 포함하지 않는다.
- Provider 오류는 키 원문이나 Provider 응답 본문을 그대로 반환하지 않는다.
- 운영 로그에는 trace ID를 포함하되 secret redaction을 적용한다.

## 7. 비기능 인수 기준

| 구분 | 인수 기준 |
|---|---|
| 성능 | 스트리밍 최초 응답 p95 3초 이내 |
| 트래픽 | 1,000 DAU, 동시 질의 50건 목표 |
| 가용성 | 단일 GCE MVP 기준 월 99.0% 목표, 보장 SLA 아님 |
| 보안 | TLS, JWT, RBAC, tenant 격리, secret 암호화·비노출 |
| 복구 | Pipeline Version rollback 및 Persistent Disk·DB 복구 절차 검증 |
| 관측성 | 요청, 오류, 단계별 지연시간, token, 비용 기록 |
| 데이터 | PostgreSQL+pgvector, Redis, MinIO를 Persistent Disk에 저장 |
| 배포 | Artifact Registry image를 단일 GCE Docker Compose로 실행 |
| 품질 | 서비스 테스트, API 통합 테스트, SQL 보안 테스트, tenant 격리 테스트 |

## 8. 화면별 기능 연결

| 화면 | 관련 기능 |
|---|---|
| Overview | FS-017 운영 모니터링 |
| Sources | FS-003~FS-006, FS-020 |
| Providers | FS-001, FS-002, FS-019 |
| Pipeline Studio | FS-007, FS-008 |
| Playground | FS-009~FS-014, FS-016 |
| Deployments | FS-015, FS-019 |

현재 `index.html`, `styles.css`, `app.js`는 상태 기반 정적 목업이며 backend API와 직접 연결되어 있지 않다.

## 9. 출시 단계별 범위

### 9.1 현재 PoC

- Provider 키 암호화 및 모델 탐색
- 파일 업로드와 로컬 인덱싱
- RAG·TAG·CAG 실행
- Pipeline Version과 불변 배포 실행
- SSE 스트리밍과 실행 trace
- 기본 평가 API

### 9.2 Beta MVP 필수 잔여 범위

- JWT, RBAC, tenant 격리와 감사 로그
- PostgreSQL+pgvector, Redis, MinIO Adapter 및 migration
- 비동기 Worker, Scheduler, retry 및 동기화 상태
- Web·Notion connector
- 평가셋, retrieval/generation 분리 평가 및 결과 영속화
- 배포 token, rate limit, 상태 변경·중지·삭제
- OpenTelemetry 및 운영 지표 API
- 목업을 실제 Web Console로 전환하고 backend API 연동

### 9.3 MVP 제외 범위

- 완전 자동화된 RAG·TAG·CAG 라우팅
- 엔터프라이즈 SSO
- 고객 전용 인프라와 온프레미스 배포
- 99.9% 이상 보장 SLA
- GKE 및 GCP 관리형 애플리케이션 서비스

## 10. 추적성 매트릭스

| PRD 요구사항 | 기능명세 |
|---|---|
| FR-01~02 데이터 수집·문서 처리 | FS-003~FS-006, FS-020 |
| FR-03 RAG | FS-009 |
| FR-04 TAG | FS-006, FS-010 |
| FR-05 CAG | FS-011 |
| FR-06~07 전략·실행 설정 | FS-007, FS-012~FS-013 |
| FR-08 배포 | FS-015 |
| FR-09 버전 관리 | FS-008 |
| FR-10~12 Provider | FS-001~FS-002 |
| FR-13 LangChain 파이프라인 | FS-009~FS-013 |
| FR-14 실행 추적 | FS-016~FS-017 |
| FR-16 DB 연결 | FS-010 후속 확장 |
| FR-17 자동 라우팅 | MVP 제외 |
| FR-18 품질 평가 | FS-014 |
| FR-19 운영 모니터링 | FS-017 |
| FR-20 장애 대응 | FS-002, FS-016~FS-020 후속 확장 |
