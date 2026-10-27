# 서울 여행 친구 (서울 관광 챗봇) Implementation Plan

> **For agentic workers:** 이 계획은 **Agent Teams**(팀원 3명, 각자 독립 프로세스)로 실행한다. 각 태스크 제목의 `[담당]`을 보고 자기 태스크만 가져간다. 단계는 체크박스(`- [ ]`)로 추적한다. 팀원끼리는 `SendMessage`로 직접 소통하고, 태스크가 끝날 때마다 사용자에게 보고하며, `TEAM-STATUS.md`의 자기 섹션을 즉시 갱신한다.

**Goal:** 대화하며 서울 맛집·관광지를 추천받고, 귀여운 일러스트 지도에서 핀으로 확인하는 모바일 웹 챗봇을 만든다.

**Architecture:** FastAPI 하나가 `/api/*`와 정적 화면(`static/`)을 함께 서빙한다. 장소 원본은 메모리에 올린 카탈로그(`seoul_tour.json` + 전화번호 보강 파일)이고, OpenSearch kNN은 "의미가 맞는 후보"만 고르며, 거리·반경·기준점 계산은 파이썬에서 한다. 답변 문장은 Ollama가 만들지만 **장소 목록은 항상 카탈로그에서** 만든다.

**Tech Stack:** Python 3.11, FastAPI, uvicorn, pydantic v2, python-dotenv, opensearch-py, sentence-transformers(`jhgan/ko-sroberta-multitask`), requests, PyMySQL, pytest / 프론트: HTML·CSS·JavaScript(ES modules, 프레임워크 없음), 프론트 순수함수 테스트는 `node --test`(Node 24).

**Spec:** `docs/superpowers/specs/2026-10-23-seoul-tour-chatbot-design.md` (확정 시안: `docs/superpowers/mockups/`)

## Global Constraints

- 모든 사용자 화면 문구·답변은 한국어.
- 원본 `data/seoul_tour.json`은 수정 금지. 보강 결과는 `data/seoul_tour_enriched.json`.
- 비밀값(관광 API 키, OpenSearch·MySQL 계정)은 코드·저장소에 넣지 않는다. `.env`에서만 읽고 `.env.example`만 커밋. 필수 값이 비면 빠진 변수 이름을 모두 출력하고 종료.
- 포트 `8000`. OpenSearch 인덱스 `seoul-tour-v2`(기존 `seoul-tour` 건드리지 않음). Ollama 모델 `gemma4:e4b`. 임베딩 `jhgan/ko-sroberta-multitask`(768차원).
- MySQL DB `seoul_tour`, 새 테이블 `chat_message`(기존 `chat_history` 건드리지 않음). 세션당 최근 100개 유지, 30일 지난 기록 삭제.
- 추천: 최대 5곳(최소 3곳 목표), 반경 `1500`m, 도보 시간 = 직선거리 ÷ `67`m/분 반올림(최소 1분).
- 맛집 = `contenttypeid` `39`(주황 `#ff9f43`), 관광지 = `12`·`14`·`28`·`38`(분홍 `#ff8fa3`). `15`(축제/행사)는 질문에 축제·행사·공연이 있을 때만. 카페 = `cat3` `A05020900`.
- 좌표가 0인 장소(예: `도심속 바다축제`)는 거리 계산·지도에서 제외.
- 화면 모양·색·SVG는 `docs/superpowers/mockups/`의 확정 시안을 따른다. 안티목표: 초록 박스/격자 지도, 일러스트 위 글자 라벨, 한강 위 배·흰 곡선.
- 확인은 PC 브라우저 모바일 보기(localhost:8000). 실기기 https는 범위 밖.
- git: `.superpowers/`, `.claude/`, `.env`는 커밋 금지. 태스크 단위 커밋, 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Ollama가 꺼졌거나 느릴 때** → 채팅은 실패하지 않고 장소 목록과 함께 템플릿 답변("○○ 근처 추천 장소를 지도에 표시했어요: A, B, C")을 준다. (B5 테스트)
2. **OpenSearch가 꺼졌을 때** → `/api/chat`이 503과 한국어 `detail`을 주고, 화면은 오류 말풍선을 띄운다(앱이 멈추지 않음). (B6·F3 테스트)
3. **첫 질문이 "거기 근처 카페 있어?"** (직전 추천 없음) → 지시어 규칙을 건너뛰고 다음 규칙으로 넘어가며 오류가 나지 않는다. (B2 테스트)
4. **전화번호·사진이 없는 장소** → 카드에 "전화번호 정보 없음"과 이모지 타일. (F3 테스트)
5. **GPS 권한 거부/미지원** → "위치 권한이 없어서 현재 위치를 쓸 수 없어요" 말풍선, 다음 요청은 `location: null`. (F4 테스트)

---

## 파일 구조

```
.env.example                 # 필수/선택 환경변수 목록 (값 없음)
requirements.txt
pytest.ini                   # testpaths=tests, markers: integration
TEAM-STATUS.md               # 팀 운영 단일 진실 소스 (가이드 6장 ①~⑧)
data/seoul_tour.json         # 원본 복사본 (수정 금지)
data/seoul_tour_enriched.json  # B1 스크립트 산출물 {contentid: {"tel": ...}}
scripts/enrich_tel.py        # 전화번호 보강 (1회성, 이어하기 가능)
scripts/build_index.py       # seoul-tour-v2 인덱스 생성
scripts/init_db.sql          # chat_message 테이블
app/config.py                # Settings 로딩·검증
app/schemas.py               # API 요청/응답 모델 (계약)
app/catalog.py               # Place, 카탈로그 로딩, 분류 한글명
app/geo.py                   # 거리·도보시간·인기지역 이름표·구 목록
app/center.py                # 기준점 결정
app/intent.py                # 의도·일상대화 판별
app/search.py                # 임베딩 + OpenSearch kNN 후보 검색
app/recommend.py             # 후보 → 최종 추천 (반경/가까운 곳 대체)
app/llm.py                   # 프롬프트 생성 + Ollama 호출
app/history.py               # chat_message 저장/조회 (MySQL / 메모리)
app/chat.py                  # ChatService: 한 턴 처리
app/main.py                  # create_app(deps), 라우트, static 마운트
static/index.html
static/css/app.css
static/js/api.js             # fetch 래퍼
static/js/landmarks.js       # 6대 랜드마크 좌표 + SVG 함수 (시안에서 이식)
static/js/map.js             # 좌표 투영 + 일러스트 지도 렌더
static/js/app.js             # 화면 상태·이벤트
tests/conftest.py            # 가짜 의존성(Fake*) + 작은 카탈로그 픽스처
tests/test_*.py
tests/js/*.test.mjs
```

**의존성 순서:** T0 → (B1, B2, B4, F1, F2 병렬) → B3 → B5 → B6 → (Q1, F3) → F4 → Q2.
팀원3은 **B6 완료 후** 시작한다(공유 태스크 리스트에 의존성으로 건다).

---

### Task T0 [리드]: 뼈대·계약·팀 문서

**Files:**
- Create: `requirements.txt`, `.env.example`, `pytest.ini`, `app/__init__.py`, `app/config.py`, `app/schemas.py`, `TEAM-STATUS.md`, `data/seoul_tour.json`(원본 복사), `tests/test_config.py`

**Interfaces:**
- Produces:
  - `Settings` (dataclass, frozen): `tour_api_key, opensearch_host="localhost", opensearch_port=9200, opensearch_user, opensearch_password, opensearch_index="seoul-tour-v2", ollama_url="http://localhost:11434", ollama_model="gemma4:e4b", embed_model="jhgan/ko-sroberta-multitask", mysql_host="localhost", mysql_port=3306, mysql_user, mysql_password, mysql_db="seoul_tour"`
  - `load_settings(env: Mapping[str,str] | None = None, required: Sequence[str] = REQUIRED_SERVER) -> Settings` — 빈 필수값이 있으면 `ConfigError(f"…: {', '.join(missing)}")`. `REQUIRED_SERVER = ("OPENSEARCH_USER","OPENSEARCH_PASSWORD","MYSQL_USER","MYSQL_PASSWORD")`, `enrich_tel.py`는 `("TOUR_API_KEY",)`.
  - `app/schemas.py` (spec §5.4 그대로):
    - `Location(lat: float, lng: float)`
    - `ChatRequest(session_id: str | None, message: str [strip 후 1~500자], location: Location | None, selected_place_id: str | None)`
    - `PlaceOut(id, title, kind: Literal["food","tour"], category, addr, tel, lat, lng, image, distance_m: int | None, walk_min: int | None)`
    - `CenterOut(lat, lng, label: str, source: Literal["gps","place","area","gu","history"])`
    - `ChatResponse(session_id: str, answer: str, center: CenterOut | None, places: list[PlaceOut])`
    - `HistoryMessage(role: Literal["user","assistant"], message: str, center: CenterOut | None, places: list[PlaceOut], created_at: str)`, `HistoryResponse(session_id, messages: list[HistoryMessage])`

- [ ] **Step 1: 테스트 작성** — `tests/test_config.py`
  - `test_missing_required_lists_all_names`: `load_settings({"OPENSEARCH_USER":""})` → `ConfigError`, 메시지에 `OPENSEARCH_PASSWORD`, `MYSQL_USER`, `MYSQL_PASSWORD`가 모두 포함.
  - `test_defaults`: 필수값만 채우면 `s.opensearch_index == "seoul-tour-v2"`, `s.ollama_model == "gemma4:e4b"`, `s.mysql_db == "seoul_tour"`.
  - `test_chat_request_rejects_blank`: `ChatRequest(message="   ")` → `ValidationError`; 501자 → `ValidationError`.
- [ ] **Step 2:** `pytest tests/test_config.py -v` → FAIL(모듈 없음)
- [ ] **Step 3:** `config.py`, `schemas.py` 구현. `load_settings(None)`은 `python-dotenv`로 `.env`를 읽은 뒤 `os.environ` 사용.
- [ ] **Step 4:** `pytest tests/test_config.py -v` → PASS
- [ ] **Step 5:** `TEAM-STATUS.md` 작성: 가이드 6장 ①~⑧ 섹션, ④ "합의된 인터페이스"에 `app/schemas.py` 초안을 적고 "팀원1·2가 메시지로 확정 후 갱신", ③ 태스크 표(위 의존성 순서). `.env.example`에 Settings의 모든 키(값 비움, 기본값 있는 키는 주석으로 기본값).
- [ ] **Step 6: Commit** — `chore: 프로젝트 뼈대, 설정, API 계약 초안`

---

### Task B1 [팀원1]: 카탈로그 + 전화번호 보강

**Files:**
- Create: `app/catalog.py`, `scripts/enrich_tel.py`, `data/seoul_tour_enriched.json`(실행 산출물), `tests/test_catalog.py`, `tests/test_enrich.py`

**Interfaces:**
- Consumes: `load_settings(required=("TOUR_API_KEY",))`
- Produces:
  - `@dataclass(frozen=True) Place: id, title, content_type, kind ("food"|"tour"|"event"), category, cat3, addr, tel, lat, lng, image, gu`
  - `load_catalog(raw_path="data/seoul_tour.json", enriched_path="data/seoul_tour_enriched.json") -> dict[str, Place]` (enriched 파일이 없으면 tel 빈 값)
  - `has_coords(p: Place) -> bool` (`lat`·`lng` 둘 다 0이 아님)
  - `category_name(item: dict) -> str` — 음식점은 `cat3` 한글명(한식 A05020100, 양식 A05020200, 일식 A05020300, 중식 A05020400, 이색음식점 A05020700, 카페/전통찻집 A05020900), 그 외는 기존 `vectorize.py`의 `cat2_map`, 없으면 `"기타"`.
  - `pick_tel(common: dict, intro: dict) -> str` — `common["tel"]` → intro의 `infocenterfood|infocenter|infocenterculture|infocentershopping|infocenterleports` 순, HTML 태그 제거, 없으면 `""`.
  - `scripts/enrich_tel.py`: `detailCommon2`(필요 시 `detailIntro2`) 호출, 결과 `{contentid: {"tel": str}}`를 **한 건마다** 파일에 저장(중단 후 재실행 시 이미 있는 건 건너뜀). `--limit N` 옵션.
- [ ] **Step 1: 테스트** — `test_catalog.py`: 실제 원본으로 `len(load_catalog(...)) == 574`; `가회동성당`의 `kind=="tour"`, `gu=="종로구"`; 음식점 하나 `kind=="food"`; `has_coords(도심속 바다축제) is False`; enriched 파일에 `{id:{"tel":"02-1"}}`를 넣은 임시 파일로 tel 반영 확인. `test_enrich.py`: `pick_tel({"tel":""},{"infocenterfood":"02-733-9240<br>"}) == "02-733-9240"`, 둘 다 없으면 `""`.
- [ ] **Step 2:** `pytest tests/test_catalog.py tests/test_enrich.py -v` → FAIL
- [ ] **Step 3:** 구현.
- [ ] **Step 4:** 테스트 PASS 확인.
- [ ] **Step 5:** 사용자가 `.env`에 `TOUR_API_KEY`를 넣었는지 확인(없으면 사용자에게 요청하고 B2로 진행). `python scripts/enrich_tel.py --limit 5` → 5건 저장 확인 후 전체 실행. 결과: 전화번호 채워진 건수를 `TEAM-STATUS.md`와 사용자 보고에 적는다.
- [ ] **Step 6: Commit** — `feat: 장소 카탈로그와 전화번호 보강 스크립트` (보강 JSON 포함)

---

### Task B2 [팀원1]: 거리·지역 이름표·기준점 결정

**Files:**
- Create: `app/geo.py`, `app/center.py`, `tests/test_geo.py`, `tests/test_center.py`

**Interfaces:**
- Consumes: `Place`, `has_coords`
- Produces:
  - `haversine_m(lat1, lng1, lat2, lng2) -> float`; `walk_min(distance_m: float) -> int` (= `max(1, round(d/67))`)
  - `AREAS: dict[str, tuple[float,float]]` — 아래 값 그대로: 성수 (37.5446,127.0559), 홍대 (37.5563,126.9236), 연남동 (37.5660,126.9250), 합정 (37.5495,126.9139), 망원 (37.5560,126.9104), 신촌 (37.5551,126.9368), 강남역 (37.4979,127.0276), 신사 (37.5163,127.0203), 가로수길 (37.5205,127.0230), 압구정 (37.5270,127.0284), 코엑스 (37.5116,127.0595), 삼성 (37.5088,127.0631), 잠실 (37.5133,127.1000), 건대 (37.5404,127.0692), 여의도 (37.5219,126.9245), 용산 (37.5298,126.9648), 이태원 (37.5345,126.9946), 한남 (37.5340,127.0026), 서울역 (37.5547,126.9707), 시청 (37.5657,126.9769), 명동 (37.5636,126.9827), 을지로 (37.5660,126.9910), 종로3가 (37.5704,126.9921), 익선동 (37.5743,126.9897), 인사동 (37.5740,126.9850), 북촌 (37.5826,126.9830), 삼청동 (37.5850,126.9817), 서촌 (37.5800,126.9700), 대학로 (37.5822,127.0019), 혜화 (37.5822,127.0019), 동대문 (37.5712,127.0095), 남산 (37.5512,126.9882)
  - `SEOUL_GU: list[str]` (기존 `main.py`의 25개)
  - `DEMONSTRATIVES = ("거기 근처","그 근처","그 주변","거기","그곳","저기")`
  - `@dataclass Center: lat, lng, label, source` (`source` ∈ `gps|place|area|gu|history`, 지시어로 고른 장소는 `place`)
  - `resolve_center(message: str, location: Location | None, selected_place_id: str | None, last_places: list[PlaceOut], last_center: CenterOut | None, catalog: dict[str, Place]) -> Center | None`
- 규칙(spec §5.2 순서): ① `location` → `("현재 위치","gps")` ② 지시어가 있고 질문에 카탈로그 장소명·지역명·구명이 없으면: `selected_place_id`가 `last_places`에 있으면 그 장소, 아니면 `last_places[0]`, `last_places`가 비면 다음 규칙으로 ③ 카탈로그 제목이 질문에 포함 → 정확히 같은 제목 > 가장 긴 제목 > (동률) 가장 짧은 id 순, 좌표 없는 장소 제외 ④ `AREAS` 키 포함 → 그 좌표 ⑤ `addr` 의 동 이름(괄호 안 `(○○동)` 또는 주소 토큰 중 `동`으로 끝나는 것)과 일치 → 그 동 장소 평균 좌표, `source="area"` ⑥ `SEOUL_GU` 포함 → 그 구 장소 평균 좌표 ⑦ `last_center` → `source="history"` ⑧ `None`.
- [ ] **Step 1: 테스트** — `test_geo.py`: 광화문(37.5761,126.9768)–개성만두 궁(37.5743,126.9854) 거리 780±40m; `walk_min(780)==12`; `walk_min(10)==1`. `test_center.py`(작은 카탈로그 픽스처: 광화문, 광화문광장, 개성만두 궁, 가회동성당, 성수 근처 카페 1곳):
  - `test_gps_wins`: location 있고 질문에 "광화문" → `source=="gps"`
  - `test_demonstrative_uses_selected`: "거기 근처 카페 있어?", selected=개성만두 궁 id, last_places=[세종클럽, 개성만두 궁] → label `개성만두 궁`
  - `test_demonstrative_uses_first_when_none_selected` → `last_places[0]`
  - `test_demonstrative_without_history_falls_through`: last_places=[], last_center=None, "거기 근처 카페 있어?" → `None` (오류 없음)  ← Review Focus 3
  - `test_place_title_longest_match`: "광화문광장 근처 맛집" → `광화문광장`
  - `test_area_name`: "성수 카페" → (37.5446,127.0559), `source=="area"`
  - `test_gu_name`: "종로구 관광지" → `source=="gu"`
  - `test_history_fallback`: "맛집 더 알려줘", last_center 있음 → `source=="history"`
- [ ] **Step 2:** FAIL 확인 → **Step 3:** 구현 → **Step 4:** `pytest tests/test_geo.py tests/test_center.py -v` PASS
- [ ] **Step 5: Commit** — `feat: 거리 계산과 기준점 결정 규칙`

---

### Task B3 [팀원1]: 검색 인덱스 + 후보 검색

**Files:**
- Create: `scripts/build_index.py`, `app/search.py`, `tests/test_search.py`

**Interfaces:**
- Consumes: `Settings`, `load_catalog`, `Place`
- Produces:
  - `class Embedder(Protocol): def encode(self, text: str) -> list[float]` / `SentenceEmbedder(model_name)`
  - `class Searcher(Protocol): def knn(self, vector: list[float], content_types: set[str], cat3: str | None, k: int) -> list[tuple[str, float]]` (`(place_id, score)`, 점수 내림차순) / `OpenSearchSearcher(settings)` / 연결 실패 시 `SearchUnavailable` 예외
  - `build_index.py`: 인덱스 `settings.opensearch_index`가 있으면 **그 인덱스만** 지우고 재생성(`seoul-tour`는 절대 건드리지 않음 — 이름이 `seoul-tour`면 거부). 문서: `id, title, content_type, kind, cat3, category, addr, tel, location(geo_point), image, content, vector(knn_vector 768, hnsw, cosinesimil, lucene)`. `content`는 기존 `vectorize.py` 문장 + 분류(음식점은 cat3 한글명).
  - kNN 필터: `content_type` terms + 선택적 `cat3` term (lucene 엔진 efficient filter).
- [ ] **Step 1: 테스트** — `test_search.py`: `build_query(vector, {"39"}, "A05020900", 50)`이 만드는 dict에 `knn.vector.k == 50`, filter 안에 `{"terms":{"content_type":["39"]}}`와 `{"term":{"cat3":"A05020900"}}`가 있음; `cat3=None`이면 term 없음; `index_name_guard("seoul-tour")` → `ValueError`.
- [ ] **Step 2–4:** FAIL → 구현(`build_query`, `index_name_guard`는 `app/search.py`의 순수 함수) → PASS
- [ ] **Step 5:** 사용자가 `.env`에 OpenSearch 계정을 넣었는지 확인 후 `python scripts/build_index.py` → "574건 색인"(좌표 없는 1건도 색인은 함). `curl -sk -u $USER:$PW https://localhost:9200/seoul-tour-v2/_count` → `{"count":574…}`.
- [ ] **Step 6: Commit** — `feat: seoul-tour-v2 인덱스와 kNN 후보 검색`

---

### Task B4 [팀원1]: 대화 기록 저장소

**Files:**
- Create: `scripts/init_db.sql`, `app/history.py`, `tests/test_history.py`

**Interfaces:**
- Produces:
  - `chat_message(id BIGINT AUTO_INCREMENT PK, session_id VARCHAR(64) INDEX, role VARCHAR(16), message TEXT, center_json JSON NULL, places_json JSON NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)` — `CREATE TABLE IF NOT EXISTS`, utf8mb4
  - `class HistoryRepo(Protocol)`: `save(session_id, role, message, center: CenterOut | None = None, places: list[PlaceOut] | None = None) -> None` (저장 후 세션당 최근 100개 초과분 삭제), `list(session_id) -> list[HistoryMessage]` (오래된 순), `last_assistant(session_id) -> HistoryMessage | None` (마지막 **장소가 있는** 봇 메시지), `delete_expired(days=30) -> int`
  - `MySQLHistoryRepo(settings)`, `InMemoryHistoryRepo()` (테스트·개발용, 같은 동작)
- [ ] **Step 1: 테스트** — `test_history.py`(InMemory로 공통 계약 테스트, 같은 테스트를 `@pytest.mark.integration`으로 MySQL에도 적용하는 파라미터화): 101개 저장 후 `len(list)==100`이고 첫 메시지가 2번째 것; `last_assistant`는 장소 없는 일상 답변을 건너뜀; center·places 왕복 후 동일.
- [ ] **Step 2–4:** FAIL → 구현 → `pytest tests/test_history.py -v -m "not integration"` PASS
- [ ] **Step 5:** `mysql -u … seoul_tour < scripts/init_db.sql` 실행 후 `pytest tests/test_history.py -m integration -v` PASS (DB 없으면 `CREATE DATABASE IF NOT EXISTS seoul_tour` 포함)
- [ ] **Step 6: Commit** — `feat: chat_message 대화 기록 저장소`

---

### Task B5 [팀원1]: 의도 판별 + 추천 + LLM 답변

**Files:**
- Create: `app/intent.py`, `app/recommend.py`, `app/llm.py`, `tests/test_intent.py`, `tests/test_recommend.py`, `tests/test_llm.py`

**Interfaces:**
- Consumes: `Searcher`, `Embedder`, `Place`, `Center`, `haversine_m`, `walk_min`
- Produces:
  - `@dataclass Intent: content_types: set[str], cat3: str | None, casual: bool`
  - `detect_intent(message) -> Intent` — 키워드: 맛집 `맛집,식당,음식,먹,밥,점심,저녁` / 카페 `카페,커피,디저트,찻집` (→ types `{"39"}`, cat3 `A05020900`) / 관광 `관광,명소,볼거리,가볼,구경,놀거리,데이트` / 축제 `축제,행사,공연`. 맛집만 → `{"39"}`, 관광만 → `{"12","14","28","38"}`, 둘 다·없음 → 다섯 개 모두, 축제 → `"15"` 추가. 일상 대화는 기존 `main.py`의 `casual_keywords`가 있고 위 키워드가 하나도 없을 때만 `casual=True`.
  - `CASUAL_RESPONSES` (기존 `main.py` 12개 그대로)
  - `@dataclass Recommendation: places: list[PlaceOut], fallback_note: str | None`
  - `recommend(message, intent, center, searcher, embedder, catalog, k=5, radius_m=1500) -> Recommendation`
    - `knn(vector, types, cat3, k=100)` 후보 → 카탈로그에서 Place로 바꿈(좌표 없는 것 제외).
    - center 없음: 점수 상위 5개, `distance_m/walk_min=None`.
    - center 있음: 반경 안 후보 중 점수 상위 5개 → 거리순 정렬. 반경 안이 0개면 **카탈로그 전체**에서 같은 types/cat3 조건으로 가장 가까운 3곳, `fallback_note = f"가장 가까운 곳은 {d/1000:.1f}km 떨어진 {title}예요"`.
  - `build_prompt(message, history_texts: list[str], places: list[PlaceOut], center_label: str | None, fallback_note: str | None) -> str` — 기존 `main.py` 규칙(한국어, 2문장 이내, 주어진 장소 정보만) + 장소마다 `이름/분류/주소/도보 N분`, 최근 6개 대화, fallback_note가 있으면 "반드시 언급" 지시.
  - `class LLM(Protocol): def generate(self, prompt: str) -> str` / `OllamaLLM(settings, timeout=30)` (temperature 0.3, top_p 0.9) / 실패 시 `LLMUnavailable`
  - `template_answer(places, center_label) -> str` — `f"{center_label} 근처 추천 장소를 지도에 표시했어요: A, B, C"` (center 없으면 `"추천 장소를 지도에 표시했어요: …"`, 장소 0개면 `"조건에 맞는 장소를 찾지 못했어요. 다른 지역이나 종류로 물어봐 주세요."`)
- [ ] **Step 1: 테스트**
  - `test_intent.py`: "광화문 근처 맛집" → `{"39"}`; "거기 근처 카페 있어?" → `{"39"}`, cat3 `A05020900`; "종로 관광지" → 관광 4종; "이번 주 축제" → `"15"` 포함; "고마워!" → casual; "고마워, 근처 맛집도 알려줘" → casual 아님.
  - `test_recommend.py`(FakeSearcher·FakeEmbedder, conftest): 반경 안 후보 6개 → 5개, 거리 오름차순, `walk_min` 채움; 반경 안 0개 → 3개 + `fallback_note`에 "km 떨어진" 포함; 좌표 0 장소는 결과에 없음; center 없음 → distance None.
  - `test_llm.py`: `build_prompt`에 장소 이름·"2문장"·fallback_note 포함; `template_answer` 세 경우 문구 정확히 위와 같음.
- [ ] **Step 2–4:** FAIL → 구현 → `pytest tests/test_intent.py tests/test_recommend.py tests/test_llm.py -v` PASS
- [ ] **Step 5: Commit** — `feat: 의도 판별, 추천, LLM 프롬프트`

---

### Task B6 [팀원1]: ChatService + FastAPI 앱

**Files:**
- Create: `app/chat.py`, `app/main.py`, `tests/conftest.py`(B5에서 만든 Fake 확장), `tests/test_chat_service.py`

**Interfaces:**
- Consumes: 위 모든 Produces
- Produces:
  - `@dataclass Deps: catalog, embedder, searcher, llm, history`
  - `ChatService(deps).handle(req: ChatRequest) -> ChatResponse`:
    1. `session_id = req.session_id or uuid4()`
    2. intent.casual → 무작위 `CASUAL_RESPONSES`, `center=None, places=[]`, user·assistant 저장, 반환(지도 안 바뀜)
    3. `last = history.last_assistant(sid)` → `resolve_center(..., last.places, last.center, …)`
    4. `recommend(...)` → `build_prompt(...)` → `llm.generate`; `LLMUnavailable`이면 `template_answer` ← Review Focus 1
    5. 사용자 메시지 저장, 봇 메시지를 center·places와 함께 저장, 반환
    - `SearchUnavailable`은 그대로 올림
  - `create_app(deps: Deps | None = None) -> FastAPI` — `None`이면 `load_settings()`로 실제 의존성 생성. 라우트: `POST /api/chat`(SearchUnavailable → 503 `{"detail":"검색 서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요."}`), `GET /api/history/{session_id}` → `HistoryResponse`, `GET /api/health` → `{"opensearch":bool,"ollama":bool,"mysql":bool}`. `static/`을 `/`에 마운트(`index.html`). 시작 시 `delete_expired(30)` 1회.
  - 실행: `uvicorn app.main:create_app --factory --port 8000` (모듈 레벨에서 `create_app()`을 호출하지 않는다 — 테스트 import 시 실제 서비스에 붙지 않도록)
- [ ] **Step 1: 테스트** — `test_chat_service.py`: "광화문 근처 맛집 추천해줘" → places 모두 `kind=="food"`, center label `광화문`; 이어서 `selected_place_id=개성만두 궁`으로 "거기 근처 카페 있어?" → center label `개성만두 궁`, places 모두 cat3 카페 계열; FakeLLM이 `LLMUnavailable` 던지면 answer가 `template_answer` 결과이고 places 그대로; "고마워!" → places `[]`, center None, 이후 `last_assistant`는 여전히 이전 추천.
- [ ] **Step 2–4:** FAIL → 구현 → PASS
- [ ] **Step 5:** 실제 실행: `uvicorn app.main:create_app --factory --port 8000` 후 `curl -s localhost:8000/api/health` → 세 값 true, `curl -s -X POST localhost:8000/api/chat -H "Content-Type: application/json" -d "{\"message\":\"광화문 근처 맛집 추천해줘\"}"` → places 3~5개. 결과를 팀원2·3에게 SendMessage, `TEAM-STATUS.md` ④에 **확정 계약** 기록, 사용자 보고.
- [ ] **Step 6: Commit** — `feat: 채팅 서비스와 FastAPI 앱`

---

### Task F1 [팀원2]: 화면 뼈대 + 첫 화면(S2a)

**Files:**
- Create: `static/index.html`, `static/css/app.css`, `static/js/landmarks.js`, `static/js/app.js`(초기 화면만)

**Interfaces:**
- Produces:
  - `landmarks.js`: `export const LANDMARKS = [{id, name, lat, lng, draw(x, y, k, s) -> string(SVG)}]` — 좌표: 경복궁 (37.5796,126.9770), 숭례문 (37.5600,126.9753), 남산서울타워 (37.5512,126.9882), DDP (37.5665,127.0092), 63빌딩 (37.5198,126.9402), 롯데월드타워 (37.5126,127.1025). `draw`는 `docs/superpowers/mockups/first-screen-s2a.html`의 `palace/gate/namsan/ddp/b63/lotte` 이식. `export function defs(s) -> string`.
  - `export function renderHome(el)` — S2a 일러스트(배지 링, 굵은 한강, 물빛 짧은 선, **배·흰 곡선·글자 라벨 없음**), 인사말 "안녕하세요! 👋" / "서울 어디로 떠나볼까요?", 칩 `📍 내 주변 맛집`, `🏯 종로 관광지`, `☕ 성수 카페`, 입력창(+📍 버튼). 칩을 누르면 해당 문구로 전송(`📍 내 주변 맛집`은 GPS 요청 후 "내 주변 맛집" 전송).
- [ ] **Step 1:** 구조: 휴대폰 폭 기준 `max-width: 430px` 가운데 정렬, 색 토큰 `--pink:#ff8fa3 --orange:#ff9f43 --cream:#fdf6e3 --bg-top:#ffe9f0 --bg-bottom:#fff6e8`.
- [ ] **Step 2:** `python -m http.server 8001 -d static` 로 열어서 Chrome 개발자도구 모바일 보기(iPhone 14 Pro, 393px) 스크린샷 → 시안 `first-screen-s2a.html`과 나란히 비교(배치·색·배지 6개). 헤드리스 확인 예: `chrome --headless=new --window-size=393,852 --screenshot=… http://localhost:8001`
- [ ] **Step 3: Commit** — `feat: 화면 뼈대와 S2a 첫 화면`

---

### Task F2 [팀원2]: 일러스트 지도 모듈

**Files:**
- Create: `static/js/map.js`, `tests/js/map.test.mjs`

**Interfaces:**
- Consumes: `LANDMARKS`, `defs`
- Produces:
  - `export function computeBounds(points: {lat,lng}[], {minSpanM=600, pad=0.15}={}) -> {minLat,maxLat,minLng,maxLng}` — 좌표 0 제외, 범위가 600m보다 작으면 중심 기준으로 넓힘, 가로세로 비율은 지도 박스(4:3.5)에 맞춤.
  - `export function project(lat, lng, bounds, width, height) -> {x, y}` — 경도 축에 `cos(중심위도)` 보정, 위도는 위쪽이 북쪽.
  - `export function mulberry32(seed) -> () => number`; 시드 = `Math.round(center.lat*1e4) ^ Math.round(center.lng*1e4)`
  - `export function renderMap(el, {center, places, me, selectedId, onPinClick})` — 시안 `result-screen.html`의 스타일: 크림 바탕, 숲 덩어리, 점선 흰 길, 파스텔 블록(시드로 배치, 핀과 겹치지 않게), 한강은 bounds가 위도 37.505~37.545에 걸칠 때만 아래쪽 띠로, bounds 안의 `LANDMARKS`는 미니 일러스트, 물방울 핀(맛집 주황/관광 분홍)+이모지+흰 이름표, 선택 핀 1.25배, 내 위치 파란 점, 범례 "🧡 맛집 · 🩷 관광지 · 🔵 내 위치". **격자/초록 박스 금지.**
  - 핀 이모지: 카페 ☕, 그 외 음식점 🍽️, 관광지 🏯/🌳 등은 `category`로 고르되 기본값 📍.
- [ ] **Step 1: 테스트** — `map.test.mjs`(`node --test "tests/js/*.test.mjs"`): 북쪽 장소의 `y`가 더 작음; 동쪽 장소의 `x`가 더 큼; 모든 점이 `0..width`, `0..height` 안; 한 점만 있을 때 bounds 폭 ≥ 600m; `(0,0)` 점은 bounds에 영향 없음; 같은 시드는 같은 수열.
- [ ] **Step 2–4:** FAIL → 구현 → `node --test "tests/js/*.test.mjs"` PASS
- [ ] **Step 5:** 임시 HTML로 광화문 예시(시안과 같은 4곳)를 그려 스크린샷 → 시안 `result-screen.html`과 비교.
- [ ] **Step 6: Commit** — `feat: 일러스트 지도 렌더링`

---

### Task F3 [팀원2]: 대화·결과 화면·카드·접힘(B안) — B6 이후 연동

**Files:**
- Create: `static/js/api.js`, `tests/js/view.test.mjs`
- Modify: `static/js/app.js`, `static/css/app.css`

**Interfaces:**
- Consumes: B6 확정 계약(`TEAM-STATUS.md` ④), `renderMap`, `renderHome`
- Produces:
  - `api.js`: `sendChat({sessionId, message, location, selectedPlaceId}) -> Promise<ChatResponse>`(503·네트워크 오류 시 `Error(detail)`), `fetchHistory(sessionId) -> Promise<HistoryResponse>`
  - 상태: `{sessionId(localStorage "stc.sessionId"), center, places, selectedId, mapOpen: true, pendingLocation}`
  - `export function cardHtml(place) -> string` — 사진 없으면 이모지 타일, tel 비면 `전화번호 정보 없음`, 도보 `🚶 {center.label}에서 약 N분`(walk_min 없으면 줄 생략)
  - `export function chipLabel(place) -> string` — `"{emoji} {title} {walk_min}분"`(walk_min 없으면 분 생략)
- 동작: 첫 전송 시 홈 → 결과 화면 전환; 응답 places가 비어 있지 않으면 **핀·칩·요약 바 교체**(누적 안 함), 비어 있으면 지도 유지; 핀/칩 클릭 → 카드 열기 + `selectedId` 저장(다음 요청 `selected_place_id`); "▾ 지도 접기" ⇄ "▴ 지도 펼치기"; 접힘 = 미니 썸네일 + "**{label} 근처** · 추천 N곳" + "지도 보기 ▾" + 가로 스크롤 칩(맛집 주황 테두리, 관광 분홍 테두리), 칩 클릭 시 지도 안 펼치고 카드; 전송 중 "…" 말풍선; 오류 시 오류 말풍선(`Error.message`); 새로고침 시 `fetchHistory`로 말풍선 + 마지막 장소 있는 봇 메시지의 지도 복원.
- [ ] **Step 1: 테스트** — `view.test.mjs`: `cardHtml({tel:"",image:"",…})`에 "전화번호 정보 없음" 포함 ← Review Focus 4; `chipLabel({title:"광화문 세종클럽",kind:"food",walk_min:3,…})` → "🍽️ 광화문 세종클럽 3분".
- [ ] **Step 2–4:** FAIL → 구현 → `node --test "tests/js/*.test.mjs"` PASS
- [ ] **Step 5:** 서버(`uvicorn app.main:create_app --factory --port 8000`)로 모바일 보기 확인: "광화문 근처 맛집 추천해줘" → 핀 → 카드 → "거기 근처 카페 있어?" → 핀 교체 → 접기 → 칩 클릭 → 카드 → 새로고침 후 복원. 각 단계 스크린샷을 시안 3개와 비교. OpenSearch를 잠시 끄거나 잘못된 포트로 띄워 오류 말풍선 확인 ← Review Focus 2.
- [ ] **Step 6: Commit** — `feat: 결과 화면, 정보 카드, 지도 접힘(B안)`

---

### Task F4 [팀원2]: GPS 위치

**Files:**
- Modify: `static/js/app.js`
- Create: `tests/js/geo.test.mjs`

**Interfaces:**
- Produces: `export function requestLocation(geo = navigator.geolocation) -> Promise<{lat,lng} | {error: string}>` — 미지원 → `{error:"이 브라우저에서는 위치를 쓸 수 없어요"}`, 거부 → `{error:"위치 권한이 없어서 현재 위치를 쓸 수 없어요"}`, 시간 초과 8초.
- 📍 누르면 위치를 받아 `pendingLocation`에 두고 입력창에 "📍 현재 위치 사용 중" 표시, 다음 전송에 `location` 포함 후 비움. 오류면 봇 말풍선으로 오류 문구, `location: null`.
- [ ] **Step 1: 테스트** — 가짜 geo 객체로: 성공 → 좌표; `PERMISSION_DENIED`(code 1) → 위 거부 문구 ← Review Focus 5; geo 없음 → 미지원 문구.
- [ ] **Step 2–4:** FAIL → 구현 → PASS
- [ ] **Step 5:** Chrome 개발자도구 Sensors에서 위치를 광화문(37.5759,126.9769)으로 설정 → "내 주변 맛집" → 파란 점과 center `현재 위치` 확인; 위치 "차단"으로 바꿔 오류 말풍선 확인.
- [ ] **Step 6: Commit** — `feat: GPS 현재 위치 추천`

---

### Task Q1 [팀원3]: API 테스트 스위트 — **B6 완료 후 시작**

**Files:**
- Create: `tests/api/test_chat_api.py`, `tests/api/test_history_api.py`, `tests/api/test_health_api.py`

**Interfaces:**
- Consumes: `create_app(Deps)`, conftest의 Fake*, `TEAM-STATUS.md` ④ 확정 계약

- [ ] **Step 1: 테스트 작성** (`fastapi.testclient.TestClient(create_app(fake_deps))`)
  - 계약: 응답 JSON 키가 정확히 `session_id, answer, center, places`; 각 place 키가 `PlaceOut` 필드와 같음; `kind ∈ {"food","tour"}`
  - **모든 places의 id가 카탈로그에 존재** (지어낸 장소 없음)
  - 빈 메시지/공백/501자 → 422
  - `session_id` 없이 보내면 새 UUID, 같은 id로 두 번째 요청 시 history 4개
  - "거기 근처 카페 있어?" 시나리오(selected_place_id 반영) — B6 테스트와 같은 입력을 HTTP로
  - FakeSearcher가 `SearchUnavailable` → 503, `detail` 한국어 문구 정확히
  - FakeLLM 실패 → 200, answer = `template_answer` 문구
  - `/api/history/{id}`: center·places 왕복; 없는 세션 → `messages: []`
  - `/api/health`: 각 의존성 상태 bool
- [ ] **Step 2:** `pytest tests/api -v` → 실패하는 테스트가 있으면 **팀원1에게 SendMessage**(재현 입력·기대·실제), 고쳐질 때까지 반복. 테스트 쪽 오해면 테스트 수정.
- [ ] **Step 3:** 전체 `pytest -m "not integration" -v` PASS 결과를 사용자에게 보고.
- [ ] **Step 4: Commit** — `test: API 계약·시나리오 테스트`

---

### Task Q2 [팀원3]: 통합·화면 시나리오 점검 — F3·F4 완료 후

**Files:**
- Create: `tests/integration/test_live_chat.py` (`@pytest.mark.integration`), `docs/manual-qa.md`

- [ ] **Step 1:** 실서비스 통합 테스트(`create_app()` 실제 의존성): "광화문 근처 맛집 추천해줘" → places 3~5, 모두 `kind=="food"`, 모두 기준점 1500m 이내 또는 fallback 문구 포함; "성수 카페" → center `source=="area"`; "고마워!" → places `[]`.
- [ ] **Step 2:** `pytest -m integration -v` (OpenSearch·Ollama·MySQL 켜진 상태) → PASS
- [ ] **Step 3:** `docs/manual-qa.md`에 모바일 보기 체크리스트 작성·수행: 첫 화면이 시안과 같음(라벨·배·흰 곡선 없음) / 추천 → 핀 색 / 카드 항목 / "거기 근처" / 핀 교체 / 접힘 B안·칩 → 카드 / 새로고침 복원 / GPS 허용·거부 / 서버 오류 말풍선. 항목별 통과·실패와 스크린샷 경로.
- [ ] **Step 4:** 실패 항목은 담당 팀원에게 SendMessage, 재확인. 최종 결과를 사용자에게 보고.
- [ ] **Step 5: Commit** — `test: 통합 테스트와 수동 QA 체크리스트`

---

## 실행 메모 (리드)

- 시작 전: Claude Code 재시작(Agent Teams 적용), 사용자가 `.env`에 OpenSearch·MySQL 계정과 `TOUR_API_KEY` 입력.
- 리드가 T0 수행 후 공유 태스크 리스트에 B1~B6, F1~F4, Q1~Q2를 의존성과 함께 등록하고 팀원 3명을 띄운다. 각 팀원 프롬프트에 포함: 이 계획 경로, spec 경로, 담당 태스크, worktree 격리 + 태스크 단위 커밋, `TEAM-STATUS.md` 즉시 갱신 규칙(가이드 6장), 인터페이스는 SendMessage로 직접 조율, 태스크 끝날 때마다 사용자 보고.
- 마무리: 리드가 worktree 브랜치들을 main에 합치고 전체 테스트(`pytest -m "not integration"`, `node --test "tests/js/*.test.mjs"`) 후 push.
