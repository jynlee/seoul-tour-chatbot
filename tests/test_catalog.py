import json

from app.catalog import category_name, has_coords, load_catalog

RAW = "data/seoul_tour.json"


def _by_title(catalog, title):
    return next(p for p in catalog.values() if p.title == title)


def test_loads_all_574(tmp_path):
    catalog = load_catalog(RAW, tmp_path / "none.json")
    assert len(catalog) == 574


def test_kind_and_gu(tmp_path):
    catalog = load_catalog(RAW, tmp_path / "none.json")
    p = _by_title(catalog, "가회동성당")
    assert p.kind == "tour"
    assert p.gu == "종로구"
    assert p.tel == ""
    food = _by_title(catalog, "개성만두 궁")
    assert food.kind == "food"
    assert food.content_type == "39"
    assert food.category == "한식"


def test_event_kind(tmp_path):
    catalog = load_catalog(RAW, tmp_path / "none.json")
    ev = _by_title(catalog, "도심속 바다축제")
    assert ev.kind == "event"
    assert has_coords(ev) is False
    assert has_coords(_by_title(catalog, "가회동성당")) is True


def test_bogus_coords_excluded(tmp_path):
    # 원본에 좌표가 (19.69, 117.99)로 잘못 들어간 장소가 6곳 있다 (예: 반포종합운동장)
    catalog = load_catalog(RAW, tmp_path / "none.json")
    assert has_coords(_by_title(catalog, "반포종합운동장")) is False
    assert sum(1 for p in catalog.values() if not has_coords(p)) == 7


def test_enriched_tel_applied(tmp_path):
    catalog = load_catalog(RAW, tmp_path / "none.json")
    pid = _by_title(catalog, "가회동성당").id
    enriched = tmp_path / "enriched.json"
    enriched.write_text(json.dumps({pid: {"tel": "02-1"}}), encoding="utf-8")
    catalog2 = load_catalog(RAW, enriched)
    assert catalog2[pid].tel == "02-1"


def test_category_name():
    assert category_name({"contenttypeid": "39", "cat2": "A0502", "cat3": "A05020900"}) == "카페/전통찻집"
    assert category_name({"contenttypeid": "39", "cat2": "A0502", "cat3": "A05020200"}) == "양식"
    assert category_name({"contenttypeid": "12", "cat2": "A0201", "cat3": "A02010900"}) == "역사관광지"
    assert category_name({"contenttypeid": "38", "cat2": "ZZZ", "cat3": ""}) == "기타"
