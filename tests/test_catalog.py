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


def _new_item(ctype, lcls3, **kw):
    item = {"contentid": "1", "contenttypeid": ctype, "title": "t", "cat1": "", "cat2": "", "cat3": "",
            "lclsSystm1": lcls3[:2], "lclsSystm2": lcls3[:4], "lclsSystm3": lcls3, "addr1": "서울특별시 강서구 x"}
    item.update(kw)
    return item


def test_lcls_cafe_gets_cafe_cat3():
    from app.catalog import CAFE_CAT3, effective_codes, place_from_item

    assert effective_codes(_new_item("39", "FD050100"))[1] == CAFE_CAT3
    assert effective_codes(_new_item("39", "FD050200"))[1] == CAFE_CAT3  # 찻집
    assert effective_codes(_new_item("39", "FD030100"))[1] == CAFE_CAT3  # 제과(베이커리 카페)
    p = place_from_item(_new_item("39", "FD050100"))
    assert p.cat3 == CAFE_CAT3 and p.category == "카페/전통찻집"
    assert place_from_item(_new_item("39", "FD010100")).category == "한식"
    assert place_from_item(_new_item("39", "FD020200")).category == "일식"
    assert place_from_item(_new_item("39", "FD020300")).category == "양식"
    assert place_from_item(_new_item("39", "FD020100")).category == "중식"
    assert place_from_item(_new_item("39", "FD020400")).category == "이색음식점"


def test_lcls_tour_category():
    from app.catalog import place_from_item

    cases = {("12", "HS010100"): "역사관광지", ("12", "NA040700"): "자연관광지", ("12", "VE040300"): "자연관광지",
             ("12", "VE030100"): "휴양관광지", ("12", "VE010200"): "건축/조형물", ("12", "VE010300"): "건축/조형물",
             ("12", "VE040100"): "체험관광지", ("12", "EX061000"): "산업관광지", ("12", "VE070100"): "문화시설",
             ("14", "VE070600"): "문화시설", ("14", "VE020400"): "문화시설", ("15", "EV010200"): "축제",
             ("15", "EV030400"): "공연/행사", ("28", "VE100200"): "육상레포츠", ("28", "LS020700"): "수상레포츠",
             ("28", "AC050100"): "육상레포츠", ("38", "SH060200"): "쇼핑"}
    for (ctype, code), name in cases.items():
        assert place_from_item(_new_item(ctype, code)).category == name, code


def test_existing_cat_wins():
    from app.catalog import effective_codes

    item = _new_item("39", "FD050100", cat2="A0502", cat3="A05020100")
    assert effective_codes(item) == ("A0502", "A05020100")
