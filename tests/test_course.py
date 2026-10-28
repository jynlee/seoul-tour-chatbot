import pytest

from app.course import is_course_question, plan_course
from app.history import InMemoryHistoryRepo
from app.schemas import ChatResponse, PlaceOut


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
