# 데이터 확장 1단계(목록 받기·분포 보고) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 관광공사 `areaBasedList2`로 서울 장소 목록(종류 12·14·15·28·38·39)을 받아 중간 파일에 저장하고, 쇼핑 거르기·체인·중복·짧은 제목 분포를 뽑아 리드에게 보고한다.

**Architecture:** `scripts/fetch_list.py`가 종류별로 페이지를 넘겨 받으며 한 페이지마다 `data/raw/seoul_list.json`에 저장(이어 받기). `scripts/analyze_list.py`는 API 없이 그 파일과 기존 `data/seoul_tour.json`을 읽어 보고용 숫자를 출력한다. 호출·저장 도구는 `scripts/enrich_tel.py`의 `save_json`·`_scrub`·`QuotaExceeded`를 재사용.

**Tech Stack:** Python 3.11, requests, pytest (가짜 응답은 monkeypatch).

**Spec:** `docs/superpowers/specs/2026-10-27-data-expansion-design.md` (§3, §4 "순서" 1단계, §5)

## Global Constraints

- `data/seoul_tour.json`·`data/seoul_tour_enriched.json`·`app/` 는 바꾸지 않는다. 새 스크립트·테스트·`data/raw/` 중간 파일만.
- 목록 조회: `areaBasedList2`, `lDongRegnCd=11`, `contentTypeId` ∈ {12,14,15,28,38,39}. 숙박 32 제외. `areaCode`는 쓰지 않는다.
- `TOUR_API_KEY`는 `.env`에서만 읽고, 커밋·로그·저장 파일에 남기지 않는다(오류 메시지는 `_scrub`).
- OpenSearch는 이 단계에서 쓰지 않는다.
- 커밋 메시지에 `Co-Authored-By`·생성 문구를 넣지 않는다.

## Review Focus

- 한도 초과가 페이지 중간에 나면: 그 페이지는 저장하지 않고 멈춤, 다시 실행하면 그 페이지부터 → 테스트 `test_quota_stops_and_resumes`.
- 결과가 1건뿐인 페이지(`item`이 dict)·빈 페이지(`items`가 `""`) → `test_parse_page_single_and_empty`.
- 받는 도중 전체 수(totalCount)가 바뀌어 마지막 페이지가 비면 그 종류를 끝난 것으로 처리 → `test_fetch_type_until_empty_or_total`.
- 저장 파일에 키 문자열이 들어가지 않는다 → `test_saved_file_has_no_key`.
- 지점명 떼기에서 '시장'·'백화점' 같은 이름이 체인으로 잘못 묶이지 않음 → `test_chain_base`.

---

### Task 1: 목록 받기 스크립트

**Files:**
- Create: `scripts/fetch_list.py`, `tests/test_fetch_list.py`, `data/raw/seoul_list.json`(실행 결과)

**Interfaces:**
- Consumes: `scripts.enrich_tel.save_json`, `_scrub`, `QuotaExceeded`, `BASE_URL`
- Produces:
  - `CONTENT_TYPES = ("12", "14", "28", "39", "38", "15")`
  - `parse_page(data: dict) -> tuple[list[dict], int]` — (items, totalCount)
  - `fetch_page(api_key, content_type, page, rows) -> tuple[list[dict], int]` — 한도 초과면 `QuotaExceeded`
  - `fetch_all(state: dict, api_key, out: Path, rows=1000, fetch=fetch_page, max_calls=None) -> dict`
  - 상태 파일 형식: `{"types": {"12": {"total": int, "next_page": int, "done": bool}}, "items": {contentid: item}, "calls": {"YYYY-MM-DD": int}}`

- [ ] **Step 1: 실패하는 테스트** — `test_parse_page_single_and_empty`, `test_fetch_type_until_empty_or_total`(가짜 fetch로 2페이지 받으면 done, items 합쳐짐, calls 2), `test_quota_stops_and_resumes`(2페이지째 QuotaExceeded → next_page 2 저장, 다시 돌리면 이어서 done), `test_saved_file_has_no_key`.
- [ ] **Step 2:** `pytest tests/test_fetch_list.py -v` → FAIL(모듈 없음)
- [ ] **Step 3: 구현** — 한 페이지 받을 때마다 `save_json`. `main`은 `load_settings(required=("TOUR_API_KEY",))`, `--rows`, `--out`(기본 `data/raw/seoul_list.json`).
- [ ] **Step 4:** 테스트 PASS, 실제로 `python scripts/fetch_list.py` 실행 → 종류별 수 출력, `grep`로 키 문자열 없음 확인.
- [ ] **Step 5: 커밋** (`feat: 서울 장소 목록 받기 스크립트(areaBasedList2)`)

### Task 2: 분포 분석 스크립트

**Files:**
- Create: `scripts/analyze_list.py`, `tests/test_analyze_list.py`

**Interfaces:**
- Consumes: `data/raw/seoul_list.json`(Task 1 형식), `app.catalog.load_raw_items`, `SEOUL_BOUNDS`
- Produces:
  - `chain_base(title: str) -> str` — 괄호·끝의 '○○점'(지점명) 떼고 공백 제거한 상호. 예: `"스타벅스 명동점" -> "스타벅스"`, `"투썸플레이스(강남역점)" -> "투썸플레이스"`, `"광장시장" -> "광장시장"`
  - `shopping_keep(item: dict) -> str | None` — 남길 이유(`"시장"`·`"백화점"`·`"면세점"`·`"거리"`) 또는 None. cat3(A04010100 5일장, A04010200 상설시장, A04010300 백화점, A04010400 면세점) + 제목에 거리·골목·상가·시장·면세
  - `find_duplicates(items, meters=50) -> list[tuple[dict, dict]]` — 같은 이름(공백 무시)·50m 안·다른 id
  - `short_titles(items, max_len=2) -> list[dict]` — 괄호 뺀 이름 공백 제외 2글자 이하
- [ ] **Step 1: 실패하는 테스트** — `test_chain_base`, `test_shopping_keep`(백화점 cat3 남김, '명동거리' 남김, '다이소 명동점' 뺌), `test_find_duplicates`, `test_short_titles`
- [ ] **Step 2:** FAIL 확인 → **Step 3:** 구현(`main`은 보고용 숫자를 표준 출력) → **Step 4:** PASS, 실제 데이터로 실행
- [ ] **Step 5: 커밋** (`feat: 목록 분포 분석(쇼핑 거르기·체인·중복·짧은 제목)`)

### Task 3: 기록·보고

- [ ] TEAM-STATUS ⑦ 팀원4 로그·⑧ 다음 할 일 추가, 커밋·push(origin feat/data).
- [ ] 리드에게 분석 숫자 보고 후 **멈춤**(개요·상세 받기는 사용자 결정 뒤).
