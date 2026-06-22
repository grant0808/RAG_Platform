# LLMOps 기반 개인화 AI 챗봇 플랫폼 PRD v1.3

## 1. 문서 개요

| 항목 | 내용 |
|---|---|
| 문서 버전 | v1.3 |
| 제품 도메인 | 개인 지식관리 및 생산성 |
| 제품 유형 | 클라우드 기반 멀티테넌트 SaaS |
| 핵심 기술 | LangChain, RAG, TAG, CAG, LLMOps, GCP |
| 최우선 사용자 | AI 챗봇 개발자·AI 엔지니어 |
| 보조 사용자 | 기업 지식관리·고객지원 조직 |
| 출시 단계 | 제한된 사용자 대상 MVP 베타 |

### 용어 정의

| 용어 | 정의 |
|---|---|
| RAG | 비정형 문서를 검색해 관련 문맥을 LLM에 제공하는 방식 |
| TAG | Table Augmented Generation. 테이블 데이터를 활용해 답변을 생성하는 방식 |
| CAG | Cache-Augmented Generation. 반복 사용되는 지식을 캐시에 적재해 활용하는 방식 |
| BYOK | Bring Your Own Key. 사용자가 보유한 모델 제공사의 API 키를 연결하는 방식 |
| Provider Connection | 테넌트별로 암호화 저장된 OpenAI 또는 Anthropic API 연결 정보 |
| LangChain | 모델·프롬프트·Retriever·Tool·Runnable을 공통 인터페이스로 조합하는 애플리케이션 프레임워크 |
| 파이프라인 | 데이터 수집부터 검색·생성·평가·배포까지의 실행 구성 |

## 2. 프로젝트 목적

비정형 문서와 정형 테이블을 활용해 신뢰도 높은 개인화 AI 챗봇을 구축하고 운영하는 전 과정을 하나의 플랫폼에서 제공한다.

사용자는 데이터 특성에 따라 RAG·TAG·CAG 방식을 직접 선택할 수 있으며, 모델과 검색 설정을 조정하고 품질·속도·비용을 평가한 후 웹 또는 API 형태로 배포할 수 있어야 한다.

본 프로젝트의 기술적 목적은 LangChain의 모델 추상화, Runnable 조합, Retriever, Tool, callback과 streaming 구조를 실제 서비스 흐름에 적용하고 그 동작과 한계를 학습하는 것이다. 완성된 애플리케이션은 Artifact Registry와 단일 GCE VM을 사용해 배포한다.

### 핵심 가치

1. 연결된 데이터를 바탕으로 정확하고 출처가 명확한 답변을 제공한다.
2. RAG·TAG·CAG를 데이터와 질의 특성에 맞게 조합한다.
3. 챗봇 생성·평가·배포·모니터링을 하나의 LLMOps 환경에서 지원한다.
4. RAG·TAG·CAG를 LangChain의 표준 컴포넌트로 구현해 학습 과정과 실행 흐름을 확인할 수 있게 한다.

### 기술 학습 목표

1. `langchain-openai`와 `langchain-anthropic`을 이용해 동일한 Chain에서 모델을 교체한다.
2. Document Loader → Text Splitter → Embedding → Vector Store → Retriever로 이어지는 2-step RAG를 구현한다.
3. TAG를 안전한 SQL Tool, CAG를 Cache Retriever 또는 Runnable로 구현한다.
4. Runnable과 callback을 통해 각 단계의 입력·출력·지연시간·토큰 사용량을 추적한다.
5. 단순 Chain부터 시작하고 상태 기반 장기 실행이 필요한 시점에만 LangGraph를 도입한다.

### MVP 범위 제외

- 완전 자동화된 RAG·TAG·CAG 라우팅
- 엔터프라이즈 SSO 및 감사 로그
- 고객 전용 인프라와 온프레미스 배포
- 월 99.9% 이상의 상용 SLA
- Cloud Run·Cloud SQL·Memorystore·Pub/Sub·Secret Manager 등 GCP 관리형 애플리케이션 서비스

## 3. 사용자 및 페르소나

### 핵심 페르소나

| 항목 | 내용 |
|---|---|
| 역할 | AI 챗봇 개발자·AI 엔지니어 |
| 목표 | 다양한 데이터에 적합한 검색·생성 방식을 구성하고 안정적으로 배포 |
| 주요 문제 | 비정형 문서, 테이블, 캐시 기반 지식을 별도로 구축·운영해야 함 |
| 기술 수준 | API, 데이터베이스, LLM 및 검색 파이프라인에 대한 실무 지식 보유 |
| 성공 조건 | 하나의 플랫폼에서 데이터 연결부터 배포까지 완료 |

### 핵심 사용자 퍼널

`데이터 연결 → RAG·TAG·CAG 구성 → 챗봇 생성 → 평가 → 배포 → 모니터링`

### 핵심 사용자 스토리

- 개발자로서 PDF·웹·Notion 데이터를 연결해 검색 기반 답변을 생성하고 싶다.
- 개발자로서 CSV·Excel 데이터를 자연어로 질의하고 싶다.
- 개발자로서 반복 사용되는 지식을 캐시에 적재해 응답 속도와 비용을 개선하고 싶다.
- 개발자로서 모델·프롬프트·검색 설정을 변경하고 이전 버전으로 롤백하고 싶다.
- Workspace Admin으로서 OpenAI 또는 Anthropic API 키를 안전하게 등록·검증·교체·삭제하고 싶다.
- 개발자로서 연결된 키로 사용 가능한 모델 목록을 확인하고 파이프라인별 모델을 선택하고 싶다.
- 개발자로서 완성된 챗봇을 웹 UI 또는 REST API로 배포하고 싶다.

## 4. 기능 요구사항

### Must Have

| ID | 기능 | 주요 요구사항 | 완료 조건 |
|---|---|---|---|
| FR-01 | 데이터 수집 | PDF·웹·Notion 데이터를 등록하고 동기화 | 데이터별 수집 상태와 오류 확인 가능 |
| FR-02 | 문서 처리 | 파싱·청킹·임베딩 파이프라인 실행 | 처리 결과와 실패 단계 확인 가능 |
| FR-03 | RAG 검색 | 벡터 검색 결과를 LLM 문맥으로 제공 | 답변에 원문 출처와 참조 구간 표시 |
| FR-04 | TAG 질의 | CSV·Excel 업로드 및 자연어 질의 | 테이블 기반 결과와 사용 데이터 표시 |
| FR-05 | CAG 관리 | 캐시 생성·갱신·만료 설정 | 캐시 상태와 최종 갱신 시각 확인 가능 |
| FR-06 | 전략 선택 | RAG·TAG·CAG 처리 방식을 수동 선택 | 챗봇 또는 파이프라인별 설정 저장 |
| FR-07 | 실행 설정 | 모델·프롬프트·검색 파라미터 설정 | 설정 변경 후 테스트 실행 가능 |
| FR-08 | 배포 | 웹 채팅 UI와 REST API 제공 | 배포 상태 및 API 인증정보 확인 가능 |
| FR-09 | 버전 관리 | 파이프라인 설정을 버전별로 저장 | 특정 버전 조회·복원·롤백 가능 |
| FR-10 | Provider 연결 | Workspace Admin이 OpenAI·Anthropic API 키를 등록·검증·교체·삭제 | 키 원문을 다시 노출하지 않고 연결 상태·마지막 검증 시각·마스킹된 식별자 표시 |
| FR-11 | 모델 탐색·선택 | 연결된 Provider API의 모델 목록을 조회하고 파이프라인별 모델 선택 | 사용할 수 없는 모델 저장 방지, 모델 ID와 Provider를 Pipeline Version에 고정 |
| FR-12 | Provider 실행 | 선택 모델에 맞는 Provider Adapter로 스트리밍 요청 실행 | OpenAI와 Anthropic 응답을 공통 스트림·사용량·오류 형식으로 정규화 |
| FR-13 | LangChain 파이프라인 | RAG·TAG·CAG를 LangChain Runnable·Retriever·Tool 인터페이스로 구성 | 각 전략을 독립적으로 실행·테스트하고 동일한 입출력 계약으로 교체 가능 |
| FR-14 | Chain 실행 추적 | LangChain callback으로 단계별 실행 상태·지연시간·토큰·오류 기록 | Playground에서 데이터 조회부터 모델 응답까지 실행 단계를 확인 가능 |
| FR-15 | 학습 문서화 | 핵심 Chain별 코드 구조·선택 이유·실험 결과를 문서화 | RAG·TAG·CAG 예제와 테스트, ADR이 저장소에 포함 |

### Should Have

| ID | 기능 | 주요 요구사항 |
|---|---|---|
| FR-16 | DB 연결 | 관계형 DB 연결 및 질의 기반 SQL 생성 |
| FR-17 | 자동 라우팅 | 질문 특성에 따라 RAG·TAG·CAG 선택 |
| FR-18 | 품질 평가 | 테스트셋 기반 정확도·지연시간·비용 측정 |
| FR-19 | 운영 모니터링 | 요청 로그·사용량·오류·비용을 Provider·모델별로 확인 |
| FR-20 | 장애 대응 | Provider별 timeout·재시도·circuit breaker와 관리자가 승인한 fallback 모델 지원 |

### Could Have / Won’t Have

현재 별도 지정된 기능은 없다. 베타 검증 결과를 바탕으로 후속 범위를 결정한다.

## 5. 비기능 요구사항

| ID | 구분 | 요구사항 |
|---|---|---|
| NFR-01 | 인프라 | GCP 기반 멀티테넌트 SaaS로 제공 |
| NFR-02 | 인증 | JWT 기반 사용자 및 API 인증 |
| NFR-03 | 전송 보안 | 모든 외부 통신에 TLS 적용 |
| NFR-04 | 데이터 보안 | 저장 데이터 및 비밀정보 암호화 |
| NFR-05 | 접근 제어 | 조직과 역할을 기준으로 RBAC 적용 |
| NFR-06 | 격리 | 테넌트별 원본 데이터·임베딩·로그 격리 |
| NFR-07 | 성능 | 최초 응답 시간 p95 3초 이내 |
| NFR-08 | 트래픽 | 1,000 DAU 및 동시 요청 50건 지원 |
| NFR-09 | 가용성 | 단일 GCE VM MVP 기준 월 99.0%를 목표로 하되 보장 SLA로 제공하지 않음 |
| NFR-10 | 확장성 | 서비스 중단 없이 수평 확장 가능 |
| NFR-11 | 관측성 | 요청 추적, 오류, 지연시간 및 LLM 비용 기록 |
| NFR-12 | 복구 | 파이프라인 설정을 안정적인 이전 버전으로 롤백 |
| NFR-13 | 키 보안 | API 키는 브라우저 저장소·로그·DB 평문에 저장하지 않고 애플리케이션 계층에서 암호화한 ciphertext만 PostgreSQL에 저장 |
| NFR-14 | 키 접근 | 암호화 master key는 GCE의 root 전용 파일로 분리하고, Provider 키는 호출 시점에만 서버 메모리에서 복호화 |
| NFR-15 | 키 비노출 | 저장 후 API 키 원문을 조회·응답·로그로 반환하지 않고 마지막 4자리 등 마스킹 정보만 제공 |
| NFR-16 | Provider 격리 | Provider별 timeout·rate limit·오류가 다른 Provider와 Control Plane으로 전파되지 않도록 격리 |
| NFR-17 | 감사 | 키 등록·검증·교체·삭제 이벤트를 키 원문 없이 행위자·시각·Provider와 함께 기록 |
| NFR-18 | GCP 범위 | GCP 서비스는 Artifact Registry와 Compute Engine만 사용하며 애플리케이션은 GCE VM의 Docker Compose로 배포 |
| NFR-19 | 자체 운영 데이터 | PostgreSQL+pgvector, Redis, MinIO와 Worker를 GCE 내부 컨테이너로 운영하고 Persistent Disk에 상태 저장 |
| NFR-20 | IaC | Artifact Registry, GCE, Persistent Disk, firewall과 최소 IAM 설정을 Terraform으로 재현 가능하게 관리 |
| NFR-21 | 프레임워크 경계 | LangChain 객체가 도메인·저장소 계층으로 누출되지 않도록 Application 계층 Adapter 안에 격리 |

## 6. 성공 지표

| 지표 | 목표 | 측정 기준 |
|---|---:|---|
| 첫 정상 답변 도달 시간 | 10분 이내 | 프로젝트 생성부터 출처 또는 데이터 근거가 포함된 첫 답변까지 |
| 답변 정확도 | 85% 이상 | 사전에 승인된 평가 테스트셋의 정답 판정 비율 |
| 평균 질의 비용 | $0.03 이하 | 모델·임베딩 등 직접 AI 사용 비용의 질의당 평균 |
| LangChain 학습 커버리지 | 100% | RAG·TAG·CAG 각각 Runnable/Retriever/Tool 구현, 테스트와 학습 문서 완료 |

## 7. MVP 출시 기준

MVP는 다음 조건을 모두 충족해야 한다.

- 모든 Must 기능이 구현되고 핵심 통합 테스트를 통과한다.
- 정의된 성공 지표의 목표값을 충족한다.
- 제한된 베타 사용자가 전체 핵심 퍼널을 완료한다.
- 베타 과정에서 발견된 치명적 오류와 데이터 격리 문제를 해결한다.
- 파이프라인 버전 저장 및 롤백이 정상 동작한다.
- OpenAI와 Anthropic 키 등록·검증·교체·삭제 및 모델 목록 동기화가 정상 동작한다.
- 브라우저 저장소, API 응답, 애플리케이션 로그와 오류 추적 시스템에 API 키 원문이 남지 않는다.
- 동일한 테스트 질의를 OpenAI 모델과 Claude 모델로 각각 실행하고 공통 응답·비용 형식으로 비교할 수 있다.
- RAG·TAG·CAG가 LangChain 표준 인터페이스로 구현되고 각 전략의 단위·통합 테스트와 학습 문서가 존재한다.
- GCP staging 환경의 Artifact Registry에 이미지를 push하고 GCE Docker Compose에서 전체 핵심 퍼널을 완료한다.

## 8. 주요 위험 및 대응

| 위험 | 영향 | 대응 방향 |
|---|---|---|
| RAG·TAG 답변 정확도 편차 | 사용자 신뢰 저하 | 평가 테스트셋과 출처 표시 적용 |
| 자동 생성 SQL의 안전성 | 데이터 유출·변경 위험 | 읽기 전용 연결, 쿼리 검증 및 실행 제한 |
| 테넌트 데이터 혼선 | 심각한 보안 사고 | 저장소·검색 인덱스·캐시 격리 테스트 |
| LLM 지연시간 변동 | p95 성능 목표 미달 | 스트리밍, 캐시, 타임아웃 및 모델별 관측 |
| 질의 비용 증가 | 목표 원가 초과 | 토큰 사용량 제한 및 CAG 활용 |
| 외부 데이터 동기화 실패 | 오래된 답변 제공 | 동기화 상태·오류 표시 및 재시도 지원 |
| API 키 유출 | Provider 계정 오용과 비용 손실 | app-level 암호화, root-only master key, 쓰기 전용 UI, 로그 마스킹, Admin RBAC |
| Provider API 장애·제한 | 응답 지연 또는 서비스 중단 | Provider별 timeout·circuit breaker·rate limit 관측, 승인된 fallback |
| 모델 목록·기능 변경 | 저장된 파이프라인 실행 실패 | Provider Models API 동기화, 배포 전 모델 가용성 검사, 모델 ID 버전 고정 |
| Provider별 파라미터 차이 | 결과 불일치 또는 잘못된 요청 | 공통 Provider Adapter 계약과 capability 기반 설정 UI |
| LangChain 추상화 과사용 | 디버깅 난이도와 프레임워크 결합도 증가 | 단순 Runnable 우선, 명시적 Adapter 경계, 핵심 로직 단위 테스트 |
| GCP 비용 증가 | 학습 환경 유지 비용 초과 | GCE right-sizing, 비사용 시간 VM 중지, Artifact Registry 정리 정책과 예산 알림 |
| 단일 GCE 장애 | 전체 서비스와 데이터 접근 중단 | 자동 재시작, health check, Persistent Disk snapshot, 복구 runbook |
| 동일 VM의 상태·애플리케이션 결합 | 배포나 자원 고갈이 DB·캐시에 영향 | 전용 data disk, container resource limit, 순차 배포와 백업 검증 |
| VM master key 유실 | 저장된 Provider 키 복호화 불가 | root 전용 파일의 별도 암호화 백업과 키 회전 runbook |

## 9. 검증 필요 가정

- CAG는 **Cache-Augmented Generation**을 의미한다.
- 정확도 85%는 베타 이전에 합의된 평가 테스트셋을 기준으로 계산한다.
- p95 3초는 전체 답변 완료 시간이 아닌 **최초 응답 시작 시간**을 의미한다.
- 질의당 $0.03에는 LLM 및 임베딩 직접 비용이 포함되며 일반 인프라 비용은 제외한다.
- 사용자는 본인이 관리 권한을 가진 OpenAI·Anthropic API 키만 등록한다.
- API 키 입력과 Provider 호출은 항상 서버를 경유하며 브라우저에서 OpenAI·Anthropic API를 직접 호출하지 않는다.
- 모델명은 문서에 고정된 목록이 아니라 각 Provider Models API에서 키 권한 기준으로 동기화한다.
- 초기 RAG는 지연시간과 학습 용이성을 위해 2-step RAG로 구현하고 Agentic RAG는 후속 실험으로 분리한다.
- GCP 기본 배포 리전은 한국 사용자 지연시간과 서비스 지원 여부를 검토해 확정한다.
- 초기 배포는 단일 GCE VM을 전제로 하며 고가용성이나 무중단 배포가 필요해지면 다중 VM 또는 관리형 서비스 전환을 별도 결정한다.
