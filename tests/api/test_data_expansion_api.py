"""QA: 데이터 확장(574 → 3,444곳, feat/data 16e86aa) — 새 데이터로 기준점·이어받기·지역명 제목·세부 장소 묶기.

POST /api/chat·GET /api/history (가짜 검색·LLM + 새 카탈로그 data/seoul_tour.json, 상세·개요 포함).
FakeSearcher는 카탈로그 순서로 돌려주므로 '어느 장소가 몇 번째'가 아니라 기준점·이어받기·묶기 규칙만 본다.
xfail(strict) = 이번 QA에서 찾은 버그 재현(QA-10·QA-11). 고쳐지면 XPASS로 실패하니 xfail 표시를 지울 것.
"""
import pytest

from app.center import match_place
from app.geo import haversine_m
from app.llm import CLARIFY_ANSWER
from app.recommend import GROUP_RADIUS_M, group_key
from tests.api.test_multiturn_api import Api, assert_place_info


@pytest.fixture(scope="module")
def new_catalog():
    from app.catalog import load_catalog

    return load_catalog("data/seoul_tour.json", "data/seoul_tour_enriched.json")


def titles(body):
    return [p["title"] for p in body["places"]]


# ---------------------------------------------------------------- 서울 전체 질문(d976c2c)

@pytest.mark.parametrize("first, second", [
    ("명동 맛집 추천해줘", "서울 야경 명소 알려줘"),          # '서울' 낱말
    ("종로 관광지 추천해줘", "서울에서 데이트 코스 추천해줘"),  # 사용자 실제 대화
    ("강서구 공원 추천해줘", "역사 유적지 알려줘"),            # 장소 없이 세부 주제만
    ("청계천 근처 맛집 추천해줘", "야경 보기 좋은곳 알려줘"),   # 사용자 실제 대화
])
def test_whole_seoul_drops_previous_center(new_catalog, first, second):
    api = Api(new_catalog)
    assert api.say(first)["center"] is not None
    r = api.say(second)
    assert r["center"] is None and r["places"]


@pytest.mark.parametrize("first, second, source, label", [
    ("강서구 공원 추천해줘", "카페는?", "gu", "강서구"),
    ("강서구 공원 추천해줘", "다른 데 더 추천해줘", "gu", "강서구"),
    ("명동 맛집 추천해줘", "공원은?", "history", "명동"),
    ("강서구 공원 추천해줘", "서울역 근처 맛집", "area", "서울역"),   # '서울역'은 서울 전체가 아님
    ("강서구 공원 추천해줘", "서울숲 근처 카페", "place", "서울숲"),  # '서울숲'도 장소
    ("강서구 공원 추천해줘", "서울 시청 근처 맛집", "area", "시청"),  # '서울'이 있어도 지역 이름이 이김
])
def test_follow_up_and_seoul_prefixed_names_keep_center(new_catalog, first, second, source, label):
    api = Api(new_catalog)
    api.say(first)
    r = api.say(second)
    assert r["center"] and (r["center"]["source"], r["center"]["label"]) == (source, label)


def test_user_conversation_near_cafe_after_gu_list(new_catalog):
    """사용자 실제 대화 끝 두 턴: 구 목록 뒤 '그 근처 카페는?' → 직전 목록 1번이 기준점, 카페만."""
    api = Api(new_catalog)
    r1 = api.say("강서구에 산책할만한 곳 추천해줘")
    assert r1["center"]["source"] == "gu"
    r2 = api.say("그 근처 카페는?")
    assert r2["center"]["source"] == "place" and r2["center"]["label"] == r1["places"][0]["title"]
    assert r2["places"] and all(p["category"] == "카페/전통찻집" for p in r2["places"])


# QA-11: '이 근처'·'근처에'·'주변에'는 지시어로 안 잡혀(REF_DEMONSTRATIVES에 없음), 세부 주제가 있으면
# wants_whole_seoul → 직전 기준점을 버리고 서울 전체에서 고름. (예: 종로 관광지 → "이 근처 박물관도 있어?" → 용산·성북구 대학 박물관)
@pytest.mark.xfail(strict=True, reason="QA-11: '이 근처/근처에/주변에 + 세부 주제' 이어 묻기가 서울 전체로 바뀜 (app/dialog.py wants_whole_seoul)")
@pytest.mark.parametrize("first, second", [
    ("종로 관광지 추천해줘", "이 근처 박물관도 있어?"),
    ("홍대 맛집 추천해줘", "근처에 산책할 곳 있어?"),
    ("반포한강공원 근처 맛집", "주변에 야경 명소는?"),
])
def test_qa11_near_word_follow_up_keeps_center(new_catalog, first, second):
    api = Api(new_catalog)
    r1 = api.say(first)
    r = api.say(second)
    # 직전 기준점을 이어받거나(구·지역) 직전 목록의 장소를 기준점으로 — 어느 쪽이든 서울 전체(center null)는 아님
    assert r["center"] is not None and r["center"]["label"] in (r1["center"]["label"], *titles(r1))


# ---------------------------------------------------------------- 지역명 제목·세부 장소

@pytest.mark.parametrize("message, source, label", [
    ("명동 관광지", "area", "명동"),       # '명동' 제목 장소(체험관광지)가 있어도 지역
    ("홍대 근처 카페", "area", "홍대"),
    ("강남 맛집", "gu", "강남구"),
    ("한강 야경 볼 곳", None, None),        # '한강' 제목 장소를 기준점으로 안 잡음
])
def test_area_like_titles_are_areas(new_catalog, message, source, label):
    r = Api(new_catalog).say(message)
    got = (r["center"]["source"], r["center"]["label"]) if r["center"] else (None, None)
    assert got == (source, label)


@pytest.mark.parametrize("message", ["종로 근처 궁이나 박물관", "종로 역사 관광지 알려줘", "반포한강공원 근처 관광지",
                                     "덕수궁 근처 볼거리", "강서구에 산책할만한 곳"])
def test_no_two_parts_of_same_place_in_one_list(new_catalog, message):
    r = Api(new_catalog).say(message)
    by_id = {p["id"]: new_catalog[p["id"]] for p in r["places"]}
    ps = list(by_id.values())
    for i, a in enumerate(ps):
        for b in ps[i + 1:]:
            if group_key(a.title) and group_key(a.title) == group_key(b.title):
                assert haversine_m(a.lat, a.lng, b.lat, b.lng) > GROUP_RADIUS_M, (a.title, b.title)


# ---------------------------------------------------------------- QA-10: 새 데이터의 문화재식 제목

# 새 데이터의 대표 명소 제목이 '창덕궁과 후원 [유네스코 세계유산]'·'서울 운현궁'·'서울 효창공원'·'서울 명동성당'처럼
# 붙어 있어(‘서울 ’로 시작 55곳, '○○과 ○○' 4곳) 사람들이 부르는 이름으로는 못 찾음 → 정보 질문은 되묻기,
# "효창공원 근처 맛집"은 기준점 없이 서울 전체(도봉구·동대문구 음식점). 위치: app/center.py title_aliases.
@pytest.mark.xfail(strict=True, reason="QA-10: '서울 ○○'·'○○과 ○○' 제목을 부르는 이름으로 못 찾음 (app/center.py title_aliases)")
@pytest.mark.parametrize("message, title", [
    ("창덕궁 주차돼?", "창덕궁과 후원 [유네스코 세계유산]"),
    ("운현궁 입장료 얼마야?", "서울 운현궁"),
    ("효창공원 근처 맛집 추천해줘", "서울 효창공원"),
    ("명동성당 근처 카페", "서울 명동성당"),
    ("국립민속박물관 근처 카페", "국립민속박물관과 국립민속박물관 어린이박물관"),
])
def test_qa10_heritage_style_titles_by_common_name(new_catalog, message, title):
    p = match_place(message, new_catalog)
    assert p is not None and p.title == title


@pytest.mark.xfail(strict=True, reason="QA-10: '창덕궁 주차돼?'가 되묻기로 끝남")
def test_qa10_changdeokgung_info_not_clarify(new_catalog):
    r = Api(new_catalog).say("창덕궁 주차돼?")
    assert_place_info(r)
    assert r["answer"] != CLARIFY_ANSWER


def test_known_landmarks_still_found(new_catalog):
    """회귀: 이미 되는 이름들."""
    for message, title in [("경복궁 근처 맛집", "경복궁"), ("창경궁 근처 카페", "창경궁"), ("덕수궁 근처 볼거리", "덕수궁"),
                           ("반포한강공원 근처 맛집", "반포한강공원"), ("청계천 근처 맛집 추천해줘", "청계천"),
                           ("석파정 근처 맛집", "대원군별장(석파정)")]:
        p = match_place(message, new_catalog)
        assert p is not None and p.title == title, message


# ---------------------------------------------------------------- 리드 결정(2026-10-27): 접속어 + 짧은 이어 묻기

# '그럼/그러면/그리고/또' + 짧은 이어 묻기는 직전 기준점 유지(서울 전체 아님). 지금은 세부 주제가 있어 서울 전체로 감.
@pytest.mark.xfail(strict=True, reason="리드 결정: '그럼/그러면/그리고/또' + 짧은 이어 묻기는 직전 기준점 유지 (app/dialog.py wants_whole_seoul)")
@pytest.mark.parametrize("first, second, source, label", [
    ("강서구 카페 추천해줘", "그럼 산책할 곳은?", "gu", "강서구"),
    ("종로 관광지 추천해줘", "그러면 박물관은?", "gu", "종로구"),
    ("명동 맛집 추천해줘", "그리고 야경 명소는?", "history", "명동"),
    ("홍대 맛집 추천해줘", "또 공원 있어?", "history", "홍대"),
])
def test_connective_short_follow_up_keeps_center(new_catalog, first, second, source, label):
    api = Api(new_catalog)
    api.say(first)
    r = api.say(second)
    assert r["center"] and (r["center"]["source"], r["center"]["label"]) == (source, label)


def test_connective_with_seoul_word_is_still_whole_seoul(new_catalog):
    """'서울'을 낱말로 말하면 접속어가 있어도 서울 전체 (d976c2c 규칙 유지)."""
    api = Api(new_catalog)
    api.say("강서구 카페 추천해줘")
    assert api.say("그럼 서울 야경 명소는?")["center"] is None


# ---------------------------------------------------------------- 품질 메모 → 리드가 data에게 맡김 (재현)

def _nearest(catalog, center, pred):
    from app.catalog import has_coords

    return min((p for p in catalog.values() if has_coords(p) and pred(p)),
               key=lambda p: haversine_m(center["lat"], center["lng"], p.lat, p.lng))


# ① 반경 기준(area/place)은 kNN 상위 100곳 중 반경 안 5곳 → 음식점이 1,586곳이 되자 아주 가까운 곳이 빠짐.
#    가짜 검색(카탈로그 순서)으로도 같은 구조가 재현됨: 청계천 1.5km 안 음식점 91곳, 84m 더 우리곱창이 빠짐.
@pytest.mark.xfail(strict=True, reason="품질 ①: 반경 안 가장 가까운 곳이 kNN 후보 밖이면 빠짐 (app/recommend.py _recommend, CANDIDATES_K)")
def test_q1_nearest_food_in_radius_included(new_catalog):
    r = Api(new_catalog).say("청계천 근처 맛집 추천해줘")
    assert r["center"]["label"] == "청계천"
    nearest = _nearest(new_catalog, r["center"], lambda p: p.kind == "food")
    assert nearest.id in [p["id"] for p in r["places"]], nearest.title


# ② 기준점 장소의 세부 장소('덕수궁 돈덕전' 0m, '반포한강공원 달빛광장')가 결과에 나옴
@pytest.mark.xfail(strict=True, reason="품질 ②: 기준점 장소와 같은 묶음(세부 장소)이 결과에 나옴 (app/recommend.py one_per_group에 기준점 미포함)")
# (가짜 검색 순서로는 '반포한강공원 근처'의 달빛광장이 안 뽑혀 재현 안 됨 → 실서비스 tests/integration/test_live_data_expansion.py)
@pytest.mark.parametrize("message", ["덕수궁 근처 볼거리"])
def test_q2_center_parts_excluded(new_catalog, message):
    r = Api(new_catalog).say(message)
    key = group_key(r["center"]["label"])
    assert key and not [p["title"] for p in r["places"] if group_key(p["title"]) == key]


# ③ 국립민속박물관이 '산업관광지'(신분류 매핑)
@pytest.mark.xfail(strict=True, reason="품질 ③: 국립민속박물관 분류가 산업관광지 (app/catalog.py effective_codes 신분류 매핑)")
def test_q3_folk_museum_is_culture(new_catalog):
    p = next(p for p in new_catalog.values() if p.title.startswith("국립민속박물관"))
    assert p.category == "문화시설"
