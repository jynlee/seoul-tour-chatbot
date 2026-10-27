# 데이터 확장 2단계(반영·재색인) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 합친 3,444곳과 개요를 앱 데이터로 반영하고, 신분류 매핑·지역명 제목 제외·세부 장소 겹침 방지·개요 임베딩을 넣어 `seoul-tour-v3`로 다시 색인한다.

**Architecture:** 데이터 파일은 형식 그대로 내용만 바꾼다(`scripts/apply_merged.py`가 `data/raw/*` → `data/seoul_tour.json`·`data/seoul_tour_enriched.json`). 신분류는 카탈로그를 읽을 때 기존 cat2/cat3 코드로 바꿔서, 분류명·카페 판별·OpenSearch cat3 필터 등 기존 코드가 그대로 동작하게 한다.

**Tech Stack:** Python 3.11, FastAPI, OpenSearch kNN, sentence-transformers(`jhgan/ko-sroberta-multitask`, 최대 128토큰), pytest.

**Spec:** `docs/superpowers/specs/2026-10-27-data-expansion-design.md` (§3.1, §4 순서 2, §5, §6)

## Global Constraints

- `food-materials`·`seoul-tour`·`seoul-tour-v2`는 지우거나 만들지 않는다. 새 인덱스는 `seoul-tour-v3`, 설정 기본값도 v3.
- 서버는 8015만(8000은 리드 전용). 실행할 때 `OPENSEARCH_INDEX=seoul-tour-v3` 환경 변수로(.env는 v2 그대로).
- 추천 점수 규칙은 바꾸지 않는다. 데이터가 늘어 생긴 문제만 최소로 고친다.
- API 응답 형식·화면은 바꾸지 않는다.
- 키 노출·`Co-Authored-By` 금지, main 병합 금지.

## Review Focus

- cat3가 비어 있는 새 카페(신분류 FD050100)가 "카페 추천"에 나와야 함(OpenSearch cat3 필터) → `test_lcls_cafe_gets_cafe_cat3`.
- 지역명과 같은 제목('한강'·'명동')이 질문 속 지역 이름을 가로채지 않음 → `test_area_titled_place_never_matched`.
- 세부 장소 묶기가 멀리 떨어진 같은 앞말 장소(체인 지점)나 '서울 ○○' 같은 흔한 앞말을 묶지 않음 → `test_group_key_*`.
- 쓰기용 인덱스 이름 보호: v2로 `build_index`를 돌리면 거부, 읽기(8000 서버의 v2)는 허용 → `test_write_guard_protects_v2`.
- 다시 돌려도 같은 결과: 상세가 더 받아진 뒤 `apply_merged`를 다시 돌리면 기존 tel·detail을 잃지 않음 → `test_apply_merged_keeps_existing`.

---

### Task 1: 데이터 반영 스크립트

**Files:** Create `scripts/apply_merged.py`, `tests/test_apply_merged.py`; Modify(실행 결과) `data/seoul_tour.json`, `data/seoul_tour_enriched.json`

**Interfaces:** Produces `build_enriched(items: list[dict], old: dict, overview: dict[str, str], detail: dict) -> dict` — `{cid: {"tel"?, "detail"?, "overview"?}}`, 합친 목록에 없는 id는 버림. 기존 tel·detail 우선, 없으면 `data/raw/detail.json`의 detail.

- [ ] 실패 테스트 `test_apply_merged_keeps_existing`, `test_apply_merged_drops_missing_ids` → 구현 → 통과 → 실행 → 커밋

### Task 2: 신분류 → 분류 코드 매핑

**Files:** Modify `app/catalog.py`; Test `tests/test_catalog.py`

**Interfaces:** Produces `effective_codes(item: dict) -> tuple[str, str]` (cat2, cat3). cat3가 있으면 원래 값. 없으면 음식은 `FD` 신분류 → 음식 cat3(FD05·FD030100 → `A05020900` 카페, FD01·FD0304~06 → 한식, FD020100 중식, FD020200 일식, FD020300·FD0302·FD0303 양식, FD020400·FD020500 이색), 그 밖은 신분류 → cat2(NA→자연, HS01·03·04→역사, HS02·VE01→건축/조형물, VE040300 둘레길→자연, VE02·03·05·EX05→휴양, VE04·EX01·02·04·07→체험, EX06→산업, 문화시설 14와 VE06·07·09·12→문화시설, EV01→축제, EV02·03→공연/행사, LS01·AC05·VE10→육상, LS02→수상, LS03→항공, LS04→복합, SH→쇼핑). 매핑은 cat3·신분류가 둘 다 있는 장소의 실제 대응을 보고 정함. `place_from_item`·`category_name`이 이 값을 씀.
- [ ] 실패 테스트 `test_lcls_cafe_gets_cafe_cat3`, `test_lcls_tour_category`, `test_existing_cat_wins` → 구현 → 통과 → 커밋

### Task 3: 지역명과 같은 제목은 이름 찾기에서 제외

**Files:** Modify `app/center.py`; Test `tests/test_center.py`

- `_match_place`는 이미 질문 속 AREAS·구 이름에 포함된 이름을 건너뛴다. 추가로 제목(부르는 이름) 자체가 AREAS 이름·구 이름·구 별칭·`한강`·`서울`과 같으면 아예 후보에서 뺀다(`AREA_LIKE_TITLES`).
- [ ] 실패 테스트 `test_area_titled_place_never_matched`("한강 야경 볼 곳"·"명동 맛집"·"홍대 근처 카페" → None) → 구현 → 통과 → 커밋

### Task 4: 한 장소 안 세부 장소 겹침 방지

**Files:** Modify `app/recommend.py`; Test `tests/test_recommend.py`

**Interfaces:** `group_key(title: str) -> str | None` — 괄호·대괄호 뺀 제목의 첫 단어에서 끝의 '과/와'를 뗀 말(2글자 이상, `서울`·`국립`·`한국` 같은 흔한 앞말 제외). `one_per_group(places: list[Place], meters=500) -> list[Place]` — 앞선 장소와 묶음이 같고 500m 안이면 뺌. `_recommend`의 후보·구 안 목록·채우기 목록에 적용.
- 예: '창덕궁과 후원 [유네스코 세계유산]'·'창덕궁 인정문'·'창덕궁 낙선재' → '창덕궁' 묶음, '반포한강공원'·'반포한강공원 달빛광장' → 한 묶음.
- [ ] 실패 테스트 `test_group_key_palace_parts`, `test_group_key_ignores_common_prefix`, `test_one_per_group_keeps_far_apart`, `test_recommend_no_two_parts_of_same_palace` → 구현 → 통과 → 커밋

### Task 5: 개요 임베딩 + v3 인덱스

**Files:** Modify `app/catalog.py`(Place.overview), `app/search.py`, `app/config.py`, `scripts/build_index.py`; Test `tests/test_search.py`, `tests/test_config.py`

- `Place.overview: str = ""`(비교 제외), `load_catalog`가 enriched `overview`를 채움.
- `build_document_text`: 기존 문장 뒤에 개요 앞 `OVERVIEW_CHARS = 150`자(기존 문장 약 32토큰 + 개요 ≈ 128토큰 한도).
- `index_name_guard(name, write=False)`: 읽기는 `seoul-tour`·`food-materials` 거부, 쓰기(`build_index`)는 `seoul-tour-v2`도 거부. 설정 기본값 `seoul-tour-v3`.
- [ ] 실패 테스트 `test_document_text_includes_overview_cut`, `test_write_guard_protects_v2`, `test_default_index_v3` → 구현 → 통과 → `OPENSEARCH_INDEX=seoul-tour-v3 python scripts/build_index.py` → 커밋

### Task 6: 통합 테스트·기대값 정리와 실서버 확인

- [ ] `pytest -m "not integration"`, `node --test "tests/js/*.test.mjs"`, `OPENSEARCH_INDEX=seoul-tour-v3 pytest -m integration` — 데이터 때문에 깨진 기대값만 고치고 이유를 커밋 메시지·TEAM-STATUS에 기록.
- [ ] 8015 서버(v3)로 설계 §6 질문 + 기존 맛집·카페·멀티턴 + 석파정 별칭·QA-9 확인, 답변 원문 기록. 테스트 세션은 지움.
- [ ] TEAM-STATUS ⑦⑧ 갱신, 커밋·push, 리드 보고(추천 대상 수 = 좌표 있는 곳).
