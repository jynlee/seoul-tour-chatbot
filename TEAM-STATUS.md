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
| 팀원2 frontend | F1~F4 | `feat/frontend` |
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
| B7 | 관광공사 상세 정보 보강(detailIntro2 → detail) | 팀원1 | B1 | ✅ 팀원1 (574/574, 2026-10-26) |
| B8 | 장소 정보 질문 의도(place_info) | 팀원1 | B6, B7 | ✅ 팀원1 · ✅ 팀원3 검증(2b4a42a+f413aea, QA-4~8 통과, QA-9 보고) |
| B9 | 멀티턴(순서·이름 지칭, "다른 데 더", 조건 이어받기, 프롬프트에 최근 대화) | 팀원1 | B8 | ✅ 팀원1 · ✅ 팀원3 검증(2b4a42a+f413aea, QA-4~8 통과, QA-9 보고) |
| F1 | 화면 뼈대 + S2a 첫 화면 | 팀원2 | T0 | ✅ 팀원2 |
| F2 | 일러스트 지도 모듈 | 팀원2 | F1 | ✅ 팀원2 |
| F3 | 대화·결과·카드·접힘 B안 | 팀원2 | B6, F2 | ✅ 팀원2 |
| F4 | GPS 위치 | 팀원2 | F3 | ✅ 팀원2 |
| Q1 | API 테스트 스위트 | 팀원3 | **B6** | ✅ 팀원3 |
| Q2 | 통합·화면 시나리오 점검 | 팀원3 | F3, F4 | ✅ 팀원3 |

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
- 2026-10-23 B8·B9(팀원1): **API 필드 변경 없음.** 장소 정보 질문("고려삼계탕 주차 돼?", "두 번째 거기 어디야?")·되묻기·"다른 데 더"가 없을 때의 응답은 `places: []`, `center: null` → 프론트는 "고마워!"처럼 지도·핀 유지. 단 `/api/history`에는 이 봇 메시지가 `center:{source:"place", label:장소이름}`, `places:[]`로 저장됨(다음 "거기"가 그 장소를 가리키게 하려는 용도). 프론트 복원은 "places가 있는 마지막 봇 메시지" 기준이라 영향 없음.
- 2026-10-26 구 기준점·관광 세부 주제(팀원1): **API 필드 변경 없음.** 기준점 `source:"gu"`(또는 구를 이어받은 `history`)이면 결과가 그 구 전체에서 관련도순이라 `distance_m`이 1500을 넘을 수 있고 **거리순이 아님**(첫 번째가 가장 관련 있는 곳). area/place/gps는 기존대로 반경 1.5km·주제 맞는 곳 먼저, 그다음 거리순.
- 2026-10-26 QA-8 결정(리드, A안) — **값 규칙 보충, 필드 변경 없음:**
  1. 기준점이 구(`center.source:"gu"`)이면 `places`의 `distance_m`·`walk_min`은 **null**(구 중심 평균 좌표에서 잰 거리라 의미 없음). `center`는 그대로 보냄 → "center가 있어도 distance가 null일 수 있음". 프롬프트에도 거리·도보 표시 없음. (프론트 view.js는 `Number.isFinite(p.walk_min)`일 때만 도보 표시 → 안전, 리드 확인)
  2. 구 기준점을 이어받은 턴("다른 데 더", "카페는?" 등, 직전 center가 구)은 `source:"history"`가 아니라 **`source:"gu"`**(label=구 이름)로 나가고 거리 null — 프론트 요약 바의 gu 처리("강서구 · 추천 5곳")와 일치. 구가 아닌 직전 기준점을 이어받으면 기존대로 `history`.
- 2026-10-27 괄호 장소 이름·되묻기 이어받기(팀원1): **API 필드 변경 없음.** ① "석파정"·"길상사"처럼 괄호가 든 제목('대원군별장(석파정)', '길상사(서울)')을 괄호 뺀 이름·괄호 안 이름으로 불러도 그 장소로 인식(장소 정보 질문·기준점·직전 목록 지칭 모두). 응답의 `title`·`center.label`은 원래 제목 그대로. ② 챗봇이 장소를 되물은 직후(`CLARIFY_ANSWER`) 사용자가 장소 이름만 답하면 앞 질문(요금·주차 등 또는 "어디야")에 대한 장소 정보 답변 → `places: []`, `center: null`(지도 유지).
- 2026-10-23 QA-1 수정(팀원1, 팀원3 리포트): `ChatRequest.session_id`에 **최대 64자** 제한 추가 → 넘으면 422. (`chat_message.session_id`가 VARCHAR(64)라 긴 id는 기록이 조용히 안 남던 문제.) 프론트는 UUID(36자)라 영향 없음.

## ⑤ 결정 사항 로그
- 2026-10-23 리드: 이 환경(Claude Code 2.1.309)에는 공유 태스크 리스트 전용 도구가 없어서 **이 문서 ③ 표를 공유 태스크 리스트로 쓴다**. 팀원은 백그라운드 에이전트로 뜨고, 서로 agentId로 `SendMessage` 한다(아래 ⑦ 명단).
- 2026-10-23 리드: MySQL은 전용 컨테이너 `seoul-tour-mysql`(3306, DB `seoul_tour` 생성됨), OpenSearch는 `food-opensearch`(https://localhost:9200) 공유. 접속 정보는 루트 `.env`(git 제외) — worktree에는 `.env`가 없으니 **메인 폴더 `C:\Users\SMT03\SeoulTourChatbot\.env`를 복사해서** 쓴다.

## ⑥ 블로커
(없음)

## ⑦ 팀원별 작업 로그 (컨텍스트 노트)
명단(agentId): 리드가 팀원을 띄운 뒤 기록.
- 팀원1 backend: `aba34c491b89ebbac`
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
- B7(2026-10-23): `scripts/enrich_detail.py` — detailIntro2를 타입별로 골라 `detail`(parking·hours·rest_day·menu·fee·reservation·pet·stroller·contact·period·place·season·discount·age·packing)로 저장, `<br>`→` / `, 키 가림, 한 건마다 원자적 저장(임시 파일→교체, Windows 파일 잠금 재시도 — 처음엔 쓰기 중 `OSError 22`로 죽었음). **관광공사 일일 호출 한도(LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR)로 469/574에서 중단.** 채움(574 기준): contact 358, hours 357, rest_day 313, parking 175, fee 128, stroller 86, menu 84, period 50, place 45, age 9, discount 3. `Place.detail`로 로딩됨.
- B8·B9(2026-10-23, 커밋 25bea2d): 리드 재현 세션
  - 세션1: "명동 맛집 추천해줘"→"카페는?"→"다른 데 더 추천해줘"(전엔 카페를 잃고 남산 관광지, 답변 '남산 근처' 불일치)→"두 번째 거기 어디야?"(전엔 재검색·핀 교체)
  - 세션2: "강남 관광지 알려줘"(전엔 center가 장소 '강남')→"아까 첫 번째 거 다시 알려줘"(전엔 강남 식당 재검색)→"거기서 가까운 맛집은?"(연쇄 오류)
  - 지금 동작(FakeLLM 회귀 `tests/test_multiturn.py` + 실서버 확인): 세션1 → 명동 카페 → 명동 기준 이전과 겹치지 않는 카페 3곳 → 두 번째 카페 설명(places [], 핀 유지). 세션2 → center 강남구(gu) → 1번 장소 설명 → 그 장소 기준 맛집.
  - 구조: `app/dialog.py`(지칭 해석 `resolve_reference`: 순서 > 이름(최근 목록 우선) > "아까 그 ○○"(이름 일부·분류) > "거기"(selected → 방금 설명한 장소 → 직전 첫 장소), `asked_fields`, `is_near`/`is_more_request`/`is_explain`, `intent_from_places`, `format_history`). `ChatService.handle` 순서: (근처·추천·다른 데 아님) 정보 키워드 또는 순서/이름 지칭+설명 → place_info / 일상 대화 / 추천(빠진 카테고리 이어받기, 지칭 장소=기준점, "다른 데 더"는 같은 기준점에서 보여 준 곳 제외, 남은 게 없으면 솔직히 안내).
  - place_info: 물어본 항목이 detail에 하나도 없으면 LLM 없이 "고려삼계탕 — 주차 정보는 없어요. 전화(02-…)로 확인해 보세요." Ollama 다운이면 detail 값 그대로 템플릿. 대상 없으면 되묻기.
  - 기타: 구/지역 이름이 같은 이름의 장소보다 우선(`강남`=강남구, `대학로`=지역). 기준점이 장소면 그 장소는 결과에서 뺌. 프롬프트 최근 대화 6→8줄(약 4턴, 봇 턴에 기준점·보여 준 장소 이름), "이전 대화 장소 재추천 금지" 규칙(실측: '다른 데 더'에서 이전 카페 이름을 다시 말하던 문제 해결).
  - 테스트: 단위 100개 통과, `pytest -m integration` 9개 통과(`tests/integration/test_live_multiturn_backend.py` 포함, 끝나면 세션 삭제). 확인용으로 만든 test-* 세션은 chat_message에서 모두 지움.
- B7 완료(2026-10-26): 남은 105건 이어받아 **detail 574/574**(실패 0). 채움: contact 457, hours 456, rest_day 411, parking 257, menu 181, fee 128, stroller 89, period 50, place 45, packing 35, reservation 12, age 9, discount 3.
- 개선 3개(2026-10-26, 각각 회귀 테스트 먼저):
  - 2글자 장소명 오인(`app/center.py` `_short_title_used_as_place`): 제목이 공백 빼고 2글자 이하이면 ① 질문 전체가 그 이름(`기후`, `기후?`)이거나 ② 앞이 한글이 아니고(다른 낱말의 일부 X, `골목길목`) 바로 뒤(조사 은/는/이/가/도 하나 허용)에 장소로 쓰인 말(`근처·주변·가까운·맛집·카페·식당·에서·까지·가는·어디·위치·주차·영업·메뉴·전화·몇 시·휴무·가격·예약`)이 올 때만 장소. → "기후 변화 걱정 없는 실내 관광지"는 기준점 없음, "기후 맛집 근처 카페"는 기후. 대상 15곳(`가담·가문·개뿔·개화·계월·공푸·구펠·굴림·금룡·금문·기와·기후·길목·단하`, `강남`은 원래 구 우선). 최근 추천 목록 속 이름 지칭(`resolve_reference`의 in_last)은 방금 본 목록이라 그대로 느슨하게 둠.
  - 분류 단어 "궁" ↔ "궁금"(`app/dialog.py` `_has_word`): 한 글자 분류 단어는 뒤가 끝·한글 아님·조사(은/는/이/가/을/를/에/도/만/로/으로/랑/의/였)일 때만 인정. 두 글자 이상 단어는 기존대로 부분 문자열("전시회" 등 회귀 방지).
  - "다른 데 더"가 반경 밖으로만 이어질 때(`app/chat.py`, `app/llm.py` `all_far`·`mentions_far`·`FAR_MORE_NOTICE`): 결과가 **모두** 1.5km 밖이면 프롬프트에 "'○○' 1.5km 안에는 더 없어서 떨어진 곳을 골랐다, 첫 문장에서 솔직히 말할 것" 규칙. LLM 답에 `떨어`·`멀`·`km`가 없으면 "○○ 근처(1.5km 안)에는 더 보여드릴 곳이 없어서 조금 떨어진 곳을 골랐어요."를 앞에 붙임(처음엔 무조건 붙였더니 LLM이 같은 말을 반복해 두 번 나옴 → 조건부로 바꿈). LLM 다운이면 템플릿에 항상 붙이고 "근처 추천 장소" 문구 대신 "추천 장소를 지도에 표시했어요". 실서버(삼청동 카페 → 다른 데 더 ×3) 3번 모두 "삼청동에서 조금 떨어진 곳…"으로 확인.
- QA-4~7 수정(2026-10-26, 팀원3 리포트, 회귀 테스트 `tests/test_multiturn.py`·`tests/test_dialog.py`):
  - QA-4 "아까 그 궁" → 이름에 분류 단어('궁'·'카페' 등)가 든 장소가 같은 분류의 첫 장소보다 우선(`_partial_match` 점수 2.5). "종로 관광지" → "아까 그 궁 주차돼?" = 건청궁.
  - QA-5 목록 범위를 넘는 순서 지칭("6번째 거 어디야?") → `ORDINAL_OUT_OF_RANGE` "목록에는 5곳까지 있어요. 몇 번째 장소인지 다시 알려 주세요.", places [] (지도 유지). 순서 인식을 6~10까지 넓힘(`여섯`~`열`, `6`~`10번`).
  - QA-6 가리킬 장소가 없는 "거기 어디야?"(지시어+설명 질문, 근처·추천·다른 데 아님) → `CLARIFY_ANSWER`. "거기 근처 카페"(첫 메시지)는 기존대로 추천.
  - QA-7 "아까 그 식당"이 직전 목록에 없으면 그 전 추천 목록들(최근 것부터)에서도 찾음(`earlier_place_lists`, `resolve_reference(earlier_lists=)`).
- 구 기준점·산책 의도(2026-10-26, 리드 요청 — 사용자 확인 중 발견: "강서구에 산책할만한 곳"과 "강서구 공원"이 같은 5곳(클라이밍·도매시장·배드민턴장…)):
  - 원인: 구 기준점에도 1.5km 반경을 적용(구 중심 1.5km만 봄, 강서습지생태공원은 2670m라 빠짐), 산책·공원 키워드 없음.
  - `app/recommend.py`: 기준점이 구(`gu`, 또는 label이 구 이름인 `history`)면 **그 구에 속한 곳 전체**에서 kNN 관련도순(kNN 상위 100에 없던 같은 구 장소도 뒤에 붙임), 구 이름과 같은 제목('강남')은 뺌, 3곳 미만이면 기존처럼 가까운 곳으로 채움. `Recommendation.gu_wide`·`topic_missing` 추가.
  - `app/intent.py` `TOUR_TOPICS`: 야경·산책/자연·역사·문화/전시·쇼핑·체험/레포츠 키워드 → types=관광, `Intent.topic`. 음식·카페 키워드가 같이 있으면 주제 무시("한강 근처 맛집"은 음식점). 한 글자 '궁'은 단어 경계(`has_word`, dialog와 공유 — '궁금' 제외). '먹'·'밥' 같은 음식 키워드는 기존대로 부분 문자열.
  - 주제 맞는 곳 판정 `matches_topic`: 분류(cat2 한글명) 또는 제목 패턴. 산책/자연은 분류 `자연관광지`만(휴양관광지에 미로·스파·관광특구가 섞여 있어 제목 '공원·숲·둘레길·한강·호수·습지·○○산/천/길' 으로 판단), 제외 패턴(도서관·수영장·물놀이장·시장·스파 등). 맞는 곳을 앞으로(구: 관련도순 안에서, 반경: 주제 → 거리순).
  - 맞는 곳이 하나도 없으면 프롬프트에 솔직히 말하라는 규칙 + LLM 답에 '없/못 찾/어려/아쉽'이 없으면 "○○에서 산책·자연에 딱 맞는 곳은 못 찾아서 비슷한 관광지를 골랐어요."를 앞에 붙임(LLM 다운이면 항상). "다른 데 더"는 직전 주제를 이어받음. 구 결과는 프롬프트에서 도보·'조금 멂' 표시를 빼고 "○○구에 있는"으로 말하게 함, 먼 곳 안내도 안 붙임.
  - 실서버(8011) before → after: 강서구 산책/공원 → 1번 강서습지생태공원(전: 클라이밍·도매시장…, "공원 관련 장소가 없네요"). 금천구 산책(자연 관광지 0곳) → "아쉽게도 산책하기 좋은 곳은 없지만…". 종로 관광지 → 종로구 전체에서(광통교·바라캇 서울·경희궁 흥화문·광화문·석파정). 홍대 놀거리·명동 맛집·성수 카페 결과 동일, 멀티턴 세션1·2 정상.
- 테스트(2026-10-26): 단위 128개 통과, `pytest -m integration` 9개 통과. 확인용 test-* 세션은 chat_message에서 모두 지움.
- 괄호 장소 이름·되묻기 이어받기(2026-10-27, 사용자 재현 "종로 관광지 추천해줘"→"석파정 무료 입장이야?"(전: 되묻기)→"대원군별장"(전: 그 장소 근처 추천)):
  - 원인: `_match_place`·`resolve_reference` in_last가 "제목 전체가 메시지에 들어 있음"만 봄 → 괄호 제목 37곳(좌표 있는 곳 기준)은 사실상 이름으로 못 찾음. 되묻기 뒤 이름만 답하면 정보 키워드가 없어 추천 흐름으로 감.
  - `app/center.py` `title_aliases(title)`: 부르는 이름 후보 = 원래 제목 + 괄호 뺀 이름(공백 정리, 2글자 이상) + 괄호 안 이름. **괄호 안 이름 제외 기준:** 공백 빼고 2글자 미만(`樂`), 이름이 아닌 말(`서울`·`실내`·`실외`·`일본군 위안부` — `_NOT_NAMES`), `구 ○○`(옛 이름 설명), `…점`(지점 설명, `강남코엑스점`). 예: 대원군별장(석파정)→대원군별장·석파정, 국기원(세계태권도본부)→국기원·세계태권도본부, 올림픽체조경기장(KSPO DOME)→…·KSPO DOME(영문은 대소문자 무시).
  - 후보마다 기존 규칙 그대로: 구/지역 이름 안에 들어가는 이름은 무시, 2글자 이하는 `_short_title_used_as_place`('공기(Gongi)'→"공기 좋은 곳"은 아님, "공기 맛집 근처"는 공기). 우선순위: 정확히 같은 이름 > 가장 긴 이름 > 짧은 id. 직전 목록 지칭(in_last)도 `matched_alias`로 같은 후보 사용(원래 제목은 기존처럼 느슨한 부분 문자열, 파생 이름은 2글자 규칙 적용).
  - 회귀 확인: "남산 맛집"은 그대로 지역 남산(남산공원(서울)의 '남산공원'은 "남산"에 안 들어감), "남산공원 근처 카페"는 이제 장소 남산공원(서울)(전: 지역 남산). "서울 관광지"·"실내 관광지"·"강남 관광지"는 장소 없음.
  - `app/chat.py` `_clarified_question`: 직전 챗봇 메시지가 `CLARIFY_ANSWER`이고 이번 메시지가 장소를 가리키며 물어본 항목·설명 요청이 없으면(근처·추천·다른 데 아님) 앞 사용자 질문의 fields를 이어받아 `_place_info`. LLM 프롬프트 질문은 "이번 메시지 + 앞 질문"("대원군별장 무료 입장이야?"). 석파정은 요금 정보가 없어 LLM 없이 "대원군별장(석파정) — 요금 정보는 없어요. 전화(02-395-0100)로 확인해 보세요."
  - 실서버(8011) 확인: 위 대화 2·3턴 모두 위 문구, "거기 어디야?"→되묻기→"길상사"→길상사 설명(places []). 남은 동작(의도대로 둠): 되묻기가 아닌 상황에서 장소 이름만 말하면("대원군별장") 기존처럼 그 장소 근처 추천.
  - 테스트: `tests/test_place_alias.py`(신규), `tests/test_multiturn.py`·`tests/test_chat_service.py`(API 멀티턴)·`tests/integration/test_live_multiturn_backend.py`에 재현 테스트. 단위 154개, 통합 10개 통과. test-* 세션 삭제함.
- 알려진 한계: 임베딩 문장(`build_document_text`)에 설명이 없어 kNN만으로는 '산책'과 공원이 잘 안 맞음 → 주제 가산점으로 보완(재색인 안 함). 북촌처럼 반경 1.5km 안에 공원이 없으면 "없다"고 답함. 3글자 장소명(`고기다`·`골목집`·`그래픽`·`국시집` 등)도 일반 단어와 겹칠 수 있음(2글자만 규칙 적용). 2글자 규칙은 "기후 어때?"처럼 장소 쓰임 말 없이 물으면 장소로 안 봄(일부러 보수적으로).

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
- F4 완료(1af1537): `geo.js` requestLocation(미지원/거부/실패 문구, 8초), 📍 누르면 `pendingLocation` + 입력창 "📍 현재 위치 사용 중"·버튼 강조, 다시 누르면 취소, 다음 전송에 한 번 실어 보내고 비움. "📍 내 주변 맛집" 칩은 위치 요청 후 전송(실패해도 오류 말풍선 후 location null로 전송).
- 첫 화면 수정(f3b86e0, 사용자 요청): 🍜 핀 삭제, 포인터를 따라다니는 🎒(`follower.js`, 첫 화면에서만, 결과 화면 가면 해제).
- **F3·F4 실제 연동 확인 완료**(feat/backend 병합 a8c27d1, uvicorn 8000): 광화문 맛집 5곳 핀 → 개성만두 궁 카드 → "거기 근처 카페 있어?" 핀 교체(카페 3곳) → 접기·칩→카드 → "고마워!" 지도 유지 → 새로고침 복원(성수 카페) → GPS(가짜 geo 좌표 주입)로 내 위치 파란 점·걸어서 점선 → OPENSEARCH_PORT=9299로 띄운 서버에서 503 오류 말풍선. 스크린샷 `scratchpad/shots/real-*.png`.
- 연동 중 고친 것: 채팅 fetch 90초 타임아웃(첫 Ollama 호출이 느림, "답변이 너무 오래 걸려요" 문구), 강 있을 때 범례 클래스 `.top`이 상단 바 `.top` CSS와 겹쳐 글자가 커지던 버그 → `.up`으로 변경, 요약 바 "근처 · 추천" 띄어쓰기.
- 미확인: Chrome 개발자도구 Sensors로 실제 위치 권한 허용/차단 수동 확인은 못 함(헤드리스에서 navigator.geolocation을 가짜로 바꿔 확인). Q2에서 확인 부탁.
- 상단 바 시안 A(사용자 확정, 고운돋움은 되돌림): 🗺️ 삭제, Jua 21px "서울"(#ff6f8d) "여행친구"(#5a4632), 왼쪽 40px 랜드마크 배지(`brand.js` pickBadge·badgeSvg). 배지 = 응답 center에서 가장 가까운 6대 랜드마크(거리 제한 없음), center null이면 직전 배지, 처음엔 광화문(경복궁). 바뀔 때 Y축 뒤집기 0.4초, reduced-motion이면 바로. 새로고침 복원은 마지막 center로. 배지 그림 배치값은 `landmarks.js` BADGE_ART로 첫 화면 링과 공유.
- 상단 토글 제거(2026-10-26, 사용자 요청): 상단 바의 "▾ 지도 접기/▴ 지도 펼치기" 버튼 삭제(로고만). 펼친 지도 바로 아래에 얇은 손잡이 `#handle` "▴ 지도 접기"(예전 토글 글자 모양 그대로: #c07a8a 14px, 배경 없음, 가로 전체·가운데). 누르면 접힘, 요약 바 "지도 보기 ▾"로 다시 펼침. 보임 규칙은 `view.js` placesView(has, mapOpen)로 빼서 테스트. 손잡이 `aria-expanded="true"`, 요약 바 `aria-expanded="false"`, 둘 다 `aria-controls="map"`; 키보드로 눌렀을 때만 포커스를 반대쪽 버튼으로 넘김(마우스 클릭 땐 포커스 테두리 안 생기게). 스크린샷 `scratchpad/shots/toggle-open.png`·`toggle-folded.png`(+`toggle-reopen`·`toggle-none`).
- 첫 화면·새 대화(2026-10-26, 사용자 요청): 세션 ID를 `sessionStorage`로 옮김 → 같은 탭 새로고침은 복원, 새 탭·브라우저 재시작은 첫 화면. 예전 `localStorage`의 `stc.sessionId`는 시작할 때 지움. 저장·초기 상태는 `session.js`(loadSession·saveSession·clearSession·freshState, 테스트 6개)로 뺌. 결과 화면 상단 바 오른쪽 "↺ 새 대화"(`#newchat`, 예전 토글 글자 모양 #c07a8a 14px 그대로): 세션 ID·state 초기화, 대화·지도·칩·카드 비움, 배지 기본, 입력창·📍 대기 비움, 첫 화면 + 🎒 재시작. 응답 대기 중엔 disabled, 진행 중 복원은 세대 번호로 버림. 서버 기록은 안 지움. 확인(가짜 API 8013 + 헤드리스): 새로고침 복원 / 새 탭 첫 화면 / 같은 프로필로 브라우저 재시작 첫 화면 / 예전 localStorage 값 남겨도 첫 화면 / 새 대화 후 새로고침도 첫 화면 / 대기 중 버튼 비활성(CDP 실시간). 스크린샷 `scratchpad/shots/newchat-result.png`·`newchat-home.png`.
- QA-8 후속(2026-10-26): center.source가 `gu`(구 전체)면 요약 바 제목에서 '근처'를 뺌("강서구 · 추천 5곳"). 이때 백엔드가 보내는 distance_m·walk_min null은 칩·카드가 이미 숨김(`hasWalk`=Number.isFinite) — 테스트로 확인.
- 함정: 헤드리스 `--virtual-time-budget`은 네트워크 대기 중 가상 시간을 멈춰서 "응답 대기 중" 상태를 못 찍음 → `--remote-debugging-port` + node CDP 스크립트로 실시간 확인.
- 참고: 명동(37.5636,126.9827)은 "가장 가까운" 규칙상 숭례문(0.8km)이 남산타워(1.4km)보다 가까워 숭례문 배지가 됨.
- **함정: Node 24에서 `node --test tests/js`(디렉터리)는 MODULE_NOT_FOUND로 실패** → `node --test "tests/js/*.test.mjs"`로 실행해야 함(완료 조건 명령도 이걸로).
- 함정: Windows에서 헤드리스 Chrome `--window-size=393,…`은 최소 폭(약 500px) 때문에 실제로는 393이 안 됨 → 393×852 iframe을 감싼 페이지를 찍어서 비교함.

### 팀원3 qa
- 2026-10-23 시작. 브랜치 `feat/qa`(origin/feat/backend e633eee에서 분기). worktree 루트에 메인 `.env` 복사(커밋 안 함).
- Q1 완료: `tests/api/`(가짜 의존성 56건: 계약·422·세션·멀티턴 "거기 근처"·places 교체·Review Focus 1~5·잘못된 좌표·지어낸 장소·기록 저장소 장애·history·health) + `tests/integration/test_live_api.py`(실서비스 8건, `test-qa-` 세션만 쓰고 끝나면 삭제). `pytest -m "not integration"` 129 통과, `pytest -m integration` 8 통과.
- 버그 QA-1(팀원1, 850364d로 수정·재확인 완료): session_id 64자 초과 시 200인데 MySQL 저장이 조용히 실패 → 이제 65자 이상은 422.
- 함정: Git Bash에서 `curl -d '{"message":"한글"}'`은 인코딩이 깨져 400 "There was an error parsing the body"가 남(서버 문제 아님) → 파이썬 requests나 UTF-8 파일 `--data-binary @파일`로 보낼 것. 포트 8001은 다른 프로세스(정적 http 서버)가 쓰는 중 → QA 서버는 8011. 8000은 사용자용 서버(끄지 말 것).
- Q2 완료: `docs/manual-qa.md` 24개 항목 모두 통과(헤드리스 Chrome iPhone 14 Pro 393x852, 실서비스). 자동 점검 스크립트 `scripts/qa_mobile/run.mjs`(CDP, Node 24 내장 WebSocket): 8011 정상 / 8012 `OPENSEARCH_PORT=9299`(503) / 8013 `OLLAMA_URL=http://localhost:11999`(템플릿). `tests/integration/test_live_chat.py` 3건 추가. 스크린샷: `C:\Users\SMT03\AppData\Local\Temp\claude\C--Users-SMT03-SeoulTourChatbot\796dbd34-6ee3-48fe-b2a5-1247492df3b8\scratchpad\shots\01~14-*.png`.
- 버그 QA-2(팀원1, bed8ebc): 기준점 없을 때 "근처/주변"·지어낸 동네 이름, 기준점 대신 이전 지역명 → 프롬프트 보강, 재확인 통과(LLM 문구라 완전 보장은 아님). QA-3(팀원2, ea2ea88): 넓은 범위 지도에서 랜드마크끼리·핀과 겹침 → 겹치는 랜드마크 생략, 재확인 통과.
- 함정: 점검용 화면에서 만든 대화 기록은 UUID 세션이라 `test-qa-` 접두가 아님 → `results.json`의 `sessions`를 `delete_session()`으로 지움(완료).
- B8·B9 검증(2026-10-26, feat/backend 9f38d69 병합): `tests/api/test_multiturn_api.py`(가짜 의존성 + 실제 카탈로그 22건: 세션1·2, 정보 질문 이름/거기+선택/거기+첫 장소/정보 없음/LLM 다운/대상 없음, "거기 근처 카페"·"3번 출구" 회귀, history place_info 형식, "다른 데 더" 소진) + `tests/integration/test_live_multiturn.py`(실서비스 7건, Ollama만 끈 앱 포함) + 화면 `scripts/qa_mobile/run_b89.mjs`(14항목 통과, manual-qa B8·B9 절). 단위 177·통합 27·JS 37 통과.
- B9 반영해 기존 `test_tel_present_passes_through` 수정: 기준점이 된 장소는 결과에서 빠지므로 "가회동성당 근처" 대신 "종로 관광지"로 조회.
- 버그 QA-4~7(팀원1에게 보냄): "아까 그 궁"→같은 분류 첫 장소, 범위 밖 순서("6번째")→재추천, 맥락 없는 "거기 어디야?"→아무 관광지 추천, "아까 그 식당"이 직전 목록만 봄(경미).
- 함정: 지도 핀의 DOM 순서는 응답 순서와 다름(그리는 순서). "두 번째" 검증은 응답/기록 순서나 접힘 칩 순서로 할 것.
- B8·B9 재확인(2026-10-26, feat/backend b101c72 병합): QA-4~7 수정 확인 통과. 테스트 보강 — `test_multiturn_api.py` 35건(QA-4 '궁'/'궁금', QA-5 6·여섯·10번째, QA-6, QA-7, 2글자 장소명 '기후', "다른 데 더" 먼 곳 안내 추가), `test_live_multiturn.py` 10건(B7 574/574로 고려삼계탕 주차 '가능'이 생겨 "정보 없음"은 각시보쌈으로 교체, 정보 있음 케이스 추가, QA-4·5·6 실서비스). 화면 `run_b89.mjs` 17항목 통과(8012). 단위 204·통합 30·JS 37 통과.
- 함정: "종로 관광지" 실검색 상위 5곳엔 '궁'이 든 장소가 없음 → QA-4 실서비스 확인은 "종로 역사 관광지"로(테스트는 목록에서 '궁'이 든 첫 장소를 기대값으로 씀 — 51b8c0d 뒤 순서가 바뀌어 경희궁 흥화문).
- 51b8c0d(구 전체·관광 세부 주제) 확인(2026-10-26): `test_multiturn_api.py` +9(강서구 산책/공원 1번이 주제 맞는 곳·구 밖 장소 없음·프롬프트에 거리 표시 없음, 구 '다른 데 더'에 1.5km 안내 없음, 금천구 산책 솔직 안내(템플릿·LLM 누락 시), 한강 근처 맛집=음식점, 주제 이어받기, '궁금'은 역사 주제 아님), `test_live_multiturn.py` +3(강서습지생태공원 1번, 금천구 안내, 한강 맛집), 화면 GU-1·2. 단위 227·통합 33·JS 37·화면 19 통과.
- b689e90 회귀(2026-10-26): 단위 229·통합 33·JS 37·화면 B8·B9 19 + Q2 24 통과. `run.mjs`는 `QA_OK`/`QA_OS_DOWN`/`QA_LLM_DOWN` 환경 변수로 주소 지정 가능(이번엔 8012/8013/8014). test-qa- 세션 남은 것 0.
- 2026-10-26 중단 시점(사용자 요청으로 종료): QA-8 리드 결정 ①(gu면 distance_m·walk_min null + 프론트 요약 바 "강서구 · 추천 5곳") 반영분은 **아직 병합·확인 안 함**. 확인 완료 기준은 feat/backend b689e90 + feat/frontend ea2ea88(feat/qa e6af8fb). 서버(8012~8014) 꺼짐, test-qa- 세션 0.
- QA-8(팀원1→리드 결정 ① 확정, 백엔드 5bed7dc→2fee772(최종, d822a58 문서), 프론트 f413aea): 구 기준점일 때 거리·도보가 구 중심점 기준이라 카드 "강서구에서 약 40분"·요약 바 "강서구 근처"가 오해를 줌 → gu일 때 distance/walk null(④ 계약 변경) 또는 프론트에서 숨김 제안.
- **QA-8 최종 확인(2026-10-27, feat/backend d822a58 + feat/frontend f413aea 병합, 충돌 없음):** 통과. 테스트 수정 — `assert_contract`(gu면 거리 null), `test_gu_wide_may_exceed_radius`(응답 거리 null이라 좌표로 1.5km 밖 확인), 구 '다른 데 더'·주제 이어받기에 source gu·거리 null 검사. 새 테스트 — 구 이어받은 턴('다른 데 더'·'맛집은?')·두 번 이어받기 gu, area/place/gps 거리 int, 명동 이어받기 history+int, 실서비스 2건. 화면 — `#toggle`→`#handle`, 세션 ID `sessionStorage`, B9-4 "강남구 · 추천", GU-1b·1c, `run.mjs` 8b(새 탭 첫 화면)·8c(↺ 새 대화). 결과: 단위 239+xfail 2·통합 35·JS 52·화면 B8·B9 21/21·Q2 25/26(11b LLM 문구, 회귀 아님).
- **버그 QA-9(2026-10-27, 리드에게 보고):** 구 안에 맞는 곳이 0곳이면(카탈로그 카페 14곳뿐 → "강서구 카페 추천해줘", "강서구 공원" 뒤 "카페는?", 마포구도 같음) `recommend.py`가 구 분기를 지나 가장 가까운 곳 대체로 빠짐 → `source:"gu"`인데 `distance_m` 12838·`walk_min` 192(용산구·종로구 카페). 화면은 "🚶 강서구에서 약 192분"·칩 "192분"이 다시 보임(QA-8 이전 문제). 재현: `tests/api/test_multiturn_api.py::test_qa9_gu_with_no_match_still_no_distance`(xfail strict — 고치면 XPASS로 실패하니 xfail 표시를 지울 것).
- **2b4a42a(괄호 장소 이름·되묻기 뒤 이어받기, backend-2) 확인(2026-10-27):** 통과. 새 `tests/api/test_alias_clarify_api.py` 32건(괄호 안·뺀 이름·영문 대소문자·직전 목록 지칭·기준점, 이름 아닌 괄호 말 '서울'·'실내'·'실외'·'…점'·'구 ○○', 2글자 별명 '공기', 남산/남산공원 회귀, 되묻기 이어받기·새 정보 우선·한 번만·기록 형식), `test_live_multiturn.py` +6, 화면 AL-1~3. 최종: 단위 294+xfail 2·통합 41(+환경 경합 1)·JS 52·화면 B8·B9 24/24·Q2 26/26.
- 함정: 통합 실행 중 `tests/test_history.py::test_keeps_latest_100[mysql]`가 한 번 17건으로 실패(단독 3회 통과) — 같은 MySQL을 쓰는 다른 세션이 `test-%` 세션을 지우면 생김. 통합은 다른 팀원 테스트와 겹치지 않게 돌릴 것.
- 함정: 요약 바 `#fold` innerText는 flex라 "강서구\n· 추천 5곳"처럼 줄바꿈이 섞임 → 공백으로 바꿔 비교. 세션 ID는 74d76eb부터 `sessionStorage`(새 탭은 첫 화면).

## ⑧ 다음에 이어서 할 일
- 리드: 팀원 3명 띄우기 → 각자 ③에서 태스크 가져가기.
- 팀원1 (2026-10-27): 괄호 장소 이름("석파정"·"길상사") 인식 + 되묻기 뒤 이름만 답하면 앞 질문 이어받기 ✅(⑦ 참고) → qa-2에게 재확인 요청함.
- 팀원1 (2026-10-26): B7 데이터 574/574 ✅, 개선 3개(2글자 장소명·"궁" 단어 경계·"다른 데 더" 먼 곳 안내) ✅, QA-4~7 수정 ✅(팀원3 재확인 대기), 구 기준점 전체 검색·관광 세부 주제(산책·역사·전시·쇼핑·체험·야경) ✅, QA-8(구 기준점 거리 null + 구를 이어받은 "다른 데 더"도 source "gu") ✅ 2fee772 — 리드가 다음 세션 할 일로 적은 "이어받은 구 source=gu"는 이미 반영됨(실화면 확인만 남음: 요약 바 "강서구 · 추천 5곳"). 2026-10-26 사용자 요청으로 여기서 중단. 남은 일: 팀원3 QA의 B8·B9 버그 리포트 대응. 남은 개선 후보: 3글자 장소명 오인(⑦ 참고).
- 팀원1: B1~B6 완료(`feat/backend`). 남은 일은 팀원3(Q1·Q2) 버그 리포트 대응. Q1은 `tests/conftest.py`의 `small_catalog`·`FakeEmbedder`·`FakeSearcher`·`FakeLLM`과 `InMemoryHistoryRepo`로 `create_app(Deps(...))`를 만들면 됨(예: `tests/test_chat_service.py`).
- 팀원3 (2026-10-27): QA-8 최종 확인 + 2b4a42a(괄호 이름·되묻기 이어받기) 확인 끝(⑦ 참고). 남은 일: QA-9 수정되면 xfail 지우고 재확인, 리드 병합 후 실제 휴대폰 위치 권한 팝업은 사람이 확인.
- (완료) 팀원3 2026-10-26 중단 시점 할 일 — QA-8 확인:
  1. worktree `agent-a3b7fc5a951212262`(feat/qa)에서 `git merge origin/feat/backend`(2fee772 이상) + `git merge origin/feat/frontend`(f413aea 이상). TEAM-STATUS 충돌은 양쪽 살리기.
  2. 테스트 기대값 맞추기(QA-8 최종 규칙, ④ 참고): 기준점이 구면 places의 `distance_m`·`walk_min`이 null, 구 결과 뒤 "다른 데 더"·"카페는?"도 center.source=`gu`(이전엔 history). 고칠 곳 예상: `tests/api/test_multiturn_api.py`의 `test_gu_wide_may_exceed_radius`(distance>1500 검사 → null 검사로), `test_topic_carried_to_more`·`test_gu_wide_more_has_no_far_notice`(center.source gu 추가 검사), `tests/api/test_chat_api.py`의 `assert_contract`(center 있으면 거리 int라는 가정 → gu면 null 허용), `tests/integration/test_live_api.py::test_live_area_and_gu`. 새 테스트: gu 첫 턴·이어받은 턴 모두 거리 null, area/place/gps는 거리 int 유지, 명동(area) 이어받기는 source history.
  3. 화면: `run_b89.mjs` GU-1 기대를 요약 바 "강서구 · 추천 5곳"('근처' 없음)·카드에 🚶 도보 줄 없음·칩에 분 없음으로 바꾸고, 8012로 `run_b89.mjs` + 8012/8013/8014로 `run.mjs`(QA_OK/QA_OS_DOWN/QA_LLM_DOWN) 재실행.
  4. 단위·통합·JS·화면 전체 → manual-qa(QA-8 처리·GU 항목)·TEAM-STATUS 갱신 → 커밋·push → 리드에게 보고(리드가 그 결과로 main 병합). 리드 병합 후 실제 휴대폰 위치 권한 팝업만 사람이 한 번 확인 권장.
