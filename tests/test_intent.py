from app.intent import ALL_TYPES, CASUAL_RESPONSES, TOUR_TYPES, detect_intent


def test_food():
    i = detect_intent("광화문 근처 맛집")
    assert i.content_types == {"39"}
    assert i.cat3 is None
    assert i.casual is False


def test_cafe():
    i = detect_intent("거기 근처 카페 있어?")
    assert i.content_types == {"39"}
    assert i.cat3 == "A05020900"


def test_cafe_and_food_no_cat3():
    i = detect_intent("카페랑 맛집 알려줘")
    assert i.content_types == {"39"}
    assert i.cat3 is None


def test_tour():
    assert detect_intent("종로 관광지").content_types == {"12", "14", "28", "38"}
    assert TOUR_TYPES == {"12", "14", "28", "38"}


def test_both_or_none_all():
    assert detect_intent("맛집이랑 관광지").content_types == ALL_TYPES
    assert detect_intent("명동 어때?").content_types == ALL_TYPES
    assert "15" not in ALL_TYPES


def test_festival():
    assert "15" in detect_intent("이번 주 축제").content_types
    both = detect_intent("공연 보고 저녁 먹을 곳")
    assert "15" in both.content_types and "39" in both.content_types


def test_casual():
    assert detect_intent("고마워!").casual is True
    assert detect_intent("고마워, 근처 맛집도 알려줘").casual is False
    assert len(CASUAL_RESPONSES) == 12
