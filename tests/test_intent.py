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


# ---- 관광 세부 주제 (산책·역사·전시·쇼핑·체험·야경) ----

def test_walk_words_are_tour_with_topic():
    for q in ("강서구에 산책할만한 곳 알려줘", "강서구 공원 추천해줘", "걷기 좋은 곳", "둘레길 있어?", "한강 가고 싶어"):
        i = detect_intent(q)
        assert i.content_types == TOUR_TYPES, q
        assert i.topic == "nature" and i.has_category, q


def test_other_topics():
    assert detect_intent("종로 궁 구경").topic == "history"
    assert detect_intent("박물관 추천해줘").topic == "culture"
    assert detect_intent("쇼핑할 곳").topic == "shopping"
    assert detect_intent("체험할 수 있는 곳").topic == "activity"
    assert detect_intent("야경 보러 갈 곳").topic == "night"
    assert detect_intent("종로 관광지").topic is None


def test_topic_word_with_food_stays_food():
    # "한강 근처 맛집"의 한강은 장소일 뿐 → 음식점만
    i = detect_intent("한강 근처 맛집")
    assert i.content_types == {"39"} and i.topic is None
    assert detect_intent("전통찻집 추천").cat3 == "A05020900"
    assert detect_intent("궁금한 게 있는데 맛집 알려줘").content_types == {"39"}


def test_single_char_food_words_still_substring():
    assert detect_intent("뭐 먹고 싶어").content_types == {"39"}
    assert detect_intent("밥집 알려줘").content_types == {"39"}


def test_nature_topic_matching_precision():
    from app.intent import matches_topic

    assert matches_topic("휴양관광지", "광나루한강공원", "nature")
    assert matches_topic("자연관광지", "남태령고개", "nature")
    assert matches_topic("육상레포츠", "[북한산 둘레길 4구간] 솔샘길", "nature")
    assert not matches_topic("휴양관광지", "다이나믹 메이즈 인사동", "nature")  # 실내 미로
    assert not matches_topic("휴양관광지", "강변스파랜드", "nature")
    assert not matches_topic("문화시설", "내를건너서숲으로도서관", "nature")
    assert not matches_topic("수상레포츠", "한강시민공원 뚝섬수영장(실외)", "nature")
    assert not matches_topic("쇼핑", "방산 종합시장", "nature")
