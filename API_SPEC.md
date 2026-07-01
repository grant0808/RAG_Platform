# Foundry API Specification

Base URL: `/api/v1`

## 공통 오류

애플리케이션 오류는 다음 형식을 사용한다.

```json
{
  "error": {
    "code": "validation_error",
    "message": "Unsupported file type: .csv"
  }
}
```

## Provider

- `GET /providers`
- `PUT /providers/{provider}`
- `POST /providers/{provider}/refresh-models`
- `DELETE /providers/{provider}`

지원 provider는 `openai`, `anthropic`, `ollama`다.

## Sources

- `GET /sources`
- `POST /sources/upload`
- `GET /sources/{source_id}`
- `DELETE /sources/{source_id}`

지원 확장자는 `.txt`, `.md`, `.json`, `.html`, `.pdf`다.

## Pipelines

- `GET /pipelines`
- `POST /pipelines`
- `GET /pipelines/{pipeline_id}`
- `PATCH /pipelines/{pipeline_id}`
- `DELETE /pipelines/{pipeline_id}`
- `POST /pipelines/{pipeline_id}/versions`
- `GET /pipelines/{pipeline_id}/versions`
- `POST /pipelines/{pipeline_id}/rollback/{version}`

`strategy`는 `rag`만 허용한다.

## Chat

- `POST /chat`
- `POST /chat/stream`

`/chat/stream`은 `trace`, `token`, `citation`, `done`, `error` SSE event를 반환한다.

## Chat Sessions

- `POST /chat/sessions`
- `GET /chat/sessions`
- `PATCH /chat/sessions/{session_id}`
- `DELETE /chat/sessions/{session_id}`
- `GET /chat/sessions/{session_id}/messages`

## Evaluation

- `POST /evaluations/run`

## Deployments

- `GET /deployments`
- `POST /deployments`
- `PATCH /deployments/{deployment_id}`
- `POST /deployments/{deployment_id}/run`
- `POST /deployments/{deployment_id}/stop`
- `DELETE /deployments/{deployment_id}`
- `POST /public/{slug}/chat`
