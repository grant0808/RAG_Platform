# Foundry Backend PoC API 명세서 v1.0

> 기준 코드: `backend/src/foundry/api/v1`, `backend/src/foundry/schemas`  
> 관련 문서: [PRD](./PRD.md) · [기능 명세](./FUNCTIONAL_SPEC.md) · [ERD](./ERD.md)  
> 인증: 없음 — 개발용 PoC이므로 인터넷에 직접 노출하지 않는다.

## 1. 기본 정보

| 항목 | 값 |
|---|---|
| 기본 URL | `http://localhost:8000` |
| API Prefix | `/api/v1` |
| 요청·응답 형식 | `application/json` |
| 파일 업로드 | `multipart/form-data` |
| 스트리밍 | `text/event-stream` |
| OpenAPI UI | `/docs` |
| OpenAPI JSON | `/openapi.json` |
| 인증 헤더 | 사용하지 않음 |

날짜와 시간은 ISO 8601 UTC 문자열로 반환한다. ID는 UUID 문자열이며 페이지네이션은 현재 지원하지 않는다.

## 2. 엔드포인트 요약

| 영역 | Method | Path | 성공 코드 | 설명 |
|---|---|---|---:|---|
| System | GET | `/health` | 200 | 서버 상태 확인 |
| Provider | GET | `/providers` | 200 | 연결된 Provider 목록 |
| Provider | PUT | `/providers/{provider}` | 200 | API 키 등록 또는 교체 |
| Provider | POST | `/providers/{provider}/refresh-models` | 200 | 모델 목록 갱신 |
| Provider | DELETE | `/providers/{provider}` | 204 | Provider 연결 삭제 |
| Source | POST | `/sources/upload` | 201 | 지식 소스 업로드·인덱싱 |
| Source | GET | `/sources` | 200 | 지식 소스 목록 |
| Source | DELETE | `/sources/{source_id}` | 204 | 소스와 인덱스 삭제 |
| Pipeline | POST | `/pipelines` | 201 | Pipeline 생성 및 v1 저장 |
| Pipeline | GET | `/pipelines` | 200 | Pipeline 목록 |
| Pipeline | GET | `/pipelines/{pipeline_id}` | 200 | Pipeline 상세 |
| Pipeline | PATCH | `/pipelines/{pipeline_id}` | 200 | Draft 설정 수정 |
| Pipeline | DELETE | `/pipelines/{pipeline_id}` | 204 | Pipeline과 관련 버전·배포 삭제 |
| Pipeline | POST | `/pipelines/{pipeline_id}/versions` | 201 | 새 불변 버전 저장 |
| Pipeline | GET | `/pipelines/{pipeline_id}/versions` | 200 | 버전 목록 |
| Pipeline | POST | `/pipelines/{pipeline_id}/rollback/{version_number}` | 200 | 설정 롤백 및 새 버전 생성 |
| Chat Session | POST | `/chat/sessions` | 201 | 대화 session 생성 |
| Chat Session | GET | `/chat/sessions` | 200 | 대화 session 목록 |
| Chat Session | GET | `/chat/sessions/{session_id}/messages` | 200 | session 메시지 목록 |
| Chat Session | PATCH | `/chat/sessions/{session_id}` | 200 | session 이름 변경 |
| Chat Session | DELETE | `/chat/sessions/{session_id}` | 204 | 대화 session 삭제 |
| Chat | POST | `/chat` | 200 | Pipeline 채팅 실행 |
| Chat | POST | `/chat/stream` | 200 | SSE 채팅 실행 |
| Deployment | POST | `/deployments` | 201 | 현재 Pipeline 버전 배포 |
| Deployment | GET | `/deployments` | 200 | 배포 목록 |
| Deployment | PATCH | `/deployments/{deployment_id}` | 200 | 배포 환경 또는 실행 상태 변경 |
| Deployment | POST | `/deployments/{deployment_id}/run` | 200 | 배포 실행 |
| Deployment | POST | `/deployments/{deployment_id}/stop` | 200 | 배포 중지 |
| Deployment | DELETE | `/deployments/{deployment_id}` | 204 | 배포 삭제 |
| Public | POST | `/public/{slug}/chat` | 200 | 배포 버전으로 공개 채팅 |
| CAG | GET | `/cag/cache` | 200 | 유효한 캐시 목록 |
| CAG | POST | `/cag/cache` | 201 | 캐시 항목 수동 등록 |
| CAG | DELETE | `/cag/cache/{key}` | 204 | 캐시 항목 삭제 |
| Evaluation | POST | `/evaluations/run` | 200 | Pipeline 평가 실행 |

아래 상세 경로는 모두 `/api/v1` 뒤에 결합한다.

## 3. 공통 오류 계약

애플리케이션 오류는 다음 형식을 사용한다.

```json
{
  "error": {
    "code": "not_found",
    "message": "Pipeline not found: 59c1..."
  }
}
```

| HTTP | code | 의미 |
|---:|---|---|
| 404 | `not_found` | 요청한 Provider, Source, Pipeline, Version 또는 Deployment가 없음 |
| 409 | `configuration_error` | 실행에 필요한 소스나 설정이 없음 |
| 422 | `validation_error` | 지원하지 않는 파일·Provider·모델·전략 또는 파일 제한 위반 |
| 502 | `provider_error` | Provider 인증 거부, 모델 조회 실패 또는 통신 장애 |
| 500 | `internal_error` | 처리되지 않은 서버 오류 |

Pydantic/FastAPI 요청 검증 실패는 애플리케이션 오류와 달리 FastAPI 기본 `detail` 배열 형식의 HTTP 422를 반환한다. `DELETE /cag/cache/{key}`의 404도 `{ "detail": "Cache entry not found" }` 형식이다.

## 4. 데이터 모델

### ProviderConnectRequest

```json
{
  "api_key": "sk-example-key 또는 http://localhost:11434",
  "validate_connection": true
}
```

| 필드 | 타입 | 필수 | 규칙 |
|---|---|---:|---|
| `api_key` | string | X | OpenAI/Anthropic은 API key 필수. Ollama는 local base URL이며 빈 값이면 `FOUNDRY_OLLAMA_BASE_URL` 사용. 응답과 로그에 원문 미반환 |
| `validate_connection` | boolean | X | 기본 `true`; `false`이면 모델 조회 생략 |

### ProviderResponse

| 필드 | 타입 | 설명 |
|---|---|---|
| `provider` | string | `openai`, `anthropic`, 또는 `ollama` |
| `masked_key` | string | 마스킹된 키 식별자 |
| `status` | string | 현재 `connected` |
| `models` | string[] | Provider에서 조회한 모델 ID |
| `last_validated_at` | datetime | 마지막 등록·검증 시각 |

### SourceResponse

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | string | Source UUID |
| `name` | string | 원본 파일명 |
| `kind` | string | `document`, `pdf`, `table` |
| `status` | string | 정상 인덱싱 완료 시 `ready`; 유효하지만 검색 가능한 텍스트가 없는 PDF는 `no_text` |
| `table_name` | string \| null | TAG 테이블 내부 이름 |
| `chunk_count` | integer | 생성된 문서 chunk 수 |
| `size_bytes` | integer | 업로드 크기 |
| `created_at` | datetime | 생성 시각 |

### PipelineCreate

```json
{
  "name": "고객지원 챗봇",
  "strategy": "rag",
  "provider": "openai",
  "model": "gpt-5.4-mini",
  "system_prompt": "근거가 있는 답변만 제공하고 출처를 표시하세요.",
  "top_k": 5,
  "similarity_threshold": 0.2
}
```

| 필드 | 타입 | 필수 | 기본값·규칙 |
|---|---|---:|---|
| `name` | string | O | 1~120자 |
| `strategy` | enum | X | `rag`; `rag`, `tag`, `cag` |
| `provider` | enum | X | `openai`; `openai`, `anthropic`, `ollama` |
| `model` | string | X | `gpt-5.4-mini`, 1~120자 |
| `system_prompt` | string | X | 1~10,000자 |
| `top_k` | integer | X | `5`, 1~20 |
| `similarity_threshold` | number | X | `0.2`, 0~1 |

`PipelineUpdate`는 위 필드가 모두 선택 사항인 부분 수정 모델이다. `null`을 명시하면 DB의 NOT NULL 제약과 충돌할 수 있으므로 변경할 필드와 값만 전송해야 한다.

### PipelineResponse

`PipelineCreate` 필드에 다음 필드가 추가된다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | string | Pipeline UUID |
| `current_version` | integer | 현재 head 버전 |
| `created_at` | datetime | 생성 시각 |
| `updated_at` | datetime | 수정 시각 |

### PipelineVersionResponse

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | string | 버전 레코드 UUID |
| `pipeline_id` | string | Pipeline UUID |
| `version` | integer | Pipeline 내부 버전 번호 |
| `config` | object | 저장 시점의 Pipeline 설정 스냅샷 |
| `created_at` | datetime | 저장 시각 |

### ChatRequest

```json
{
  "pipeline_id": "59c1...",
  "message": "환불 정책을 요약해줘.",
  "strategy": "rag",
  "session_id": "c9b2..."
}
```

| 필드 | 타입 | 필수 | 규칙 |
|---|---|---:|---|
| `pipeline_id` | string | O | 실행할 Pipeline ID |
| `message` | string | O | 1~20,000자 |
| `strategy` | enum \| null | X | 미지정 시 Pipeline 전략; `rag`, `tag`, `cag` |
| `session_id` | string \| null | X | 기존 대화 session ID; 미지정 시 새 session 자동 생성 |

`message`가 정확히 `/status`이면 모델을 호출하지 않고 해당 session의 token 사용량 상태를 반환한다. `FOUNDRY_OPENAI_ADMIN_API_KEY`, `FOUNDRY_ANTHROPIC_ADMIN_API_KEY`가 설정되어 있으면 Provider Admin API의 실제 사용량·비용도 함께 조회한다.

### ChatResponse

```json
{
  "session_id": "c9b2...",
  "answer": "환불은 구매일로부터 7일 이내 가능합니다.",
  "strategy": "rag",
  "provider": "openai",
  "model": "gpt-5.4-mini",
  "citations": [
    {
      "source_id": "1e83...",
      "source_name": "refund-policy.pdf",
      "location": "chunk:0",
      "score": 0.87
    }
  ],
  "trace": [
    {
      "step": "retriever",
      "status": "completed",
      "duration_ms": 12.4,
      "metadata": {"documents": 1, "top_k": 5}
    }
  ],
  "usage": {"input_tokens": 320, "output_tokens": 48, "total_tokens": 368},
  "cached": false
}
```

`citation.score`와 `location`, `trace.duration_ms`는 `null`일 수 있다. `usage` 키는 Provider SDK가 반환한 사용량 구조에 따라 달라질 수 있다.

`/status` command 응답은 `strategy: "status"`, `provider: "system"`, `model: "local-command"`를 반환하며 `token_status`와 `provider_quota` 객체를 추가로 포함한다.

```json
{
  "session_id": "c9b2...",
  "answer": "Session token status\n- Budget: 100,000 tokens\n- Used total: 368 tokens ...",
  "strategy": "status",
  "provider": "system",
  "model": "local-command",
  "citations": [],
  "trace": [],
  "usage": {},
  "cached": false,
  "token_status": {
    "budget": 100000,
    "used_total": 368,
    "used_input": 320,
    "used_output": 48,
    "remaining": 99632,
    "message_count": 1
  },
  "provider_quota": {
    "period": {
      "start": "2026-06-01T00:00:00Z",
      "end": "2026-06-25T00:00:00Z",
      "bucket_width": "1d"
    },
    "openai": {
      "configured": true,
      "usage": {"available": true, "total_tokens": 1234, "tokens": {}, "requests": {}},
      "cost": {"available": true, "amount": 0.42, "currency": "USD"},
      "remaining": {
        "available": false,
        "reason": "OpenAI usage/cost endpoints return actual usage and cost, not a universal remaining quota value."
      }
    },
    "anthropic": {
      "configured": true,
      "usage": {"available": true, "total_tokens": 500, "tokens": {}, "requests": {}},
      "cost": {"available": true, "amount": 0.2, "currency": "USD"},
      "remaining": {"available": true, "remaining_usd": 99.8}
    }
  }
}
```

Provider Admin API key가 없으면 해당 provider는 `configured: false`와 설정 안내 reason을 반환한다. Admin key가 거부되거나 권한이 부족하면 `available: false`, `status_code`, `error`를 반환한다. OpenAI는 조직 usage/cost 조회를 지원하지만 범용 remaining quota 값은 제공하지 않는다. Anthropic remaining은 Claude Enterprise Spend Limits API 권한이 있을 때만 계산된다.

### ChatSessionCreate / ChatSessionResponse

```json
{
  "pipeline_id": "59c1...",
  "title": "환불 정책 문의"
}
```

| 요청 필드 | 타입 | 필수 | 규칙 |
|---|---|---:|---|
| `pipeline_id` | string | O | session을 연결할 Pipeline ID |
| `title` | string \| null | X | 1~160자; 미지정 시 첫 user 메시지에서 자동 생성 |

응답은 `id`, `pipeline_id`, `title`, `created_at`, `updated_at`을 반환한다.

### ChatSessionUpdate

```json
{
  "title": "운영 FAQ 테스트"
}
```

| 요청 필드 | 타입 | 필수 | 규칙 |
|---|---|---:|---|
| `title` | string | O | 1~160자; 앞뒤 공백과 중복 공백은 정리되어 저장 |

### ChatMessageResponse

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | string | 메시지 ID |
| `session_id` | string | 소속 session ID |
| `role` | enum | `user`, `assistant` |
| `content` | string | 메시지 본문 |
| `message_metadata` | object | assistant 응답의 strategy, citations, trace, usage 등 |
| `created_at` | datetime | 저장 시각 |

### DeploymentCreate / DeploymentResponse

```json
{
  "pipeline_id": "59c1...",
  "slug": "support-bot",
  "environment": "preview"
}
```

| 요청 필드 | 타입 | 필수 | 규칙 |
|---|---|---:|---|
| `pipeline_id` | string | O | 배포할 Pipeline ID |
| `slug` | string \| null | X | 3~80자, 영문·숫자·하이픈; 미지정 시 자동 생성 |
| `environment` | enum | X | 기본 `preview`; `preview`, `production` |

응답은 `id`, `pipeline_id`, `slug`, `version`, `environment`, `status`, `created_at`을 반환한다. `version`은 생성 시점의 Pipeline head 버전이다. `status`는 실행 상태이며 `running`, `stopped` 중 하나다.

### DeploymentUpdate

| 요청 필드 | 타입 | 필수 | 규칙 |
|---|---|---:|---|
| `environment` | enum | X | `preview`, `production` |
| `status` | enum | X | `running`, `stopped` |

### CacheCreateRequest / CacheEntryResponse

| 요청 필드 | 타입 | 필수 | 규칙 |
|---|---|---:|---|
| `key` | string | O | 최소 1자 |
| `answer` | string | O | 최소 1자 |
| `ttl_seconds` | integer | X | 기본 300, 최소 1 |

응답은 `key`, `answer`, `expires_at_timestamp`, `expires_at`, `ttl_seconds_remaining`을 반환한다. 캐시는 프로세스 메모리에만 존재한다.

### EvaluationRunRequest / EvaluationResultResponse

```json
{
  "pipeline_id": "59c1...",
  "test_queries": ["환불 정책은?", "배송 기간은?"]
}
```

빈 `test_queries`를 보내면 서버의 기본 질문 3개를 사용한다. 응답은 실행 시각, 평균 지연시간, 추정 총비용, 평균 정확도와 질의별 `query`, `strategy`, `latency_seconds`, `estimated_cost`, `accuracy_score`를 반환한다.

## 5. 엔드포인트 상세

### 5.1 System

#### `GET /health`

의존 서비스 초기화 후 API 상태를 반환한다.

```json
{
  "status": "ok",
  "service": "Foundry API",
  "version": "0.1.0",
  "auth_enabled": false
}
```

### 5.2 Provider

#### `GET /providers`

연결된 Provider를 이름 오름차순 배열로 반환한다. 연결이 없으면 `[]`이다.

#### `PUT /providers/{provider}`

- Path: `provider`는 대소문자를 정규화하며 `openai`, `anthropic`, `ollama`를 지원한다.
- 동일 Provider가 이미 있으면 API 키 또는 Ollama base URL과 모델 목록을 교체한다.
- `validate_connection=true`이면 Provider Models API를 호출한 뒤 저장한다. Ollama는 `{base_url}/api/tags`를 호출한다.
- 성공 응답에 API 키 원문과 암호문을 포함하지 않는다.

#### `POST /providers/{provider}/refresh-models`

저장된 키를 복호화해 Provider 모델 목록과 `last_validated_at`을 갱신한다.

#### `DELETE /providers/{provider}`

연결 정보를 삭제하고 본문 없이 204를 반환한다. 해당 Provider를 사용하는 기존 Pipeline은 삭제하지 않는다.

### 5.3 Source

#### `POST /sources/upload`

요청 예시:

```bash
curl -X POST http://localhost:8000/api/v1/sources/upload \
  -F 'file=@./refund-policy.pdf'
```

- form 필드명: `file`
- 지원 확장자: `.txt`, `.md`, `.json`, `.html`, `.pdf`, `.csv`, `.xlsx`, `.xlsm`
- 기본 최대 크기: 20 MiB
- 문서형 파일은 텍스트 추출·청킹·벡터 인덱싱한다.
- PDF가 유효하지만 추출 가능한 텍스트가 없으면 201로 저장하고 `status: "no_text"`, `chunk_count: 0`을 반환한다. 이 source는 RAG 검색 인덱스에는 포함하지 않는다.
- 표 파일은 DuckDB 테이블과 catalog 문서를 생성한다.
- 빈 파일, 잘못된 JSON, 깨진 PDF, PDF 외 문서의 텍스트 추출 실패는 HTTP 422다.

#### `GET /sources`

생성 시각 내림차순으로 전체 Source를 반환한다.

#### `DELETE /sources/{source_id}`

원본 파일과 메타데이터를 삭제하고 남은 Source 전체로 인메모리 지식 인덱스를 재구성한다.

### 5.4 Pipeline 및 버전

#### `POST /pipelines`

연결된 Provider와 사용 가능한 모델을 검증한 뒤 Pipeline과 버전 1을 함께 생성한다. Provider가 먼저 연결되어 있어야 한다.

#### `GET /pipelines`

생성 시각 내림차순으로 전체 Pipeline을 반환한다.

#### `GET /pipelines/{pipeline_id}`

지정한 Pipeline의 현재 Draft 설정을 반환한다.

#### `PATCH /pipelines/{pipeline_id}`

전송한 필드만 Draft에 반영한다. 자동으로 버전을 만들지 않으며 Provider·모델 조합은 다시 검증한다.

#### `DELETE /pipelines/{pipeline_id}`

Pipeline을 삭제하고 본문 없이 204를 반환한다. PoC 정책상 관련 `pipeline_versions`, `deployments`, `chat_sessions`, `chat_messages`도 함께 삭제한다. 따라서 해당 Pipeline으로 만든 공개 채팅 slug는 즉시 404가 된다. 존재하지 않는 Pipeline은 404 `not_found`를 반환한다.

#### `POST /pipelines/{pipeline_id}/versions`

현재 Draft를 새 불변 스냅샷으로 저장하고 `current_version`을 1 증가시킨다.

#### `GET /pipelines/{pipeline_id}/versions`

버전 번호 내림차순으로 스냅샷 목록을 반환한다.

#### `POST /pipelines/{pipeline_id}/rollback/{version_number}`

선택 버전의 설정을 Draft에 복원한 뒤 새로운 head 버전을 생성한다. 예를 들어 현재 v3에서 v1로 롤백하면 v1을 덮어쓰지 않고 동일 설정의 v4가 생성된다.

### 5.5 Chat

#### `POST /chat/sessions`

Pipeline에 연결된 빈 대화 session을 생성한다. 명시적으로 생성하지 않아도 `/chat` 또는 `/chat/stream` 호출 시 `session_id`가 없으면 자동 생성된다.

#### `GET /chat/sessions`

대화 session 목록을 `updated_at` 내림차순으로 반환한다. `?pipeline_id={id}`를 주면 특정 Pipeline의 session만 반환한다.

#### `GET /chat/sessions/{session_id}/messages`

대화 session에 저장된 user/assistant 메시지를 생성 순서대로 반환한다.

#### `PATCH /chat/sessions/{session_id}`

대화 session 이름을 변경한다. 변경된 이름은 session 목록과 Playground session 선택 UI에 반영된다.

#### `DELETE /chat/sessions/{session_id}`

대화 session과 그 메시지를 삭제하고 본문 없이 204를 반환한다.

#### `POST /chat`

현재 Pipeline Draft 설정으로 RAG, TAG 또는 CAG를 동기 실행한다.

- RAG: 인메모리 벡터 검색 후 출처와 함께 답변한다.
- TAG: 업로드된 표를 대상으로 읽기 전용 DuckDB `SELECT`를 생성·검증·실행한다.
- CAG: `pipeline_id:version:normalized_question` 키로 캐시를 조회하고 miss 시 RAG로 fallback한다.
- `session_id`가 있으면 이전 user/assistant 메시지를 모델 입력에 포함하고, 없으면 새 session을 만든다.
- user 메시지와 assistant 응답은 `chat_messages`에 저장된다.
- `/status`는 저장된 assistant 메시지의 `usage.total_tokens`를 합산해 session 내부 예산 대비 사용량과 잔여량을 반환한다. 예산은 `FOUNDRY_CHAT_SESSION_TOKEN_BUDGET` 설정값이다. Admin API key가 설정되어 있으면 OpenAI/Anthropic의 실제 월간 usage/cost도 조회한다. Provider가 remaining quota를 API로 노출하지 않거나 권한이 부족하면 해당 필드는 unavailable로 표시한다.

TAG에 표 Source가 없으면 409를 반환한다. Provider가 연결되지 않았거나 모델 호출에 실패해도 요청은 실패한다.

#### `POST /chat/stream`

요청 모델은 `/chat`과 동일하고 응답 Content-Type은 `text/event-stream`이다. `done` 이벤트의 payload는 `ChatResponse`와 동일하며 `session_id`를 포함한다.

| event | data | 발생 조건 |
|---|---|---|
| `trace` | `TraceEvent` | 검색·캐시·SQL 준비 단계 완료 |
| `token` | `{ "text": string }` | 모델 token 또는 CAG 캐시 답변 |
| `citation` | `Citation` | 비캐시 실행의 token 전송 완료 후 |
| `done` | `ChatResponse` | 정상 스트림 종료 시 마지막 이벤트 |

```text
event: token
data: {"text":"환불은"}

event: citation
data: {"source_id":"1e83...","source_name":"refund-policy.pdf","location":"chunk:0","score":0.87}

event: done
data: {"answer":"환불은 ...","strategy":"rag","provider":"openai","model":"gpt-5.4-mini","citations":[],"trace":[],"usage":{},"cached":false}
```

현재 스트림 시작 후 발생한 예외를 별도 SSE `error` 이벤트로 변환하지 않는다. 클라이언트는 비정상 연결 종료도 오류로 처리해야 한다.

### 5.6 Deployment 및 Public Chat

#### `POST /deployments`

Pipeline의 현재 버전을 Preview 또는 Production 배포로 고정하고 기본 실행 상태를 `running`으로 만든다. 이후 Draft가 변경되어도 배포는 생성 당시 버전 스냅샷을 사용한다.

#### `GET /deployments`

생성 시각 내림차순으로 모든 배포를 반환한다.

#### `PATCH /deployments/{deployment_id}`

배포의 `environment` 또는 `status`를 부분 변경한다. Preview/Production 전환은 배포가 가리키는 Pipeline 버전을 바꾸지 않는다.

#### `POST /deployments/{deployment_id}/run`

배포 상태를 `running`으로 변경한다.

#### `POST /deployments/{deployment_id}/stop`

배포 상태를 `stopped`로 변경한다. 중지된 배포의 public chat은 409 `configuration_error`를 반환한다.

#### `DELETE /deployments/{deployment_id}`

배포를 삭제하고 본문 없이 204를 반환한다. 삭제된 slug의 public chat은 404 `not_found`를 반환한다.

#### `POST /public/{slug}/chat`

실행 중인 배포가 가리키는 불변 Pipeline 버전으로 채팅한다. 요청 본문은 `pipeline_id`가 없는 `PublicChatRequest`다.

```json
{
  "message": "환불 정책을 알려줘.",
  "strategy": null
}
```

PoC에서는 이름과 달리 이 API뿐 아니라 전체 API가 인증 없이 공개되어 있다.

### 5.7 CAG Cache

#### `GET /cag/cache`

TTL이 남은 캐시 항목만 반환한다. 만료 항목을 응답에서 제외하지만 즉시 저장소에서 제거하지는 않는다.

#### `POST /cag/cache`

임의 key와 답변을 TTL과 함께 메모리 캐시에 저장한다. 자동 CAG hit를 만들려면 key를 `{pipeline_id}:{version}:{trimmed_lowercase_question}` 형식으로 구성해야 한다.

#### `DELETE /cag/cache/{key}`

Path converter가 `/`를 포함한 key도 받는다. 존재하면 본문 없이 204, 없으면 FastAPI 기본 형식의 404를 반환한다.

### 5.8 Evaluation

#### `POST /evaluations/run`

각 질문을 Pipeline 전략으로 순차 실행한다.

- 정답 레이블이 없으므로 citation 존재 여부를 정확도 proxy로 사용한다.
- 추정 비용은 OpenAI `$0.015`, Anthropic·Ollama `$0.025`, cache hit `$0.001`의 고정값이다.
- 개별 질문 실패는 전체 요청을 실패시키지 않고 해당 metric을 0으로 기록한다.
- 평가 결과는 DB에 저장하지 않고 응답으로만 반환한다.

이 값은 실제 모델 정확도나 청구 비용이 아니며 PoC 비교 지표로만 사용한다.

## 6. 권장 호출 순서

1. `GET /health`
2. `PUT /providers/{provider}`
3. `POST /sources/upload`
4. `POST /pipelines`
5. `POST /chat` 또는 `POST /chat/stream`
6. `PATCH /pipelines/{id}` 후 `POST /pipelines/{id}/versions`
7. 필요 시 `POST /pipelines/{id}/rollback/{version}`
8. `POST /deployments`
9. `POST /public/{slug}/chat`

## 7. PoC 제약 및 운영 전 필수 변경

- 인증, RBAC, Tenant 격리, rate limit이 없다.
- 목록 API의 페이지네이션·필터·검색이 없다.
- Source 인덱스와 CAG cache가 프로세스 메모리에 있어 재시작 시 소실된다.
- 멱등성 키와 동시 수정 제어가 없다.
- 일부 DB unique 충돌은 표준화된 409가 아닌 500이 될 수 있다.
- SSE 도중 오류 계약, request/trace ID, OpenTelemetry 저장이 없다.
- Provider API 키 관리 API를 운영에 노출하려면 관리자 권한과 감사 로그가 필요하다.
