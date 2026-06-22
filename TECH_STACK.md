# LangChain 기반 RAG·TAG·CAG 플랫폼 기술 스택 v1.1

> 기준 문서: [PRD.md](./PRD.md), [ARCHITECTURE.md](./ARCHITECTURE.md)  
> 목표: LangChain 학습과 GCP 기반 MVP 배포

## 1. 핵심 결정

| 구분 | 결정 |
|---|---|
| Frontend | TypeScript + Next.js App Router + React |
| Backend | Python 3.12+ + FastAPI |
| LLM Framework | LangChain Python |
| Workflow | 단순 Runnable 우선, LangGraph는 후속 학습 |
| Database | PostgreSQL + pgvector Docker container |
| TAG Engine | 격리된 DuckDB Worker |
| CAG / Cache | Redis Docker container |
| Runtime | GCE + Docker Engine + Docker Compose |
| Async | Celery + Redis |
| Secret | App-level encryption + GCE root-only master key file |
| IaC | Terraform |
| CI/CD | GitHub Actions + Artifact Registry + GCE deploy script |
| Observability | LangChain callback + OpenTelemetry + Prometheus·Grafana·Loki |

## 2. LangChain 적용 범위

### 필수 패키지

```text
langchain
langchain-core
langchain-openai
langchain-anthropic
langchain-postgres
langchain-text-splitters
```

Document Loader가 필요할 때만 `langchain-community` 또는 전용 integration package를 추가한다. 패키지는 `uv.lock`으로 고정하고 월 단위로 의존성 업데이트 PR을 만든다.

### 전략별 구현

| 전략 | LangChain 구성 | 학습 포인트 |
|---|---|---|
| RAG | Document Loader → Text Splitter → Embedding → PGVector → Retriever → Prompt → ChatModel | 2-step RAG, metadata, citation, retrieval 품질 |
| TAG | Schema Retriever → SQL 생성 Runnable → Safe SQL Tool → DuckDB → Prompt → ChatModel | Tool 계약, 구조화 출력, SQL 검증 |
| CAG | Cache Key Runnable → Redis Retriever → miss 시 RAG fallback | custom Runnable, fallback, TTL, 비용·지연시간 비교 |
| Provider | `ChatOpenAI`, `ChatAnthropic` 또는 `init_chat_model` | 동일 인터페이스, streaming, usage metadata |
| Trace | custom callback handler → OpenTelemetry span | Chain·Retriever·Tool·LLM 단계 추적 |

### 프레임워크 경계

```text
HTTP API
  → Application Use Case
    → LangChain Orchestrator Adapter
      → Domain Ports
        → PostgreSQL / Redis / DuckDB / Provider
```

- API response와 DB model에 LangChain 타입을 직접 노출하지 않는다.
- `Document`, `AIMessage`, `RunnableConfig`는 LangChain Adapter 내부에서 도메인 DTO로 변환한다.
- TAG의 SQL allowlist, AST 검증, row limit과 timeout은 LangChain Tool 외부의 보안 계층에서도 강제한다.
- 첫 구현은 2-step RAG로 고정하고 Agentic RAG는 별도 실험으로 비교한다.
- LangGraph는 checkpoint, durable execution, human-in-the-loop가 필요할 때 도입한다.

## 3. 애플리케이션 기술

### Frontend

| 목적 | 기술 |
|---|---|
| Framework | Next.js App Router, React, TypeScript |
| 스타일 | CSS Modules + CSS Variables |
| 서버 상태 | TanStack Query |
| 폼·검증 | React Hook Form + Zod |
| 실시간 응답 | Server-Sent Events |
| 차트 | Apache ECharts |
| 단위 테스트 | Vitest + React Testing Library |
| E2E | Playwright |

기존 [index.html](./index.html), [styles.css](./styles.css), [app.js](./app.js)는 UX 기준 목업으로 유지하고 실제 구현 시 Next.js 컴포넌트로 분리한다.

### Backend

| 목적 | 기술 |
|---|---|
| API | FastAPI, Uvicorn |
| Schema | Pydantic, pydantic-settings |
| ORM / Migration | SQLAlchemy 2, Alembic, asyncpg |
| LLM | LangChain + OpenAI·Anthropic integrations |
| Table Query | DuckDB |
| Cache | redis-py |
| 암호화 | cryptography 기반 envelope format, root-only master key mount |
| Resilience | httpx timeout, tenacity, circuit breaker Adapter |
| Test | pytest, pytest-asyncio, testcontainers |
| Quality | Ruff, mypy |

## 4. GCE 배포 구성

GCP에서 직접 사용하는 제품은 **Artifact Registry와 Compute Engine**으로 제한한다. 방화벽, IAM, Persistent Disk와 snapshot은 GCE 운영에 필요한 기반 기능으로만 사용한다.

| 애플리케이션 역할 | 실행 위치 | 배포 단위 |
|---|---|---|
| Reverse Proxy | GCE Docker Compose | Caddy 또는 Nginx container |
| Web Console | GCE Docker Compose | Next.js container |
| Control Plane API | GCE Docker Compose | FastAPI container |
| Query Runtime | GCE Docker Compose | LangChain + SSE container |
| Ingestion·Evaluation | GCE Docker Compose | Celery worker·beat container |
| Metadata·Vector | GCE Docker Compose | PostgreSQL+pgvector container |
| CAG·Queue | GCE Docker Compose | Redis container |
| 원본 파일 | GCE Docker Compose | MinIO container |
| Provider API 키 | PostgreSQL ciphertext | Application encryption service |
| Master key | GCE host filesystem | `/etc/foundry/secrets/master.key`, root 0400 |
| 운영 데이터 | GCE Docker Compose | OTel Collector, Prometheus, Grafana, Loki |
| Container Image | Artifact Registry | digest 기반 Docker images |
| 영속 데이터 | GCE Persistent Disk | Docker named volume mount |
| 백업 | GCE snapshot schedule + cron | disk snapshot, `pg_dump`, 복구 테스트 |
| 인증 | FastAPI JWT + PostgreSQL RBAC | Workspace roles |

GCE zone과 machine type은 Terraform 변수로 관리한다. 초기에는 단일 VM을 사용하고 PostgreSQL·Redis·MinIO 포트는 외부에 공개하지 않는다.

## 5. 저장소 구조

```text
rag_project/
├── apps/
│   ├── web/                    # Next.js
│   ├── control-api/            # FastAPI Control Plane
│   ├── query-runtime/          # LangChain RAG·TAG·CAG
│   └── worker/                 # ingestion / evaluation
├── packages/
│   ├── domain/                 # LangChain 비종속 도메인 모델
│   ├── langchain-adapters/     # chains, retrievers, tools, callbacks
│   ├── provider-adapters/      # OpenAI / Anthropic
│   └── observability/          # OpenTelemetry
├── infrastructure/
│   ├── terraform/
│   │   ├── modules/
│   │   └── environments/
│   │       ├── dev/
│   │       └── prod/
│   └── docker/
├── tests/
│   ├── evaluation/             # RAG 정확도 테스트셋
│   ├── integration/
│   └── load/
├── docs/
│   ├── adr/
│   └── learning/               # LangChain 실험 기록
├── PRD.md
├── ARCHITECTURE.md
└── TECH_STACK.md
```

## 6. 단계별 구현 순서

### Phase 1 — LangChain 로컬 학습

1. `ChatOpenAI`, `ChatAnthropic` 호출과 streaming 비교
2. 로컬 PostgreSQL+pgvector로 2-step RAG 구현
3. DuckDB Safe SQL Tool로 TAG 구현
4. Redis 기반 CAG와 RAG fallback 구현
5. callback으로 단계별 trace와 usage 수집

### Phase 2 — API와 목업 연결

1. FastAPI의 `/chat`, `/sources`, `/providers`, `/pipelines` 구현
2. SSE 공통 이벤트 계약 정의
3. Next.js로 현재 목업 화면 이전
4. Pipeline Version과 평가 테스트 구현

### Phase 3 — Artifact Registry + GCE Staging

1. Terraform으로 Artifact Registry, GCE, Persistent Disk, firewall과 Service Account 생성
2. GitHub Actions에서 container image를 build하고 Artifact Registry에 push
3. GCE Service Account에 Artifact Registry Reader만 부여하고 digest로 image pull
4. GCE에 Docker Engine·Compose를 설치하고 Caddy/Nginx TLS 구성
5. PostgreSQL, Redis, MinIO, 애플리케이션, 관측성 container 실행
6. Persistent Disk snapshot과 `pg_dump` 복구 테스트
7. 전체 퍼널·보안·부하 테스트

### Phase 4 — 후속 학습

1. Agentic RAG와 2-step RAG 정확도·비용·지연시간 비교
2. LangGraph 기반 자동 RAG·TAG·CAG 라우팅 실험
3. checkpoint와 human-in-the-loop 적용
4. 필요할 때만 다중 GCE, 관리형 DB, 전용 Vector DB 또는 GKE 검토

## 7. MVP에서 사용하지 않을 기술

| 제외 기술 | 이유 |
|---|---|
| GKE / Kubernetes | 현재 트래픽에 비해 운영 복잡도가 큼 |
| Cloud Run·Cloud SQL 등 관리형 GCP 서비스 | 사용 범위를 Artifact Registry와 GCE로 제한 |
| Kafka | Celery+Redis로 초기 비동기 작업 요구사항 처리 가능 |
| 전용 Vector DB | PostgreSQL+pgvector로 학습과 초기 규모 처리 가능 |
| 초기 LangGraph 전면 도입 | LangChain 핵심 컴포넌트 학습을 방해하고 디버깅 범위가 커짐 |
| LangChain 내부 타입의 전 계층 사용 | 프레임워크 결합과 향후 교체 비용 증가 |

## 8. 공식 참고 문서

- [LangChain provider integrations](https://docs.langchain.com/oss/python/integrations/providers/overview)
- [LangChain RAG](https://docs.langchain.com/oss/python/langchain/rag)
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph)
- [Create and start a Compute Engine instance](https://cloud.google.com/compute/docs/instances/create-start-instance)
- [Artifact Registry Docker authentication](https://cloud.google.com/artifact-registry/docs/docker/authentication)
- [Artifact Registry push and pull](https://cloud.google.com/artifact-registry/docs/docker/pushing-and-pulling)
- [Persistent Disk snapshots](https://cloud.google.com/compute/docs/disks/snapshots)
- [Compute Engine OS Login](https://cloud.google.com/compute/docs/oslogin)
