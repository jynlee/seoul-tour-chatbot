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
| 팀원1 backend | B1~B6 | `feat/backend` |
| 팀원2 frontend | F1~F4 | worktree 브랜치 (시작 시 기록) |
| 팀원3 qa | Q1~Q2 (B6 완료 후 시작) | worktree 브랜치 (시작 시 기록) |

## ③ 태스크 분해 (공유 태스크 리스트)
상태: ⬜ 대기 · 🔄 진행 중 · ✅ 완료 · ⛔ 막힘. 가져갈 때 🔄로 바꾸고 이름을 적는다.

| ID | 내용 | 담당 | 선행 | 상태 |
|---|---|---|---|---|
| T0 | 뼈대·설정·API 계약 초안·이 문서 | 리드 | — | ✅ |
| B1 | 카탈로그 + 전화번호 보강 | 팀원1 | T0 | ✅ 팀원1 |
| B2 | 거리·지역 이름표·기준점 결정 | 팀원1 | T0 | ✅ 팀원1 |
| B3 | seoul-tour-v2 인덱스 + kNN 후보 검색 | 팀원1 | B1 | ✅ 팀원1 |
| B4 | chat_message 대화 기록 저장소 | 팀원1 | T0 | ✅ 팀원1 |
| B5 | 의도 판별 + 추천 + LLM | 팀원1 | B2, B3 | ✅ 팀원1 |
| B6 | ChatService + FastAPI 앱 | 팀원1 | B4, B5 | ✅ 팀원1 |
| B7 | 관광공사 상세 정보 보강(detailIntro2 → detail) | 팀원1 | B1 | 🔄 팀원1 |
| B8 | 장소 정보 질문 의도(place_info) | 팀원1 | B6, B7 | 🔄 팀원1 |
| B9 | 멀티턴(순서·이름 지칭, "다른 데 더", 조건 이어받기, 프롬프트에 최근 대화) | 팀원1 | B8 | 🔄 팀원1 |
| F1 | 화면 뼈대 + S2a 첫 화면 | 팀원2 | T0 | ⬜ |
| F2 | 일러스트 지도 모듈 | 팀원2 | F1 | ⬜ |
| F3 | 대화·결과·카드·접힘 B안 | 팀원2 | B6, F2 | ⬜ |
| F4 | GPS 위치 | 팀원2 | F3 | ⬜ |
| Q1 | API 테스트 스위트 | 팀원3 | **B6** | ⬜ |
| Q2 | 통합·화면 시나리오 점검 | 팀원3 | F3, F4 | ⬜ |

## ④ 합의된 인터페이스
**초안 (T0, 리드):** `app/schemas.py` — `ChatRequest{session_id?, message(1~500자, 앞뒤 공백 제거), location?{lat,lng}, selected_place_id?}` → `ChatResponse{session_id, answer, center?{lat,lng,label,source: gps|place|area|gu|history}, places[PlaceOut{id,title,kind: food|tour,category,addr,tel,lat,lng,image,distance_m?,walk_min?}]}` / `GET /api/history/{session_id}` → `{session_id, messages[{role,message,center?,places,created_at}]}` / `GET /api/health` → `{opensearch,ollama,mysql: bool}` / 503 `detail`: "검색 서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요."

**확정:** (팀원1·2가 SendMessage로 합의 후 여기에 기록 — 날짜, 바뀐 점)
- 2026-10-23 팀원1·2 합의: 초안 그대로 확정(필드 변경 없음). 보충 규칙:
  - 축제/행사(contenttypeid 15)는 `kind:"tour"`로 나감(분홍 핀). 내부 `Place.kind`의 `"event"`는 API에 노출 안 됨.
  - `category`는 한글 분류명: 음식점은 cat3 수준(`한식`·`양식`·`일식`·`중식`·`이색음식점`·`카페/전통찻집`), 그 외는 cat2 수준(`역사관광지`·`자연관광지`·`휴양관광지`·`체험관광지`·`건축/조형물`·`문화시설`·`축제`·`공연/행사`·`육상레포츠`·`수상레포츠`·`쇼핑` 등), 없으면 `기타`. 프론트 이모지: `카페/전통찻집`→☕, 그 외 food→🍽️, tour는 category 키워드로.
  - `tel`·`image`는 없으면 `""`. `center`가 `null`이면 `distance_m`·`walk_min`도 `null`.
  - 일상 대화 응답은 `places: []`, `center: null` (지도 유지).
  - `/api/history`: `created_at`은 ISO 문자열(`2026-10-23T14:05:00`), 오래된 순, 없는 세션은 `messages: []`. user 메시지는 `center:null, places:[]`.
  - 오류: 422(FastAPI 기본 검증 형식), 503 `{"detail":"검색 서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요."}`.
- 2026-10-23 B6 완료(팀원1) — 실제 동작 기준 보충:
  - 실행: `uvicorn app.main:create_app --factory --port 8000` (worktree 루트에 `.env` 필요, 시작에 임베딩 모델 로딩 ~10초). `static/`이 있으면 `/`에 마운트(`index.html`).
  - `/api/health` 실측 `{"opensearch":true,"ollama":true,"mysql":true}`. 채팅 한 턴 약 2~7초(Ollama). 첫 Ollama 호출은 모델 로딩으로 +13초 가능 → 프론트 fetch 타임아웃은 넉넉히(60초 이상).
  - LLM 실패 시 answer = `template_answer` 문구. 단, 반경 안 장소가 없어 가까운 곳으로 대체한 경우에만 뒤에 ` (가장 가까운 곳은 2.3km 떨어진 ○○예요)`가 붙음.
  - `tel`은 관광공사 원문 그대로라 `"광화문 관광안내소 02-735-8688"`, `"강남구청 02-3423-6000~3 …"`처럼 설명이 섞일 수 있음(457/574건 있음).
  - 기준점 없는 검색(예: "이번 주 축제")은 `center:null`, `distance_m/walk_min:null`.
- 2026-10-23 QA-1 수정(팀원1, 팀원3 리포트): `ChatRequest.session_id`에 **최대 64자** 제한 추가 → 넘으면 422. (`chat_message.session_id`가 VARCHAR(64)라 긴 id는 기록이 조용히 안 남던 문제.) 프론트는 UUID(36자)라 영향 없음.

## ⑤ 결정 사항 로그
- 2026-10-23 리드: 이 환경(Claude Code 2.1.309)에는 공유 태스크 리스트 전용 도구가 없어서 **이 문서 ③ 표를 공유 태스크 리스트로 쓴다**. 팀원은 백그라운드 에이전트로 뜨고, 서로 agentId로 `SendMessage` 한다(아래 ⑦ 명단).
- 2026-10-23 리드: MySQL은 전용 컨테이너 `seoul-tour-mysql`(3306, DB `seoul_tour` 생성됨), OpenSearch는 `food-opensearch`(https://localhost:9200) 공유. 접속 정보는 루트 `.env`(git 제외) — worktree에는 `.env`가 없으니 **메인 폴더 `C:\Users\SMT03\SeoulTourChatbot\.env`를 복사해서** 쓴다.

## ⑥ 블로커
(없음)

## ⑦ 팀원별 작업 로그 (컨텍스트 노트)
명단(agentId): 리드가 팀원을 띄운 뒤 기록.
- 팀원2 frontend: `a3f8272f943c570fa` (팀원1이 리드에게 받아 기록)
- 팀원3 qa: `a3b7fc5a951212262` (팀원1이 리드에게 받아 기록)

### 리드
- T0 완료: `app/config.py`(Settings·load_settings·ConfigError), `app/schemas.py`, `pytest.ini`(integration 마커), `requirements.txt`(설치 확인됨), `.env.example`, `data/seoul_tour.json`(원본 복사, 수정 금지).
- 함정: 원본 데이터 `tel` 574건 전부 빈 값, `도심속 바다축제`만 좌표 0.

### 팀원1 backend
- 2026-10-23 시작. 브랜치 `feat/backend`. worktree 루트에 메인 `.env` 복사해 사용(커밋 안 함).
- 함정(데이터): 좌표 0인 `도심속 바다축제` 외에 **좌표가 (19.69, 117.99)로 잘못 들어간 장소 6곳**(계남근린공원 2건·대치유수지체육공원·관악구민운동장·반포종합운동장·롯데백화점 김포공항점). → `has_coords`는 0 검사 + 서울 범위(위도 37.3~37.8, 경도 126.6~127.3) 검사. 이걸 안 하면 `강남구` 평균 좌표가 37.15로 틀어짐. 프론트도 지도 bounds 계산 시 같은 범위 밖 좌표는 무시 권장(백엔드는 이런 장소를 places에 넣지 않음).
- 함정(데이터): `계남근린공원` 제목 중복(id 다름). 원본 `cat2` `A0401`(쇼핑)이 기존 `cat2_map`에 없어 `쇼핑`을 추가함.
- 결정(B2): 기준점 규칙 보충 — ⑥ 구 이름은 `종로`처럼 '구'를 뗀 이름(2글자 이상, `중구` 제외)도 인정(첫 화면 칩 "🏯 종로 관광지"용). ③ 장소명은 질문 속 지역·구 이름 안에 들어 있는 짧은 제목은 무시(예: `강남역` 속 장소 `강남`). ⑤ 동 이름은 주소 토큰에서 `○○동`/`○○동N가`를 뽑음.
- B4: `chat_message` 테이블 생성 완료(`scripts/init_db.sql`, `MySQLHistoryRepo.ensure_table()`도 같은 DDL). MySQL 통합 테스트는 `test-` 접두 세션만 쓰고 끝나면 지움. 연결은 요청마다 새로 맺음(단순·스레드 안전, 대신 101건 저장 테스트가 ~15초).
- B1: 보강 스크립트 `--limit 5` 정상(5건 모두 tel 있음). 전체 실행 중 → 끝나면 `data/seoul_tour_enriched.json` 별도 커밋.
- B3: `seoul-tour-v2` 574건 색인 완료(`python scripts/build_index.py`, 임베딩 포함 약 1분). 문서 `_id`=contentid. 좌표 없는 7곳은 `location` 필드만 뺌. 기존 `seoul-tour` 인덱스는 이 OpenSearch에 원래 없음(건드리지 않음). kNN 결과 예: "성수 카페"+cat3 필터 → 성수 카페 5곳 정상.
- 결정(B5): ① 축제·행사·공연 키워드**만** 있으면 types=`{"15"}`만("이번 주 축제"에 음식점이 섞이지 않게), 다른 키워드와 같이 있으면 15 추가. ② 카페 cat3 필터는 카페 키워드만 있을 때("카페랑 맛집"은 음식점 전체). ③ 반경 1500m 안이 1~2곳이면 같은 조건의 가장 가까운 곳으로 **3곳까지 채움**(거리·도보는 실제값; 음식점이 100곳뿐이라 자주 생김). 0곳이면 계획대로 가장 가까운 3곳 + fallback_note.
- B5: Ollama 호출에 `"think": false` 넣음(gemma4 생각 출력 방지). 실호출 약 4초, 첫 호출은 모델 로딩 ~13초. 타임아웃 30초 → `LLMUnavailable` → 템플릿 답변.
- 테스트: `tests/__init__.py` 추가(패키지) → 테스트에서 `from tests.conftest import FakeSearcher` 가능. conftest에 `small_catalog`, `FakeEmbedder`, `FakeSearcher(catalog, scores, fail)`, `FakeLLM(answer, fail)`.
- B1 완료: 전화번호 보강 574/574 처리, **457건 번호 있음**(117건은 API에도 없음 → "전화번호 정보 없음"). 인덱스도 보강 후 재색인함. 주의: 요청 URL에 API 키가 들어가므로 오류 로그에서 키를 가리도록 고침.
- B6 완료: `app/chat.py`(ChatService, Deps), `app/main.py`(create_app, 503 처리, health, static 마운트, 시작 시 30일 지난 기록 삭제). 대화 기록 저장/조회가 실패해도 채팅은 계속(로그만 남김). 실서버 시나리오 확인: 광화문 맛집→5곳, "거기 근처 카페"(개성만두 궁 선택)→감꽃당 등 카페 3곳, "고마워!"→places [], "성수 카페"→area, "종로 관광지"→gu 종로구, GPS→"현재 위치".
- B5 보충: 프롬프트에 "날짜·영업시간·가격 등 없는 정보 말하지 말 것" 규칙 추가(축제 질문에 "이번 주에 열리는"이라고 지어낸 사례 있었음).
- QA-1 수정(850364d): `session_id` 최대 64자(④ 참고).
- QA-2 수정(답변 문구): 프롬프트 규칙 보강 — 기준점 없으면 "근처·주변"·지역명 금지 + 📍/지역을 알려 달라는 안내, 기준점 있으면 그 이름만 쓰기, 1500m 넘는 장소 줄에 "기준점에서 조금 멂" 표시. 실제 Ollama로 QA 재현 3건×2회 확인(모두 개선). LLM 출력이라 완전 보장은 아님.
- 알려진 한계: 2글자 장소명(`기후`, `길목`, `기와` 등)이 일반 단어로 질문에 들어가면 그 장소가 기준점이 됨(드묾, 그대로 둠).

### 팀원2 frontend
-

### 팀원3 qa
-

## ⑧ 다음에 이어서 할 일
- 리드: 팀원 3명 띄우기 → 각자 ③에서 태스크 가져가기.
- 팀원1: B1~B6 완료(`feat/backend`). 남은 일은 팀원3(Q1·Q2) 버그 리포트 대응. Q1은 `tests/conftest.py`의 `small_catalog`·`FakeEmbedder`·`FakeSearcher`·`FakeLLM`과 `InMemoryHistoryRepo`로 `create_app(Deps(...))`를 만들면 됨(예: `tests/test_chat_service.py`).
