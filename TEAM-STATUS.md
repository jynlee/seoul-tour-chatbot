# TEAM-STATUS — 서울 여행 친구

> 팀 운영의 **단일 진실 소스**. 태스크 완료·인터페이스 확정·중요 결정·새로 알게 된 함정이 생기면 담당자가 **즉시** 자기 섹션을 갱신한다. 세션이 끊겨도 새 팀이 이 문서만 읽고 이어갈 수 있어야 한다.
>
> 계획: `docs/superpowers/plans/2026-10-23-seoul-tour-chatbot.md` · 설계: `docs/superpowers/specs/2026-10-23-seoul-tour-chatbot-design.md` · 시안: `docs/superpowers/mockups/`

## ① 작업 개요
- 목표: 대화하며 서울 맛집·관광지를 추천받고, 귀여운 일러스트 지도에서 핀으로 확인하는 모바일 웹 챗봇.
- 완료 조건: 계획의 모든 태스크 체크 완료, `pytest -m "not integration"` · `node --test tests/js` 통과, `pytest -m integration` 통과(로컬 서비스 켜진 상태), `docs/manual-qa.md` 전 항목 통과, main에 병합·push.

## ② 팀 구성
| 역할 | 담당 태스크 | 작업 브랜치 |
|---|---|---|
| 리드 | T0, 병합·최종 확인 | main |
| 팀원1 backend | B1~B6 | worktree 브랜치 (시작 시 기록) |
| 팀원2 frontend | F1~F4 | `feat/frontend` |
| 팀원3 qa | Q1~Q2 (B6 완료 후 시작) | worktree 브랜치 (시작 시 기록) |

## ③ 태스크 분해 (공유 태스크 리스트)
상태: ⬜ 대기 · 🔄 진행 중 · ✅ 완료 · ⛔ 막힘. 가져갈 때 🔄로 바꾸고 이름을 적는다.

| ID | 내용 | 담당 | 선행 | 상태 |
|---|---|---|---|---|
| T0 | 뼈대·설정·API 계약 초안·이 문서 | 리드 | — | ✅ |
| B1 | 카탈로그 + 전화번호 보강 | 팀원1 | T0 | ⬜ |
| B2 | 거리·지역 이름표·기준점 결정 | 팀원1 | T0 | ⬜ |
| B3 | seoul-tour-v2 인덱스 + kNN 후보 검색 | 팀원1 | B1 | ⬜ |
| B4 | chat_message 대화 기록 저장소 | 팀원1 | T0 | ⬜ |
| B5 | 의도 판별 + 추천 + LLM | 팀원1 | B2, B3 | ⬜ |
| B6 | ChatService + FastAPI 앱 | 팀원1 | B4, B5 | ⬜ |
| F1 | 화면 뼈대 + S2a 첫 화면 | 팀원2 | T0 | ✅ 팀원2 |
| F2 | 일러스트 지도 모듈 | 팀원2 | F1 | ✅ 팀원2 |
| F3 | 대화·결과·카드·접힘 B안 | 팀원2 | B6, F2 | 🔄 팀원2 (화면 완료, B6 연동 대기) |
| F4 | GPS 위치 | 팀원2 | F3 | ⬜ |
| Q1 | API 테스트 스위트 | 팀원3 | **B6** | ⬜ |
| Q2 | 통합·화면 시나리오 점검 | 팀원3 | F3, F4 | ⬜ |

## ④ 합의된 인터페이스
**초안 (T0, 리드):** `app/schemas.py` — `ChatRequest{session_id?, message(1~500자, 앞뒤 공백 제거), location?{lat,lng}, selected_place_id?}` → `ChatResponse{session_id, answer, center?{lat,lng,label,source: gps|place|area|gu|history}, places[PlaceOut{id,title,kind: food|tour,category,addr,tel,lat,lng,image,distance_m?,walk_min?}]}` / `GET /api/history/{session_id}` → `{session_id, messages[{role,message,center?,places,created_at}]}` / `GET /api/health` → `{opensearch,ollama,mysql: bool}` / 503 `detail`: "검색 서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요."

**확정:** (팀원1·2가 SendMessage로 합의 후 여기에 기록 — 날짜, 바뀐 점)

## ⑤ 결정 사항 로그
- 2026-10-23 리드: 이 환경(Claude Code 2.1.309)에는 공유 태스크 리스트 전용 도구가 없어서 **이 문서 ③ 표를 공유 태스크 리스트로 쓴다**. 팀원은 백그라운드 에이전트로 뜨고, 서로 agentId로 `SendMessage` 한다(아래 ⑦ 명단).
- 2026-10-23 리드: MySQL은 전용 컨테이너 `seoul-tour-mysql`(3306, DB `seoul_tour` 생성됨), OpenSearch는 `food-opensearch`(https://localhost:9200) 공유. 접속 정보는 루트 `.env`(git 제외) — worktree에는 `.env`가 없으니 **메인 폴더 `C:\Users\SMT03\SeoulTourChatbot\.env`를 복사해서** 쓴다.

## ⑥ 블로커
(없음)

## ⑦ 팀원별 작업 로그 (컨텍스트 노트)
명단(agentId): 리드가 팀원을 띄운 뒤 기록. 팀원1 backend = `aba34c491b89ebbac`

### 리드
- T0 완료: `app/config.py`(Settings·load_settings·ConfigError), `app/schemas.py`, `pytest.ini`(integration 마커), `requirements.txt`(설치 확인됨), `.env.example`, `data/seoul_tour.json`(원본 복사, 수정 금지).
- 함정: 원본 데이터 `tel` 574건 전부 빈 값, `도심속 바다축제`만 좌표 0.

### 팀원1 backend
-

### 팀원2 frontend
- 브랜치 `feat/frontend`. 팀원1(backend) agentId `aba34c491b89ebbac`로 API 조율.
- F1 완료: `static/index.html`, `css/app.css`, `js/landmarks.js`(시안 SVG 그대로), `js/home.js`(renderHome·S2a), `js/app.js`. 입력창(`#inp`)은 홈/결과 공용으로 index.html에 고정.
- 결정: 계획과 달리 DOM에 의존하지 않는 모듈은 따로 뺌 — `home.js`(renderHome), F3의 `view.js`(cardHtml·chipLabel), F4의 `geo.js`(requestLocation). app.js는 import 시 DOM을 건드려서 node 테스트에서 import 불가하기 때문.
- 결정: 크기는 결과 시안(폰 폭 300px) → 393px 기준 약 1.3배로 맞춤. 첫 화면 칩 3개(📍 내 주변 맛집·🏯 종로 관광지·☕ 성수 카페)가 한 줄에 들어가게 12.5px.
- API 계약: 팀원1과 2026-10-23 합의(④). 핀 이모지는 category 키워드로 고름(카페/전통찻집→☕, food→🍽️, 역사→🏯, 자연·휴양·공원→🌳, 쇼핑→🛍️, 문화→🏛️, 축제·행사·공연→🎉, 레포츠→🏃, 기본 📍).
- F2 완료: `static/js/map.js`(computeBounds·project·mulberry32·seedFor·riverVisible·renderMap), `emoji.js`(placeEmoji), `util.js`(esc), `tests/js/map.test.mjs` 11개 통과.
- 결정(지도): 기준점 900m 안의 6대 랜드마크는 범위에 포함해서 미니 일러스트가 보이게 함(광화문→경복궁). 한강 물빛은 S2a처럼 **짧은 직선**만(시안 결과 화면의 q 곡선은 '흰 곡선' 안티목표와 헷갈려서 뺌). 이름표끼리 겹치면 순위 낮은 장소 이름표만 숨김(핀은 그대로). 핀은 물방울 끝이 좌표에 오도록 배치. 선택 핀이 있으면 내 위치(없으면 기준점)에서 점선 '걸어서' 경로.
- F2 리뷰 반영(537b109): 핀 밀어내기(spreadPins), 길은 강 앞에서 끝나고 세로 큰길만 다리, 강 있으면 범례 위쪽.
- F3 화면(가짜 API로 확인): `api.js`(sendChat·fetchHistory, 실패 시 한국어 Error), `view.js`(cardHtml·chipLabel·bubbleHtml·foldBarHtml·placeChipsHtml), `app.js` 상태·이벤트. 테스트 26개 통과. **미완성: 실제 백엔드(B6) 연동 확인 전.**
- 결정(F3): 카드 ✕로 닫아도 `selectedId`는 남겨서 다음 요청 `selected_place_id`로 보냄(새 추천이 오면 초기화). 걷는 점선은 내 위치(GPS)가 있을 때만(기준점엔 표시가 없어 선이 허공에서 시작해 보여서). 첫 추천 전에는 지도 자리를 숨기고 대화만 보임. 새로고침 복원 실패 시 첫 화면 유지.
- 확인 도구(저장소 밖): 가짜 API 서버 `scratchpad/mock_server.py <static경로> 8002`와 iframe 하네스 `/__h/harness.html#reset;send:…;click:…`로 클릭 시나리오 스크린샷.
- **함정: Node 24에서 `node --test tests/js`(디렉터리)는 MODULE_NOT_FOUND로 실패** → `node --test "tests/js/*.test.mjs"`로 실행해야 함(완료 조건 명령도 이걸로).
- 함정: Windows에서 헤드리스 Chrome `--window-size=393,…`은 최소 폭(약 500px) 때문에 실제로는 393이 안 됨 → 393×852 iframe을 감싼 페이지를 찍어서 비교함.

### 팀원3 qa
-

## ⑧ 다음에 이어서 할 일
- 리드: 팀원 3명 띄우기 → 각자 ③에서 태스크 가져가기.
