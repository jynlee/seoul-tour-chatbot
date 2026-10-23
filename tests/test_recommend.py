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
