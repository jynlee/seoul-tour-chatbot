# 화면 시나리오 점검 (Q2)

- 점검일: 2026-10-23 · 점검: 팀원3(QA)
- 대상: `feat/qa` 3fde006 (feat/backend bed8ebc + feat/frontend ea2ea88 병합)
- 환경: 헤드리스 Chrome 155, **iPhone 14 Pro 보기(393x852, DPR 3, 모바일·터치)**, 실서비스(OpenSearch `seoul-tour-v2`, Ollama `gemma4:e4b`, MySQL `chat_message`)
- 자동 실행: `scripts/qa_mobile/run.mjs` (CDP로 화면 조작, 요청 본문 기록, 스크린샷 저장)
- 스크린샷 폴더: `C:\Users\SMT03\AppData\Local\Temp\claude\C--Users-SMT03-SeoulTourChatbot\796dbd34-6ee3-48fe-b2a5-1247492df3b8\scratchpad\shots\` (아래 표의 파일 이름)

## 실행 방법

서버 3개를 띄운다(8000은 사용자용이라 쓰지 않음, 8001은 다른 프로세스가 사용 중).

```bash
uvicorn app.main:create_app --factory --port 8011                              # 정상
OPENSEARCH_PORT=9299 uvicorn app.main:create_app --factory --port 8012         # 검색 서버 꺼짐 → 503
OLLAMA_URL=http://localhost:11999 uvicorn app.main:create_app --factory --port 8013  # LLM 꺼짐 → 템플릿 답변
node scripts/qa_mobile/run.mjs <스크린샷 폴더>
```

끝나면 `<스크린샷 폴더>/results.json`의 `sessions`를 `MySQLHistoryRepo.delete_session()`으로 지운다(점검 중 만든 대화 기록 정리).

## 결과: 24개 항목 모두 통과

| # | 항목 | 결과 | 스크린샷 | 확인한 내용 |
|---|---|---|---|---|
| 1 | 첫 화면이 시안(S2a)과 같음 | ✅ | `01-home.png` (시안 `mock-s2a.png`) | 배지 링·굵은 한강·물빛 선, 글자 라벨·배·흰 곡선 없음(SVG `<text>` 0개), 인사말, 칩 3개(📍 내 주변 맛집 / 🏯 종로 관광지 / ☕ 성수 카페), 가로 스크롤 없음 |
| 2 | 추천 → 핀 색 | ✅ | `02-result-gwanghwamun.png` | "광화문 근처 맛집 추천해줘" → 주황(맛집) 핀 5개 |
| 2b | 첫 요청 형식 | ✅ | — | `session_id:null, location:null, selected_place_id:null` |
| 3 | 카드 항목 | ✅ | `03-card.png` | 이름·분류 태그·📍주소·📞전화·🚶"광화문에서 약 12분"·✕, 선택 핀 강조 |
| 3b | 전화번호 없는 장소 (RF4) | ✅ | `03b-card-no-tel.png` | 금용문 → "전화번호 정보 없음" |
| 3c | 사진 없는 장소 (RF4) | ✅ | `03-card.png` | 이미지 대신 🍽️ 이모지 타일 |
| 4 | "거기 근처" → 핀 교체 | ✅ | `04-demonstrative-cafe.png` | 마지막으로 연 카드(광화문국밥)가 `selected_place_id`로 전송, ☕ 카페 핀 3개로 교체 |
| 4c | 답변이 기준점 이름을 씀 (QA-2) | ✅ | `04-demonstrative-cafe.png` | "광화문국밥 근처에는 감꽃당… 조금 더 멀리 가려면 광장싸롱 1961이나…" |
| 5 | 접힘 B안 | ✅ | `05-folded.png` | "광화문국밥 근처 · 추천 3곳 · 지도 보기 ▾" + 장소 칩(☕ 감꽃당 21분 …) |
| 6 | 칩 → 카드 | ✅ | `06-folded-chip-card.png` | 칩 클릭 → 카드, 칩 눌림 표시 |
| 6b | 요약 바 → 지도 펼침 | ✅ | — | |
| 7 | 일상 대화 → 지도 유지 | ✅ | `07-casual-keeps-map.png` | "고마워!" → 답변만, 핀 그대로 |
| 8 | 새로고침 복원 | ✅ | `08-reload-restored.png` | 말풍선 6개·핀 3개 그대로 복원 |
| 9 | GPS 허용 | ✅ | `09-gps-allowed.png` | 위치 (37.5759, 126.9769) 전송, 파란 점, 맛집 핀 |
| 9b | 📍 버튼 1회 전송 | ✅ | `09b-gps-pending.png` | "📍 현재 위치 사용 중" 표시 → 다음 요청만 `location`, 그 뒤 `null` |
| 10 | GPS 거부 (RF5) | ✅ | `10-gps-denied.png` | "위치 권한이 없어서 현재 위치를 쓸 수 없어요" 말풍선 → `location:null`로 계속, 파란 점 없음 |
| 10b | 거부 상태에서 📍 버튼 | ✅ | — | 오류 말풍선, 입력창은 일반 상태 |
| 10c | 기준점 없을 때 "근처/주변" 안 씀 (QA-2) | ✅ | `10-gps-denied.png` | "…현재 위치(📍)를 알려주시면 더 가까운 곳을 찾아 드릴게요!" |
| 11 | 첫 질문이 "거기 근처 카페 있어?" (RF3) | ✅ | `11-demonstrative-first.png` | 오류 없이 카페 추천 |
| 11b | 동네 이름을 지어내지 않음 (QA-2) | ✅ | `11-demonstrative-first.png` | "성수동 근처" 같은 표현 없음 |
| 12 | 서버 오류 말풍선 (RF2) | ✅ | `12-server-error.png` | OpenSearch 꺼짐 → 빨간 테두리 말풍선 "검색 서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요." |
| 12b | 오류 뒤에도 계속 사용 | ✅ | — | 다음 메시지 정상 전송 |
| 13 | LLM 꺼짐 → 템플릿 답변 (RF1) | ✅ | `13-llm-down-template.png` | "광화문 근처 추천 장소를 지도에 표시했어요: 광화문 세종클럽, 금용문, …" + 핀 |
| 14 | 네트워크 끊김 | ✅ | `14-network-offline.png` | "서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요." |

RF = 계획서 Review Focus.

## 발견한 버그와 처리

| ID | 내용 | 담당 | 처리 |
|---|---|---|---|
| QA-1 | `session_id`가 64자를 넘으면 200을 주지만 MySQL 저장이 조용히 실패해 기록이 사라짐 | 팀원1 | 850364d: 65자 이상이면 422 → 재확인 통과 (`tests/integration/test_live_api.py`) |
| QA-2 | 기준점이 없는데 답변이 "주변에는…"/"성수동 근처에…"라고 함, "거기 근처" 기준점 대신 이전 지역명(광화문)을 씀, 먼 곳도 "근처"라고 함 | 팀원1 | bed8ebc: 프롬프트 규칙 보강 → 재확인 통과(4c·10c·11b) |
| QA-3 | 지도가 서울 넓은 범위일 때 랜드마크 일러스트 6개가 서로 겹치고 핀 이름표와도 겹침 | 팀원2 | ea2ea88: 겹치는 랜드마크는 그리지 않음(`pickLandmarks`) → 재확인 통과(`10-gps-denied.png`) |

## 주의 (남은 한계)

- **LLM 문구**: QA-2는 프롬프트 규칙으로 고쳤기 때문에 매번 같은 문장이 나온다고 보장할 수 없음. 4c·10c·11b는 이번 실행 기준 결과.
- **먼 장소 채우기**: 반경 1500m 안이 1~2곳이면 같은 조건의 가장 가까운 곳으로 3곳을 채움(B5 결정). 그래서 "거기 근처 카페"에서 걸어서 35·45분 걸리는 곳도 나옴. 카드와 칩에는 실제 도보 시간이 표시됨.
- **넓은 범위 지도**: QA-3 수정 뒤 핀과 겹치는 랜드마크는 그리지 않으므로, 서울 곳곳이 결과로 나오면 랜드마크가 하나도 안 보일 수 있음(의도된 동작).
- **범례 "🔵 내 위치"**: GPS를 쓰지 않을 때도 항상 보임(시안·계획 문구대로, 그대로 둠).
- **실제 기기 위치 권한**: 헤드리스 Chrome의 권한 설정(`Browser.grantPermissions`/`setPermission denied`)과 위치 덮어쓰기로 확인함. 실제 휴대폰의 권한 팝업은 사람이 한 번 더 확인하는 것이 좋음.
- **Git Bash curl 함정**: `curl -d '{"message":"한글"}'`은 인코딩이 깨져 400이 남. 수동 점검은 파이썬 requests나 UTF-8 파일(`--data-binary @파일`)로 할 것.

## 자동 테스트 결과 (같은 커밋)

- `pytest -m "not integration"`: 131 통과
- `pytest -m integration`: 19 통과 (`tests/integration/test_live_api.py` 8, `test_live_chat.py` 3, 팀원1의 `tests/test_history.py` MySQL 8)
- `node --test "tests/js/*.test.mjs"`: 37 통과

---

# B8·B9 화면 시나리오 점검 (장소 정보 질문·멀티턴)

- 점검일: 2026-10-26 · 점검: 팀원3(QA)
- 대상: `feat/qa` (feat/backend 9f38d69 병합 — B8·B9 포함)
- 환경: 위와 같음(헤드리스 Chrome, iPhone 14 Pro 393x852, 실서비스). 서버는 포트 **8012** 하나(정상).
- 자동 실행: `scripts/qa_mobile/run_b89.mjs`

```bash
python -m uvicorn app.main:create_app --factory --port 8012
node scripts/qa_mobile/run_b89.mjs <스크린샷 폴더> http://localhost:8012
```

끝나면 `<스크린샷 폴더>/results.json`의 `sessions`를 `MySQLHistoryRepo.delete_session()`으로 지운다(완료).
스크린샷: `C:\Users\SMT03\AppData\Local\Temp\claude\C--Users-SMT03-SeoulTourChatbot\1f8c78e6-b194-4613-a7ad-8121fad70e0f\scratchpad\shots\b89-*.png`

## 결과: 14개 항목 모두 통과

| # | 항목 | 결과 | 스크린샷 | 확인한 내용 |
|---|---|---|---|---|
| B9-1 | 세션1 "명동 맛집 추천해줘" → "카페는?" | ✅ | `b89-01-myeongdong-cafe.png` | ☕ 핀 3개(감꽃당·광장싸롱 1961·고라니커피클럽), 요약 바 "명동 근처" |
| B9-2 | "다른 데 더 추천해줘" | ✅ | `b89-02-more.png` | 명동 기준 유지, ☕ 유지, 이전 카페와 겹치지 않음(개뿔·고카페 용산아이파크몰점·그라운드62) |
| B9-2b | "다른 데 더" 답변 지역명 = center.label | ✅ | `b89-02-more.png` | "…명동에서 조금 떨어져 있어요." — '남산' 없음, 이전 카페 이름 다시 말하지 않음 |
| B9-2c | 접힘 칩 순서 = 응답 순서 | ✅ | — | "두 번째"를 화면에서 셀 때 칩 순서가 기준(지도 핀은 그리는 순서라 다를 수 있음) |
| B8-1 | "두 번째 거기 어디야?" | ✅ | `b89-03-ordinal-info.png` | 답변만, 핀 그대로, 기록 center=2번째(고카페 용산아이파크몰점) |
| B8-1b | 답변이 그 장소 이름을 말함 | ✅ | `b89-03-ordinal-info.png` | 주소·분류·전화 안내(LLM 문구) |
| B9-3 | 새로고침 복원 | ✅ | `b89-04-reload.png` | 말풍선 8개 그대로, 핀은 "다른 데 더" 결과 3개 |
| B9-4 | 세션2 "강남 관광지 알려줘" | ✅ | `b89-05-gangnam.png` | 요약 바 "강남구 근처"(장소 '강남'이 기준점 아님), 관광지 핀 5개 |
| B8-2 | "아까 첫 번째 거 다시 알려줘" | ✅ | — | 1번 장소(국가무형유산전수교육관) 설명, 핀 그대로 |
| B9-5 | "거기서 가까운 맛집은?" | ✅ | `b89-06-gangnam-near-food.png` | "국가무형유산전수교육관 근처 · 추천 5곳", 맛집 핀 |
| B8-3 | 이름으로 정보 질문·정보 없음 | ✅ | `b89-07-info-missing.png` | "고려삼계탕 — 주차 정보는 없어요. 전화(02-752-9376)로 확인해 보세요." 지어내지 않음, 핀 그대로 |
| B8-4 | 핀 선택 후 "거기 전화번호 알려줘" | ✅ | `b89-08-info-selected.png` | `selected_place_id` 전송, 고른 장소(개화) 설명 |
| B9-6 | 회귀: 정보 질문 뒤 "거기 근처 카페 있어?" | ✅ | `b89-09-near-cafe.png` | "개화 근처 · 추천 3곳" ☕ 핀 |
| B8-5 | 대상 없는 "주차 가능해?" | ✅ | `b89-10-clarify.png` | 되묻기 말풍선(오류 아님), 핀 없음 |

LLM 다운 시 detail 템플릿은 화면 대신 통합 테스트로 확인(`tests/integration/test_live_multiturn.py::test_live_info_llm_down_uses_detail`: "가회동성당 — 주차: 가능.").

## 발견한 문제 (B8·B9)

| ID | 내용 | 담당 | 처리 |
|---|---|---|---|
| QA-4 | "종로 관광지" 뒤 "아까 그 궁 주차돼?" → 이름에 '궁'이 든 건청궁이 아니라 같은 분류(역사관광지)의 첫 장소 가회동성당을 설명 | 팀원1 | 보고함 |
| QA-5 | 목록 범위를 넘는 순서("6번째 거 어디야?", 5곳 목록) → 같은 목록을 다시 추천 | 팀원1 | 보고함 |
| QA-6 | 가리킬 장소가 없는 "거기 어디야?" → 기준점 없는 아무 관광지 5곳 추천 | 팀원1 | 보고함 |
| QA-7 | (경미) 두 턴 전 목록을 가리키는 "아까 그 식당 몇 시에 열어?" → 되묻기(직전 목록만 봄) | 팀원1 | 보고함 |

## 주의 (B8·B9)

- **"다른 데 더"가 멀어짐**: 명동 카페는 반경 안이 3곳뿐이라 두 번째 목록부터 도보 41~79분(2.8km~). 답변은 "조금 떨어져 있어요"라고 말함(이번 실행). 팀원1 개선 후보.
- **음식점 detail 없음**: B7 데이터가 469/574에서 멈춰 음식점 100곳은 상세 정보가 비어 있음 → 음식점 정보 질문은 대부분 "○○ 정보는 없어요. 전화(…)로 확인해 보세요."
- **경복궁은 카탈로그에 없음**(경복궁 별빛야행만 있음) → "경복궁 입장료 얼마야?"는 되묻기. 데이터 한계.

## 자동 테스트 결과 (B8·B9 추가 후)

- `pytest -m "not integration"`: 177 통과 (QA 신규 `tests/api/test_multiturn_api.py` 22)
- `pytest -m integration`: 27 통과 (QA 신규 `tests/integration/test_live_multiturn.py` 7)
- `node --test "tests/js/*.test.mjs"`: 37 통과
