# UI Playground Chat Auto Scroll

## 구현 범위

UI Playground의 채팅 메시지 영역은 새 메시지와 streaming 응답을 기준으로 자동 스크롤을 제어한다.

- 새 프롬프트 전송 직후 최신 사용자 메시지 위치로 이동
- AI 응답 placeholder와 token streaming 중 하단 근처에 있을 때만 하단 유지
- AI 응답 완료, citation/source/error 반영 시 하단 근처라면 최신 응답 표시
- 기존 session 선택 후 message history 로딩과 렌더링이 끝나면 즉시 하단 표시
- 사용자가 과거 메시지를 읽기 위해 위로 스크롤하면 자동 스크롤 중단
- 사용자가 다시 하단 근처로 이동하면 자동 스크롤 재활성화
- 메시지 높이가 늦게 변하는 경우를 위해 `ResizeObserver`, `MutationObserver`, double `requestAnimationFrame`을 사용

## 적용 컴포넌트

| 항목 | 위치 |
| --- | --- |
| 메시지 리스트 | `frontend/src/components/views/playground-view.tsx`의 `.messages` |
| scroll hook | `frontend/src/hooks/use-chat-auto-scroll.ts` |
| session message load | `loadMessages(sessionId)` |
| streaming 처리 | `streamChat(..., onToken/onDone/onCitation)` |

## UX 정책

| 상황 | 스크롤 정책 |
| --- | --- |
| 사용자가 prompt 전송 | `force=true`, `smooth`, 최신 메시지로 이동 |
| streaming token 추가 | 사용자가 하단 근처일 때만 `auto` scroll |
| AI 응답 완료 | 하단 근처라면 double frame 이후 하단 유지 |
| error message 추가 | 사용자가 보낸 요청의 결과이므로 `force=true`, `smooth`로 error가 보이도록 이동 |
| 기존 session 선택 | history 로딩 완료 후 `auto` scroll |
| 사용자가 위로 스크롤 | `autoScrollEnabled=false`, 강제 이동 금지 |
| 사용자가 하단 근처 복귀 | `autoScrollEnabled=true`, 이후 streaming 추적 재개 |

하단 근처 판정 threshold는 120px이다.

## 수동 테스트 체크리스트

- [ ] 새 프롬프트 전송 시 대화창이 하단으로 이동한다.
- [ ] AI 응답 placeholder가 추가되면 최신 응답 영역이 보인다.
- [ ] streaming 응답 중 하단 근처에 있으면 token을 따라 내려간다.
- [ ] streaming 응답 중 사용자가 위로 스크롤하면 강제로 하단 이동하지 않는다.
- [ ] 사용자가 다시 하단으로 내려오면 자동 스크롤이 재활성화된다.
- [ ] 기존 세션을 선택하면 메시지 로딩 후 가장 최근 대화가 보인다.
- [ ] session 전환 후 이전 session의 스크롤 위치가 새 session에 영향을 주지 않는다.
- [ ] 긴 Markdown/code block 또는 늦게 높이가 바뀌는 콘텐츠에도 하단 유지가 깨지지 않는다.
- [ ] 모바일 폭에서 `.messages` 영역이 동일하게 동작한다.

## 확인 필요 / TODO

- 현재 자동 검증은 lint/typecheck 중심이다. DOM scroll 동작은 Playwright 또는 React Testing Library 기반 테스트를 추가하면 더 안정적으로 회귀 방지할 수 있다.
- URL 기반 session deep link가 추가되면 route param 복원 후 동일한 `loadMessages` 완료 시점에 scroll-to-bottom을 호출하면 된다.
