from app.dialog import (
    asked_fields, format_history, intent_from_places, is_more_request, is_near, ordinal_index, resolve_reference,
)
from app.recommend import to_place_out
from app.schemas import CenterOut, HistoryMessage


def test_ordinal_index():
    assert ordinal_index("첫 번째 거 다시 알려줘") == 0
    assert ordinal_index("두번째 거기 어디야?") == 1
    assert ordinal_index("3번 어때") == 2
    assert ordinal_index("마지막 거") == -1
    assert ordinal_index("세종클럽 어때") is None
    assert ordinal_index("2번 출구 근처") is None


def test_keywords():
    assert asked_fields("주차 가능해? 몇 시에 열어?") == ["parking", "hours"]
    assert asked_fields("광화문 근처 맛집") == []
    assert is_near("거기서 가까운 맛집은?")
    assert is_more_request("다른 데 더 추천해줘") and is_more_request("또 없어?")
    assert not is_more_request("카페는?")


def _last(small_catalog, *ids):
    return [to_place_out(small_catalog[i]) for i in ids]


def test_reference_order(small_catalog):
    last = _last(small_catalog, "2543919", "398373", "2622715")
    assert resolve_reference("두 번째 거 어디야", None, last, None, small_catalog).place.title == "개성만두 궁"
    assert resolve_reference("마지막 거", None, last, None, small_catalog).place.title == "감꽃당"
    r = resolve_reference("개성만두 궁 주차 돼?", None, last, None, small_catalog)
    assert (r.place.title, r.kind) == ("개성만두 궁", "title")
    assert resolve_reference("아까 그 카페 어디야", None, last, None, small_catalog).place.title == "감꽃당"
    assert resolve_reference("그 만두집 몇 시에 열어", None, last, None, small_catalog).place.title == "개성만두 궁"
    assert resolve_reference("거기 주차 돼?", "398373", last, None, small_catalog).place.title == "개성만두 궁"
    assert resolve_reference("거기 주차 돼?", None, last, None, small_catalog).place.title == "광화문 세종클럽"
    assert resolve_reference("거기 주차 돼?", None, last, "2733967", small_catalog).place.title == "가회동성당"
    assert resolve_reference("주차 돼?", None, last, None, small_catalog) is None
    assert resolve_reference("거기 주차 돼?", None, [], None, small_catalog) is None


def test_near_category_word_is_not_a_reference(small_catalog):
    # "그 근처 카페"의 '카페'는 찾는 대상이지 지칭이 아님 → 거기(직전 첫 장소)
    last = _last(small_catalog, "2543919", "2622715")
    r = resolve_reference("그 근처 카페 있어?", None, last, None, small_catalog, near=True)
    assert r.place.title == "광화문 세종클럽"


def test_intent_from_places(small_catalog):
    cafe = intent_from_places(_last(small_catalog, "2622715", "2895236"), small_catalog)
    assert cafe.content_types == {"39"} and cafe.cat3 == "A05020900"
    food = intent_from_places(_last(small_catalog, "2622715", "398373"), small_catalog)
    assert food.content_types == {"39"} and food.cat3 is None
    tour = intent_from_places(_last(small_catalog, "126512"), small_catalog)
    assert tour.content_types == {"12", "14", "28", "38"}


def test_format_history_includes_place_names(small_catalog):
    places = _last(small_catalog, "2543919", "398373")
    center = CenterOut(lat=37.57, lng=126.97, label="광화문", source="place")
    msgs = [
        HistoryMessage(role="user", message="광화문 맛집", created_at="2026-10-23T10:00:00"),
        HistoryMessage(role="assistant", message="골랐어요", center=center, places=places,
                       created_at="2026-10-23T10:00:01"),
    ]
    lines = format_history(msgs)
    assert lines[0] == "사용자: 광화문 맛집"
    assert "광화문 세종클럽, 개성만두 궁" in lines[1] and "기준점: 광화문" in lines[1]


def test_category_word_needs_word_boundary(small_catalog):
    # '궁금'의 '궁'은 분류 단어(궁=역사관광지)가 아님
    last = _last(small_catalog, "2733967", "2622715")  # 가회동성당(역사관광지), 감꽃당(카페)
    r = resolve_reference("궁금한 게 있는데 저 카페 주차 돼?", None, last, None, small_catalog)
    assert r.place.title == "감꽃당"
    assert resolve_reference("아까 그 궁 어디야?", None, last, None, small_catalog).place.title == "가회동성당"
    assert resolve_reference("아까 그 궁은 몇 시에 열어?", None, last, None, small_catalog).place.title == "가회동성당"
    assert resolve_reference("그 궁금한 데 말이야", None, _last(small_catalog, "2733967"), None,
                             small_catalog) is None


def test_category_word_in_title_beats_category(small_catalog):
    # QA-4: "아까 그 궁"은 이름에 '궁'이 든 장소가 같은 분류의 첫 장소보다 우선
    last = _last(small_catalog, "2733967", "398373")  # 가회동성당(역사관광지), 개성만두 궁
    assert resolve_reference("아까 그 궁 주차돼?", None, last, None, small_catalog).place.title == "개성만두 궁"


def test_ordinal_beyond_five():
    assert ordinal_index("6번째 거 어디야?") == 5
    assert ordinal_index("여섯 번째 거") == 5
    assert ordinal_index("10번 어때") == 9
    assert ordinal_index("6번 출구 근처") is None


def test_partial_reference_searches_earlier_lists(small_catalog):
    # QA-7: 직전 목록에 없으면 그 전 추천 목록에서 찾음
    last = _last(small_catalog, "126512", "775394")  # 관광지만
    earlier = [_last(small_catalog, "398373", "2622715")]
    r = resolve_reference("아까 그 식당 몇 시에 열어?", None, last, None, small_catalog, earlier_lists=earlier)
    assert r.place.title == "개성만두 궁"
    assert resolve_reference("아까 그 식당 몇 시에 열어?", None, last, None, small_catalog) is None
