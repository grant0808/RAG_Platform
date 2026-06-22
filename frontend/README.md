# Foundry Web

PRD, API 명세, 인터랙티브 목업과 와이어프레임을 실제 FastAPI backend에 연결한 Next.js App Router 프론트엔드입니다.

## 기능

- 실제 DB 기반 Overview
- Source 파일 업로드·삭제
- OpenAI·Anthropic API 키 연결·모델 갱신·해제
- Pipeline 생성·Draft 수정·Version 저장·Rollback
- RAG·TAG·CAG SSE Playground와 LangChain trace
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
cp .env.local.example .env.local
npm install
npm run dev
```

브라우저에서 <http://localhost:3000>에 접속합니다. Backend OpenAPI는 <http://localhost:8000/docs>입니다.

기본 API 주소는 `http://localhost:8000/api/v1`입니다. 다른 주소를 사용할 때 `.env.local`을 변경합니다.

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

## 검증

```bash
npm audit --audit-level=moderate
npm run lint
npm run build
```

## 디자인 방향

- Aesthetic: Industrial editorial workbench
- Differentiation anchor: 라임색 전략 노드와 검은 실행 trace rail
- Typography: 자체 호스팅 Manrope + Azeret Mono
- Motion: 화면 진입과 실행 상태에만 제한적으로 적용
- DFII: Impact 4 + Fit 5 + Feasibility 4 + Performance 4 − Risk 2 = 15

일반적인 카드형 AI 대시보드 대신 Pipeline graph, 불변 버전 레지스트리와 실행 trace를 제품의 주 시각 언어로 사용합니다.
