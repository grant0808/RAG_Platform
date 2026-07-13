# OpenAI provider credential 복호화 실패

## 증상

Playground에서 OpenAI model을 선택하고 프롬프트를 실행하면 streaming error로 다음 메시지가 표시된다.

```text
Runtime execution failed: Stored provider credential cannot be decrypted
```

관련 API 경로:

- `POST /api/v1/chat/stream`
- `POST /api/v1/chat`
- `POST /api/v1/rag/query`

## 원인

OpenAI provider API key는 `provider_connections.encrypted_key`에 Fernet으로 암호화되어 저장된다.

복호화에는 backend 설정의 master key가 사용된다.

```env
FOUNDRY_MASTER_KEY_PATH=.data/master.key
```

아래 상황에서는 DB에 저장된 provider credential을 현재 backend가 복호화할 수 없다.

- `.data/master.key` 파일이 삭제되거나 새로 생성된 경우
- `FOUNDRY_MASTER_KEY_PATH`가 이전 실행과 다른 경로를 가리키는 경우
- DB는 기존 것을 사용하지만 `.data` 디렉터리 또는 master key만 초기화된 경우
- 다른 환경에서 만든 DB를 현재 로컬 환경으로 복사했지만 master key를 같이 가져오지 않은 경우

## 즉시 해결 방법

### 1. backend 환경변수에 OpenAI key 설정

현재 코드에서는 저장된 provider credential 복호화가 실패해도 `FOUNDRY_OPENAI_API_KEY`가 설정되어 있으면 runtime fallback key로 OpenAI 호출을 계속할 수 있다.

```env
FOUNDRY_OPENAI_API_KEY=sk-...
```

backend를 재시작한 뒤 Playground에서 다시 실행한다.

### 2. provider 재연결

Providers 화면 또는 API로 기존 OpenAI provider를 삭제 후 다시 연결한다.

```bash
curl -X DELETE http://localhost:8000/api/v1/providers/openai
```

다시 연결:

```bash
curl -X PUT http://localhost:8000/api/v1/providers/openai \
  -H "Content-Type: application/json" \
  -d '{"api_key":"sk-...","validate_connection":false}'
```

현재 코드에서는 저장 credential이 깨져 있어도 `DELETE /providers/openai`가 성공하도록 처리한다.

## 코드 동작

수정된 provider credential 처리 정책:

- `ProviderService.get_api_key()`
  - 저장된 encrypted key 복호화를 먼저 시도한다.
  - 복호화 실패 시 OpenAI provider에 한해 `settings.openai_api_key`를 fallback으로 사용한다.
  - fallback key가 없으면 기존처럼 `ConfigurationError`를 발생시킨다.

- `ProviderService.disconnect()`
  - 저장된 encrypted key 복호화가 실패해도 provider row 삭제를 허용한다.
  - 복호화에 성공한 경우에만 runtime OpenAI key 정리를 수행한다.

## 확인 방법

provider 목록:

```bash
curl http://localhost:8000/api/v1/providers
```

chat stream 실행:

```bash
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"안녕","provider":"openai"}'
```

테스트:

```bash
cd backend
uv run pytest tests/test_api.py -k "provider_key_is_masked or openai_provider_key_is_used or openai_provider_falls_back or provider_can_disconnect"
uv run ruff check src tests/test_api.py
```

## 예방 규칙

- `.data/master.key`는 DB의 provider credential과 한 쌍으로 관리한다.
- 로컬 DB를 유지할 경우 `.data/master.key`를 삭제하지 않는다.
- DB를 다른 환경으로 옮길 때는 master key도 함께 옮긴다.
- master key를 의도적으로 교체했다면 기존 provider credential은 삭제 후 다시 연결한다.
- 운영 환경에서는 `FOUNDRY_MASTER_KEY_PATH`를 고정된 secret volume 또는 secret manager 경로로 지정한다.

## 관련 파일

- `backend/src/foundry/core/crypto.py`
- `backend/src/foundry/services/providers.py`
- `backend/src/foundry/models/provider_connection.py`
- `backend/.env.example`

