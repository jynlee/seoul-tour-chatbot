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
    # 점수 상위 5개(f0~f4)가 뽑힘
    assert {p.id for p in rec.places} == {"f0", "f1", "f2", "f3", "f4"}


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
        assert rec.places[0].distance_m > 1500  # 거리는 표시용으로 그대로
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
