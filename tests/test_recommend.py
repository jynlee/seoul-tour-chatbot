from app.catalog import Place
from app.center import Center
from app.intent import Intent, detect_intent
from app.recommend import recommend
from tests.conftest import FakeSearcher

GWANGHWAMUN = Center(lat=37.5760726, lng=126.9768042, label="광화문", source="place")


def _food_cluster(n, base_lat=37.5760, base_lng=126.9770):
    """광화문 근처(반경 안)에 맛집 n곳. 뒤로 갈수록 멀어짐."""
    return [
        Place(id=f"f{i}", title=f"맛집{i}", content_type="39", kind="food", category="한식", cat3="A05020100",
              addr="서울 종로구", tel="", lat=base_lat + 0.001 * (n - i), lng=base_lng, image="", gu="종로구")
        for i in range(n)
    ]


def test_within_radius_top5_sorted_by_distance(fake_embedder):
    catalog = {p.id: p for p in _food_cluster(6)}
    rec = recommend("광화문 근처 맛집", detect_intent("광화문 근처 맛집"), GWANGHWAMUN,
                    FakeSearcher(catalog), fake_embedder, catalog)
    assert len(rec.places) == 5
    dists = [p.distance_m for p in rec.places]
    assert dists == sorted(dists)
    assert all(p.walk_min >= 1 for p in rec.places)
    assert all(p.distance_m <= 1500 for p in rec.places)
    assert rec.fallback_note is None
    # 점수 상위 4개(f0~f3) + 반경 안 가장 가까운 곳(f5, 점수 꼴찌여도) — 품질 ①
    assert {p.id for p in rec.places} == {"f0", "f1", "f2", "f3", "f5"}


def test_none_within_radius_gives_nearest3_with_note(fake_embedder, small_catalog):
    seongsu = Center(lat=37.5446, lng=127.0559, label="성수", source="area")
    intent = Intent(content_types={"12", "14", "28", "38"}, cat3=None, casual=False)
    rec = recommend("성수 관광지", intent, seongsu, FakeSearcher(small_catalog), fake_embedder, small_catalog)
    assert len(rec.places) == 3
    assert "km 떨어진" in rec.fallback_note
    assert rec.places[0].title in rec.fallback_note
    assert [p.distance_m for p in rec.places] == sorted(p.distance_m for p in rec.places)


def test_few_within_radius_topped_up_to_3(fake_embedder, small_catalog):
    # 광화문 기준: 광화문 세종클럽(약 0.4km)·개성만두 궁(약 0.8km)만 반경 안 → 감꽃당(1.2km)…은 반경 안
    intent = detect_intent("광화문 근처 맛집")
    rec = recommend("광화문 근처 맛집", intent, GWANGHWAMUN, FakeSearcher(small_catalog), fake_embedder, small_catalog)
    assert len(rec.places) >= 3
    assert all(p.kind == "food" for p in rec.places)


def test_coordless_excluded(fake_embedder, small_catalog):
    intent = Intent(content_types={"15"}, cat3=None, casual=False)
    rec = recommend("축제", intent, None, FakeSearcher(small_catalog), fake_embedder, small_catalog)
    assert all(p.id != "9999999" for p in rec.places)


def test_no_center_distance_none(fake_embedder, small_catalog):
    rec = recommend("맛집", detect_intent("맛집"), None, FakeSearcher(small_catalog), fake_embedder, small_catalog)
    assert 1 <= len(rec.places) <= 5
    assert all(p.distance_m is None and p.walk_min is None for p in rec.places)
    assert rec.fallback_note is None


def test_cafe_filter_and_kind_mapping(fake_embedder, small_catalog):
    intent = detect_intent("거기 근처 카페 있어?")
    center = Center(lat=37.5743229, lng=126.9854257, label="개성만두 궁", source="place")
    searcher = FakeSearcher(small_catalog)
    rec = recommend("거기 근처 카페 있어?", intent, center, searcher, fake_embedder, small_catalog)
    assert searcher.calls[0]["cat3"] == "A05020900"
    assert searcher.calls[0]["k"] == 100
    assert rec.places and all(p.category == "카페/전통찻집" for p in rec.places)


def test_event_kind_is_tour(fake_embedder):
    ev = Place(id="e1", title="행사", content_type="15", kind="event", category="축제", cat3="A02070200",
               addr="서울 중구", tel="", lat=37.57, lng=126.98, image="", gu="중구")
    catalog = {"e1": ev}
    rec = recommend("축제", Intent({"15"}, None, False), None, FakeSearcher(catalog), fake_embedder, catalog)
    assert rec.places[0].kind == "tour"


# ---- 구 기준점: 반경 대신 구 전체 / 세부 주제 끌어올리기 ----

def _tour(id, title, category, lat, lng, gu, ct="12"):
    return Place(id=id, title=title, content_type=ct, kind="tour", category=category, cat3="", addr=f"서울 {gu}",
                 tel="", lat=lat, lng=lng, image="", gu=gu)


GANGSEO = Center(lat=37.5600, lng=126.8300, label="강서구", source="gu")


def _gangseo_catalog():
    places = [
        _tour("s1", "마곡 실내배드민턴장", "육상레포츠", 37.5605, 126.8305, "강서구", ct="28"),
        _tour("s2", "방신전통시장", "쇼핑", 37.5610, 126.8310, "강서구", ct="38"),
        _tour("s3", "강서역사문화거리", "체험관광지", 37.5595, 126.8295, "강서구"),
        _tour("w1", "강서습지생태공원", "자연관광지", 37.5840, 126.8150, "강서구"),  # 중심에서 약 3km
        _tour("y1", "양천공원", "휴양관광지", 37.5610, 126.8320, "양천구"),  # 가깝지만 다른 구
    ]
    return {p.id: p for p in places}


def test_gu_center_uses_whole_gu_not_radius(fake_embedder):
    catalog = _gangseo_catalog()
    intent = detect_intent("강서구 관광지")
    rec = recommend("강서구 관광지", intent, GANGSEO, FakeSearcher(catalog), fake_embedder, catalog)
    assert {p.id for p in rec.places} == {"s1", "s2", "s3", "w1"}  # 3km 떨어진 공원 포함, 다른 구 제외
    assert rec.fallback_note is None


def test_gu_center_topic_boost_first(fake_embedder):
    catalog = _gangseo_catalog()
    for q in ("강서구에 산책할만한 곳 알려줘", "강서구 공원 추천해줘"):
        rec = recommend(q, detect_intent(q), GANGSEO, FakeSearcher(catalog), fake_embedder, catalog)
        assert rec.places[0].title == "강서습지생태공원", q
        # QA-8: 구 중심(평균 좌표)에서 잰 거리는 의미가 없어 null
        assert all(p.distance_m is None and p.walk_min is None for p in rec.places)
        assert rec.topic_missing is False


def test_gu_history_center_also_whole_gu(fake_embedder):
    catalog = _gangseo_catalog()
    center = Center(lat=GANGSEO.lat, lng=GANGSEO.lng, label="강서구", source="history")
    rec = recommend("다른 데 더", detect_intent("공원"), center, FakeSearcher(catalog), fake_embedder, catalog)
    assert rec.places[0].title == "강서습지생태공원"


def test_radius_topic_boost_then_distance(fake_embedder):
    catalog = _gangseo_catalog()
    near = Center(lat=37.5600, lng=126.8300, label="마곡", source="area")
    rec = recommend("마곡 공원", detect_intent("마곡 공원"), near, FakeSearcher(catalog), fake_embedder, catalog)
    assert rec.places[0].title == "양천공원"  # 반경 안 주제 맞는 곳이 먼저
    assert "강서습지생태공원" not in [p.title for p in rec.places[:1]]


def test_topic_missing_flag(fake_embedder):
    catalog = {k: v for k, v in _gangseo_catalog().items() if k not in ("w1", "y1")}
    rec = recommend("강서구 공원", detect_intent("강서구 공원"), GANGSEO, FakeSearcher(catalog), fake_embedder, catalog)
    assert rec.places and rec.topic_missing is True


def test_gu_history_center_distance_null(fake_embedder):
    catalog = _gangseo_catalog()
    center = Center(lat=GANGSEO.lat, lng=GANGSEO.lng, label="강서구", source="history")
    rec = recommend("다른 데 더", detect_intent("관광지"), center, FakeSearcher(catalog), fake_embedder, catalog)
    assert rec.gu_wide and all(p.distance_m is None and p.walk_min is None for p in rec.places)


# ---- 한 장소 안 세부 장소(창덕궁 인정문·낙선재 등)는 한 목록에 하나만 ----

def test_group_key_palace_parts():
    from app.recommend import group_key

    assert group_key("창덕궁과 후원 [유네스코 세계유산]") == "창덕궁"
    assert group_key("창덕궁 인정문") == "창덕궁"
    assert group_key("창덕궁 낙선재") == "창덕궁"
    assert group_key("반포한강공원 달빛광장") == group_key("반포한강공원") == "반포한강공원"
    assert group_key("경복궁") == "경복궁"


def test_group_key_ignores_common_prefix():
    from app.recommend import group_key

    assert group_key("서울 영휘원과 숭인원") is None
    assert group_key("국립중앙박물관") == "국립중앙박물관"
    assert group_key("국립 민속박물관") is None
    assert group_key("갗") is None


def test_one_per_group_keeps_far_apart():
    from app.recommend import one_per_group

    a = _tour("a", "창덕궁 인정문", "역사관광지", 37.5794, 126.9910, "종로구")
    b = _tour("b", "창덕궁 낙선재", "역사관광지", 37.5790, 126.9935, "종로구")  # 약 230m
    c = _tour("c", "창덕궁 소극장", "문화시설", 37.6200, 126.9200, "은평구")  # 멀리 떨어진 같은 앞말
    d = _tour("d", "종묘", "역사관광지", 37.5744, 126.9940, "종로구")
    assert [p.id for p in one_per_group([a, b, c, d])] == ["a", "c", "d"]


def test_recommend_no_two_parts_of_same_palace(fake_embedder):
    places = [
        _tour("p1", "창덕궁과 후원 [유네스코 세계유산]", "역사관광지", 37.5794, 126.9910, "종로구"),
        _tour("p2", "창덕궁 인정문", "역사관광지", 37.5796, 126.9915, "종로구"),
        _tour("p3", "창덕궁 낙선재", "역사관광지", 37.5790, 126.9935, "종로구"),
        _tour("p4", "종묘 [유네스코 세계유산]", "역사관광지", 37.5744, 126.9940, "종로구"),
        _tour("p5", "창경궁", "역사관광지", 37.5788, 126.9948, "종로구"),
    ]
    catalog = {p.id: p for p in places}
    center = Center(lat=37.5790, lng=126.9920, label="창덕궁", source="area")
    rec = recommend("궁 추천", detect_intent("궁 추천"), center, FakeSearcher(catalog), fake_embedder, catalog)
    titles = [p.title for p in rec.places]
    assert sum(t.startswith("창덕궁") for t in titles) == 1, titles
    assert "종묘 [유네스코 세계유산]" in titles and "창경궁" in titles


# ---- 데이터가 6배로 늘어 같은 분류(역사관광지 등)가 너무 많음: 질문에 나온 주제 말이 제목에 있는 곳을 더 앞으로 ----

def test_topic_word_in_title_ranks_first(fake_embedder):
    places = [  # FakeSearcher 는 카탈로그 순서 = 관련도순
        _tour("h1", "북촌한옥마을", "역사관광지", 37.5826, 126.9830, "종로구"),
        _tour("h2", "종로 무계원", "역사관광지", 37.5940, 126.9640, "종로구"),
        _tour("h3", "무궁화동산", "휴양관광지", 37.5850, 126.9700, "종로구"),  # '궁'이 낱말 속에 있을 뿐
        _tour("h4", "국립고궁박물관", "문화시설", 37.5770, 126.9750, "종로구", ct="14"),
        _tour("h5", "경복궁", "역사관광지", 37.5796, 126.9770, "종로구"),
    ]
    catalog = {p.id: p for p in places}
    center = Center(lat=37.58, lng=126.98, label="종로구", source="gu")
    q = "종로 근처 궁이나 박물관"
    rec = recommend(q, detect_intent(q), center, FakeSearcher(catalog), fake_embedder, catalog)
    titles = [p.title for p in rec.places]
    assert titles[0] == "경복궁", titles  # 제목에 질문의 주제(역사) 말 '궁'이 낱말로 있음
    assert titles.index("무궁화동산") > titles.index("북촌한옥마을")


def test_topic_words_only_of_detected_topic():
    from app.intent import topic_words

    assert topic_words("종로 근처 궁이나 박물관", "history") == ["궁"]
    assert topic_words("궁금한 게 있는데 종로 관광지", None) == []
    assert topic_words("강서구 공원 추천해줘", "nature") == ["공원"]
    assert topic_words("한강 야경 볼 곳", "night") == ["야경"]  # '한강'은 산책·자연 말 → 한강 제목이 야경 명소를 밀지 않게


def test_night_view_not_pushed_by_hangang_titles(fake_embedder):
    places = [
        _tour("n1", "반포대교 달빛무지개분수", "건축/조형물", 37.5122, 126.9960, "서초구"),
        _tour("n2", "한강 수상택시", "체험관광지", 37.5125, 126.9965, "서초구"),
    ]
    catalog = {p.id: p for p in places}
    q = "한강 야경 볼 곳"
    rec = recommend(q, detect_intent(q), None, FakeSearcher(catalog), fake_embedder, catalog)
    assert rec.places[0].title == "반포대교 달빛무지개분수"


def test_center_place_parts_excluded_within_1km(fake_embedder):
    # QA-10: "창덕궁 근처 관광지" → 기준점 창덕궁(과 후원)의 세부 장소(다래나무 약 980m)는 빼고, 다른 장소만
    places = [
        _tour("p1", "창덕궁과 후원 [유네스코 세계유산]", "역사관광지", 37.5794, 126.9910, "종로구"),
        _tour("p2", "창덕궁 다래나무", "자연관광지", 37.5882, 126.9910, "종로구"),  # 약 980m
        _tour("p3", "창덕궁 인정문", "역사관광지", 37.5796, 126.9915, "종로구"),
        _tour("p4", "종묘 [유네스코 세계유산]", "역사관광지", 37.5744, 126.9940, "종로구"),
        _tour("p5", "창경궁", "역사관광지", 37.5788, 126.9948, "종로구"),
        _tour("p6", "창덕궁 소극장", "문화시설", 37.6200, 126.9200, "은평구"),  # 멀리 떨어진 같은 앞말
        Place(id="p7", title="창덕궁 아트홀", content_type="14", kind="tour", category="문화시설", cat3="",
              addr="서울 종로구 명륜동", tel="", lat=37.5870, lng=126.9910, image="", gu="종로구"),  # 850m, 이름만 빌린 공연장
    ]
    catalog = {p.id: p for p in places}
    center = Center(lat=37.5794, lng=126.9910, label=places[0].title, source="place", place_id="p1")
    rec = recommend("창덕궁 근처 관광지", detect_intent("창덕궁 근처 관광지"), center, FakeSearcher(catalog),
                    fake_embedder, catalog, radius_m=10_000)
    titles = [p.title for p in rec.places]
    assert not any(t.startswith("창덕궁") and t not in ("창덕궁 소극장", "창덕궁 아트홀") for t in titles), titles
    assert "창덕궁 아트홀" in titles  # 종류(문화시설)가 다른 별개 장소는 기준점 묶음으로 안 뺌
    assert "종묘 [유네스코 세계유산]" in titles and "창경궁" in titles


def test_center_place_group_keeps_restaurants_named_after_it(fake_embedder):
    places = [
        _tour("g1", "광화문", "역사관광지", 37.5760, 126.9768, "종로구"),
        Place(id="f1", title="광화문 세종클럽", content_type="39", kind="food", category="이색음식점", cat3="A05020700",
              addr="서울특별시 종로구", tel="", lat=37.5728, lng=126.9740, image="", gu="종로구"),
    ]
    catalog = {p.id: p for p in places}
    center = Center(lat=37.5760, lng=126.9768, label="광화문", source="place", place_id="g1")
    rec = recommend("광화문 근처 맛집", detect_intent("광화문 근처 맛집"), center, FakeSearcher(catalog), fake_embedder, catalog)
    assert [p.title for p in rec.places] == ["광화문 세종클럽"]


# ---- 품질 ①: 반경 기준점은 반경 안에서 kNN, 가장 가까운 곳은 늘 넣음 ----

def test_radius_center_searches_within_radius(fake_embedder):
    catalog = {p.id: p for p in _food_cluster(3)}
    searcher = FakeSearcher(catalog)
    recommend("광화문 근처 맛집", detect_intent("광화문 근처 맛집"), GWANGHWAMUN, searcher, fake_embedder, catalog)
    assert searcher.calls[-1]["near"] == (GWANGHWAMUN.lat, GWANGHWAMUN.lng, 1500)


def test_no_center_and_gu_center_search_without_near(fake_embedder, small_catalog):
    searcher = FakeSearcher(small_catalog)
    recommend("맛집", detect_intent("맛집"), None, searcher, fake_embedder, small_catalog)
    gu = Center(lat=37.57, lng=126.98, label="종로구", source="gu")
    recommend("종로 맛집", detect_intent("종로 맛집"), gu, searcher, fake_embedder, small_catalog)
    assert [c["near"] for c in searcher.calls] == [None, None]


def test_far_relevant_candidates_do_not_hide_near_ones(fake_embedder):
    # kNN 상위 100곳이 다 반경 밖이어도 반경 안 장소를 찾음 (청계천 84m 음식점이 kNN 261위로 빠지던 문제)
    far = [Place(id=f"x{i}", title=f"먼집{i}", content_type="39", kind="food", category="한식", cat3="A05020100",
                 addr="서울 강남구", tel="", lat=37.50, lng=127.05, image="", gu="강남구") for i in range(150)]
    near = _food_cluster(1)
    catalog = {p.id: p for p in far + near}
    rec = recommend("광화문 근처 맛집", detect_intent("광화문 근처 맛집"), GWANGHWAMUN, FakeSearcher(catalog),
                    fake_embedder, catalog)
    assert rec.places and rec.places[0].id == "f0" and rec.fallback_note is None


def test_nearest_in_radius_found_even_beyond_knn_k(fake_embedder):
    # 반경 안이 kNN 후보 수(100)보다 많아도 가장 가까운 곳은 들어감
    catalog = {p.id: p for p in _food_cluster(130)}  # f129 가 가장 가까움, 점수는 꼴찌
    for i in range(130):  # 모두 1.5km 안에 들게 촘촘히
        p = catalog[f"f{i}"]
        catalog[p.id] = Place(**{**p.__dict__, "lat": 37.5760 + 0.00005 * (130 - i)})
    rec = recommend("광화문 근처 맛집", detect_intent("광화문 근처 맛집"), GWANGHWAMUN, FakeSearcher(catalog),
                    fake_embedder, catalog)
    assert "f129" in [p.id for p in rec.places]


def test_one_per_group_sights_within_1km():
    # 품질 ②: 큰 궁·산의 세부 관광지는 500m를 넘음(경복궁·경복궁 건청궁 805m) → 관광지(12)끼리는 1km 안이면 하나만
    from app.recommend import one_per_group

    a = _tour("a", "경복궁", "역사관광지", 37.5796, 126.9770, "종로구")
    b = _tour("b", "경복궁 건청궁", "역사관광지", 37.5868, 126.9770, "종로구")  # 약 800m
    c = Place(id="c", title="갤러리 현대", content_type="14", kind="tour", category="문화시설", cat3="",
              addr="서울 종로구", tel="", lat=37.5800, lng=126.9810, image="", gu="종로구")
    d = Place(id="d", title="갤러리 시몬", content_type="14", kind="tour", category="문화시설", cat3="",
              addr="서울 종로구", tel="", lat=37.5853, lng=126.9810, image="", gu="종로구")  # 약 590m, 다른 갤러리
    assert [p.id for p in one_per_group([a, b, c, d])] == ["a", "c", "d"]
