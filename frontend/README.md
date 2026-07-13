# Foundry Web

PRD, API 명세, 인터랙티브 목업과 와이어프레임을 실제 FastAPI backend에 연결한 Next.js App Router 프론트엔드입니다.

## 기능

- 실제 DB 기반 Overview
- Source 파일 업로드·삭제
- OpenAI·Anthropic API 키 연결·모델 갱신·해제
- Pipeline 생성·Draft 수정·Version 저장·Rollback
- RAG SSE Playground와 LangChain trace
- Playground chat 자동 스크롤: 새 질문, SSE token, 응답 완료, 오류 표시 시 최신 메시지 위치를 유지하고 기존 session 선택 시 최근 대화부터 표시
- 기본 평가 실행
- Preview·Production Deployment 생성과 endpoint 복사

## 로컬 실행

터미널 1:

```bash
cd backend
uv run foundry-local bootstrap
uv run uvicorn foundry.main:app --reload
```

터미널 2:

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 <http://localhost:3000>에 접속합니다. Backend OpenAPI는 <http://localhost:8000/docs>입니다.

기본 API 주소는 `frontend/.env.local`의 `http://localhost:8000/api/v1`입니다. 다른 주소를 사용할 때 `.env.local`을 변경합니다.

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

## 검증

```bash
npm run verify
```

## Playground scroll UX

Playground 메시지 리스트는 `useChatAutoScroll` hook으로 제어한다. 사용자가 하단 근처에 있을 때는 streaming token을 따라 자동으로 내려가고, 과거 메시지를 읽기 위해 위로 스크롤하면 자동 스크롤을 멈춘다. 기존 chat session을 다시 열면 message history 로딩과 렌더링 완료 후 가장 최근 메시지가 보이는 하단 위치로 이동한다.

상세 정책과 수동 테스트 체크리스트는 [`../docs/UI_PLAYGROUND_SCROLL.md`](../docs/UI_PLAYGROUND_SCROLL.md)를 참고한다.

`npm run verify`는 lint, TypeScript typecheck, production build를 순서대로 실행합니다. 의존성 보안 점검이 필요하면 네트워크가 가능한 환경에서 `npm audit --audit-level=moderate`를 별도로 실행합니다.

### Playground 자동 스크롤 수동 체크리스트

- 새 프롬프트 전송 직후 최신 사용자 메시지가 보이는지 확인합니다.
- SSE streaming 중 하단 근처에 있으면 토큰이 추가될 때 대화창이 하단을 유지하는지 확인합니다.
- streaming 중 사용자가 과거 메시지를 보려고 위로 스크롤하면 강제로 하단 이동하지 않는지 확인합니다.
- 사용자가 다시 하단 근처로 내려오면 자동 스크롤이 재활성화되는지 확인합니다.
- 기존 session을 선택해 history 로딩이 끝난 뒤 가장 최근 메시지가 바로 보이는지 확인합니다.
- 긴 Markdown/code block 또는 citation/source block 때문에 높이가 늦게 바뀌어도 최종 하단 위치가 유지되는지 확인합니다.

## 디자인 방향

- Aesthetic: Industrial editorial workbench
- Differentiation anchor: 라임색 전략 노드와 검은 실행 trace rail
- Typography: 자체 호스팅 Manrope + Azeret Mono
- Motion: 화면 진입과 실행 상태에만 제한적으로 적용
- DFII: Impact 4 + Fit 5 + Feasibility 4 + Performance 4 − Risk 2 = 15

일반적인 카드형 AI 대시보드 대신 Pipeline graph, 불변 버전 레지스트리와 실행 trace를 제품의 주 시각 언어로 사용합니다.
