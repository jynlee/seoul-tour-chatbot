import pytest

from app.catalog import CAFE_CAT3
from app.center import Center
from app.course import (
    CAFE, FOOD, NIGHT, SIGHT, TOURSPOT, CoursePlan, MAX_TOTAL_WALK_M, build_course, is_course_question, plan_course,
)
from app.geo import haversine_m, walk_min
from app.history import InMemoryHistoryRepo
from app.schemas import ChatResponse, PlaceOut
from tests.conftest import FakeEmbedder, FakeSearcher, _p


def _place(**extra):
    base = dict(id="1", title="t", kind="tour", category="c", addr="a", tel="",
                lat=37.5, lng=127.0, image="")
    base.update(extra)
    return PlaceOut(**base)


def test_place_out_course_fields_default_none():
    p = _place()
    assert (p.step, p.leg_m, p.leg_walk_min) == (None, None, None)


def test_chat_response_course_default_false():
    assert ChatResponse(session_id="s", answer="a").course is False


def test_history_roundtrip_keeps_step():
    repo = InMemoryHistoryRepo()
    p = _place(id="398373", title="카페", kind="food", category="카페/전통찻집",
               step="카페", leg_m=420, leg_walk_min=6)
    repo.save("test-s", "assistant", "a", places=[p])
    got = repo.last_assistant("test-s").places[0]
    assert (got.step, got.leg_m, got.leg_walk_min) == ("카페", 420, 6)


def labels(plan):
    return [s.label for s in plan.steps]


@pytest.mark.parametrize("msg,theme,expected", [
    ("기념일인데 서울 데이트 추천해줘", "date", ["볼거리", "맛집", "카페", "야경"]),
    ("종로에서 데이트할 곳", "date", ["볼거리", "맛집", "카페", "야경"]),
    ("서울 데이트 코스 추천해줘", "date", ["볼거리", "맛집", "카페", "야경"]),
    ("쇼핑하고 맛집 갈 건데 추천 코스", "shopping_food", ["쇼핑", "맛집", "카페"]),
    ("맛집 갔다가 쇼핑하는 코스", "shopping_food", ["쇼핑", "맛집", "카페"]),
    ("궁 보고 밥 먹고 카페 가는 코스", "custom", ["역사", "맛집", "카페"]),
    ("명동 코스 짜줘", "default", ["관광지", "맛집", "관광지", "카페"]),
    ("한강 데이트 코스", "custom", ["산책", "맛집", "카페"]),
    ("맛집 코스", "custom", ["관광지", "맛집", "카페"]),
    ("카페 가고 맛집 가는 코스", "custom", ["관광지", "카페", "맛집"]),
    ("카페 코스", "custom", ["관광지", "카페", "맛집"]),
    ("점심먹고 카페 가는 코스", "custom", ["관광지", "맛집", "카페"]),
    ("친구랑먹을 코스 짜줘", "custom", ["관광지", "맛집", "카페"]),
    ("경복궁 근처 데이트 코스", "date", ["볼거리", "맛집", "카페", "야경"]),
])
def test_plan_course(msg, theme, expected):
    plan = plan_course(msg)
    assert plan.theme == theme
    assert labels(plan) == expected


@pytest.mark.parametrize("msg", ["데이트하기 좋은 카페", "데이트 맛집", "데이트하기 좋은 공원",
                                  "명동 근처 맛집", "경복궁 주차돼?", "고마워"])
def test_not_course(msg):
    assert plan_course(msg) is None


def test_course_word_alone():
    assert is_course_question("하루 일정 짜줘")


def test_custom_max_four_steps():
    assert len(plan_course("궁 보고 박물관 가고 밥 먹고 카페 가고 야경 보는 코스").steps) == 4


def test_step_definitions():
    food, cafe = plan_course("서울 데이트 코스 추천해줘").steps[1:3]
    assert food.exclude_cat3 and cafe.cat3 == food.exclude_cat3
    night = plan_course("서울 데이트 코스 추천해줘").steps[3]
    assert night.topic == "night" and night.required_topic and night.quiet_drop


# ---- 동선 만들기 (Task 3) ----
LAT, LNG = 37.5750, 126.9800
DLAT = 0.0072  # 위도 0.0072도 약 800m
PLAN = CoursePlan("date", (SIGHT, FOOD, CAFE, NIGHT))
CENTER = Center(LAT, LNG, "테스트동", "area")


def _sight(id, title, dlat=0.0, dlng=0.0, gu="종로구"):
    return _p(id, title, "12", "역사관광지", "A02010100", "서울특별시 종로구 a", LAT + dlat, LNG + dlng, gu)


def _food(id, title, dlat=0.0, dlng=0.0):
    return _p(id, title, "39", "한식", "A05020100", "서울특별시 종로구 b", LAT + dlat, LNG + dlng, "종로구")


def _cafe(id, title, dlat=0.0, dlng=0.0):
    return _p(id, title, "39", "카페/전통찻집", CAFE_CAT3, "서울특별시 종로구 c", LAT + dlat, LNG + dlng, "종로구")


def _night(id, title, dlat=0.0, dlng=0.0):
    return _p(id, title, "12", "건축/조형물", "A02030100", "서울특별시 종로구 d", LAT + dlat, LNG + dlng, "종로구")


def _build(places, plan=PLAN, center=CENTER, message="데이트 코스", **kw):
    catalog = {p.id: p for p in places}
    return build_course(message, plan, center, FakeSearcher(catalog), FakeEmbedder(), catalog, **kw)


def _basic():
    return [_sight("s1", "한옥전시관", 0.001), _food("f1", "맛있는집", 0.003), _cafe("c1", "좋은카페", 0.004),
            _night("n1", "도심 전망대", 0.005)]


def _dist(a, b):
    return haversine_m(a.lat, a.lng, b.lat, b.lng)


def test_course_follows_step_order_and_walkable():
    r = _build(_basic())
    assert r.ok and [p.step for p in r.places] == ["볼거리", "맛집", "카페", "야경"]
    assert [p.id for p in r.places] == ["s1", "f1", "c1", "n1"]
    for a, b in zip(r.places, r.places[1:]):
        assert _dist(a, b) <= 1500


def test_next_step_prefers_800m_then_widens():
    ps = _basic() + [_food("f2", "먼식당", 0.009)]
    catalog = {p.id: p for p in ps}
    # 먼 식당(f2, 1km)의 관련도가 더 높아도 800m 안 f1이 먼저
    near = build_course("데이트 코스", CoursePlan("c", (SIGHT, FOOD, CAFE)), CENTER,
                        FakeSearcher(catalog, scores={"f2": 9.0}), FakeEmbedder(), catalog)
    assert near.places[1].id == "f1"
    # 800m 안에 음식점이 없고 1.2km에 있으면 그것
    far = _build([_sight("s1", "한옥전시관"), _food("f2", "먼식당", 0.011), _cafe("c1", "좋은카페", 0.012)],
                 plan=CoursePlan("c", (SIGHT, FOOD, CAFE)))
    assert [p.id for p in far.places] == ["s1", "f2", "c1"]
    assert far.places[1].leg_m == round(_dist(far.places[0], far.places[1]))


def test_step_dropped_when_nothing_within_1500():
    ps = [_sight("s1", "한옥전시관"), _food("f1", "맛있는집", 0.003), _sight("s2", "또 전시관", 0.004),
          _cafe("far", "먼카페", 0.05)]
    r = _build(ps, plan=CoursePlan("c", (SIGHT, FOOD, TOURSPOT, CAFE)))
    assert [p.step for p in r.places] == ["볼거리", "맛집", "관광지"]
    assert r.dropped == ["카페"] and r.ok


def test_night_dropped_quietly():
    r = _build(_basic()[:3])
    assert [p.step for p in r.places] == ["볼거리", "맛집", "카페"]
    assert r.dropped == [] and r.ok


def test_night_requires_topic_match():
    ps = _basic()[:3] + [_sight("x", "평범한 전시관", 0.005)]
    r = _build(ps)
    assert "야경" not in [p.step for p in r.places]


def test_total_walk_capped():
    # 매 칸 약 1.2km씩: 3칸이면 2.4km, 4칸째는 3km 초과라 빠진다
    ps = [_sight("s1", "한옥전시관"), _food("f1", "맛집", 0.011), _cafe("c1", "카페", 0.022), _night("n1", "도심 전망대", 0.033)]
    r = _build(ps)
    legs = [p.leg_m for p in r.places[1:]]
    assert sum(legs) <= MAX_TOTAL_WALK_M
    assert [p.id for p in r.places] == ["s1", "f1", "c1"] and r.dropped == []


def test_center_place_and_its_parts_excluded():
    ps = [_sight("g", "경복궁", 0.0), _sight("g2", "경복궁 건청궁", 0.002), _sight("s1", "한옥전시관", 0.003),
          _food("f1", "맛있는집", 0.004), _cafe("c1", "좋은카페", 0.005)]
    c = Center(LAT, LNG, "경복궁", "place", place_id="g")
    r = _build(ps, plan=CoursePlan("c", (SIGHT, FOOD, CAFE)), center=c)
    ids = [p.id for p in r.places]
    assert "g" not in ids and "g2" not in ids and ids[0] == "s1"


def test_places_without_coords_never_chosen():
    ps = [_p("z", "영점 전시관", "12", "역사관광지", "A02010100", "서울", 0.0, 0.0, "종로구"),
          _p("o", "부산 전시관", "12", "역사관광지", "A02010100", "부산", 35.1, 129.0, "종로구")] + _basic()
    r = _build(ps, center=None)
    assert not {"z", "o"} & {p.id for p in r.places}
    assert r.ok


def test_no_same_group_twice():
    ps = [_sight("a", "창덕궁 인정문", 0.0), _sight("b", "창덕궁 낙선재", 0.001), _food("f1", "맛있는집", 0.003),
          _sight("c", "다른 전시관", 0.004), _cafe("c1", "좋은카페", 0.005)]
    r = _build(ps, plan=CoursePlan("c", (SIGHT, FOOD, TOURSPOT, CAFE)))
    titles = [p.title for p in r.places]
    assert not ("창덕궁 인정문" in titles and "창덕궁 낙선재" in titles)
    assert "다른 전시관" in titles


def test_food_places_with_same_first_word_both_kept():
    # 음식점끼리는 묶음 검사를 하지 않는다: "인사동 한정식"과 "인사동 찻집"은 별개 가게 (Ruling 6)
    ps = [_sight("s1", "한옥전시관", 0.0), _food("f1", "인사동 한정식", 0.002), _cafe("c1", "인사동 찻집", 0.0038)]
    r = _build(ps)
    titles = [p.title for p in r.places]
    assert _dist(*[next(p for p in ps if p.title == t) for t in ("인사동 한정식", "인사동 찻집")]) <= 250
    assert r.ok and titles == ["한옥전시관", "인사동 한정식", "인사동 찻집"]


def test_legs():
    r = _build(_basic())
    first = r.places[0]
    assert first.leg_m == round(haversine_m(LAT, LNG, first.lat, first.lng))
    for p in r.places:
        assert p.leg_walk_min == walk_min(p.leg_m) and p.distance_m is None and p.walk_min is None
    none = _build(_basic(), center=None)
    assert none.places[0].leg_m is None and none.places[0].leg_walk_min is None
    assert none.places[1].leg_m is not None


def test_gu_center_first_stop_in_gu():
    ps = [_sight("o", "성동 전시관", 0.0, gu="성동구"), _sight("s1", "종로 전시관", 0.001)] + _basic()[1:]
    ps[0], ps[1] = ps[0], ps[1]
    gu = Center(LAT, LNG, "종로구", "gu")
    r = _build(ps, center=gu)
    assert r.places[0].id == "s1"
    assert r.places[0].leg_m is None
    hist = Center(LAT, LNG, "종로구", "history")
    assert _build(ps, center=hist).places[0].id == "s1"


def test_fails_below_three():
    r = _build([_sight("s1", "한옥전시관"), _food("f1", "맛있는집", 0.003)])
    assert not r.ok and len(r.places) == 2


def test_exclude_ids_respected():
    ps = _basic() + [_food("f2", "다른식당", 0.004)]
    r = _build(ps, exclude_ids={"f1"})
    assert "f1" not in [p.id for p in r.places] and r.places[1].id == "f2"


def test_cafe_not_used_for_food_step():
    r = _build([_sight("s1", "한옥전시관"), _cafe("c1", "좋은카페", 0.003), _cafe("c2", "또카페", 0.004)],
               plan=CoursePlan("c", (SIGHT, FOOD, CAFE)))
    assert [p.step for p in r.places] == ["볼거리", "카페"] and r.dropped == ["맛집"]


def test_topic_boost_orders_candidates():
    ps = [_sight("a", "한옥전시관", 0.001), _sight("b", "고궁 정원", 0.002), _food("f1", "맛집", 0.003), _cafe("c1", "카페", 0.004)]
    plan = CoursePlan("c", (plan_course("역사 코스 추천").steps[0], FOOD, CAFE))
    r = _build(ps, plan=plan, message="궁 코스")
    assert r.places[0].id == "b"


def test_gu_center_first_stop_found_outside_knn_hits():
    # 종로구 전시관이 kNN 결과에 없어도(다른 구만 상위) 구 안에서 첫 칸을 고른다
    ps = [_sight("o", "성동 전시관", 0.0, gu="성동구"), _sight("in", "종로 전시관", 0.001),
          _sight("gu", "종로구", 0.0), _food("f1", "맛있는집", 0.003), _cafe("c1", "좋은카페", 0.004)]
    catalog = {p.id: p for p in ps}

    class NoGuHits(FakeSearcher):
        def knn(self, *a, **k):
            return [h for h in super().knn(*a, **k) if self.catalog[h[0]].gu != "종로구" or self.catalog[h[0]].kind == "food"]

    r = build_course("데이트 코스", CoursePlan("c", (SIGHT, FOOD, CAFE)), Center(LAT, LNG, "종로구", "gu"),
                     NoGuHits(catalog), FakeEmbedder(), catalog)
    assert r.places[0].id == "in" and r.ok


# ---- 실데이터 확인 뒤 보정 (Ruling 8·9) ----
def test_night_rejects_statue_accepts_bridge():
    statue = _night("st", "전태일동상", 0.005)
    r = _build(_basic()[:3] + [statue])
    assert "야경" not in [p.step for p in r.places]
    bridge = _night("br", "○○대교", 0.005)
    r2 = _build(_basic()[:3] + [statue, bridge])
    assert [p.id for p in r2.places if p.step == "야경"] == ["br"]


def test_area_like_title_place_excluded_from_all_steps():
    area = _sight("hd", "홍대", 0.0005)
    r = _build(_basic() + [area])
    assert "hd" not in [p.id for p in r.places]
    r2 = _build([area, _food("f1", "맛있는집", 0.003), _cafe("c1", "좋은카페", 0.004)],
                plan=CoursePlan("c", (SIGHT, FOOD, CAFE)))
    assert not r2.ok  # 홍대만 있는 볼거리 칸은 비어 3곳이 안 됨


@pytest.mark.parametrize("title", ["[종로둘레길 3코스] 낙산 코스", "북악산 둘레길", "서울 성곽 순례 코스"])
def test_walking_course_titles_excluded_from_sight_steps(title):
    r = _build(_basic() + [_sight("w", title, 0.0005)])
    assert "w" not in [p.id for p in r.places]


# ---- Ruling 10: 야경 제목 검사·관광특구 ----
@pytest.mark.parametrize("title", ["천도교 중앙대교당", "한강시민공원 여의도수영장(실외)", "성당 야경길", "망원 도서관 전망"])
def test_night_title_rejected(title):
    r = _build(_basic()[:3] + [_night("x", title, 0.005)])
    assert "야경" not in [p.step for p in r.places]


@pytest.mark.parametrize("title", ["반포대교 달빛무지개분수", "N서울타워", "여의도 물빛광장", "성수대교", "행복다리 (보행교)"])
def test_night_title_accepted(title):
    r = _build(_basic()[:3] + [_night("x", title, 0.005)])
    assert [p.id for p in r.places if p.step == "야경"] == ["x"]


def test_tourism_zone_title_excluded_from_sight_steps():
    r = _build(_basic() + [_sight("z", "종로 청계 관광특구", 0.0005)])
    assert "z" not in [p.id for p in r.places]
