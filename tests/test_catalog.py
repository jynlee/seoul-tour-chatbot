import json

from app.catalog import category_name, has_coords, load_catalog

from tests.conftest import CATALOG_574  # noqa: E402

RAW = CATALOG_574  # 574곳 시절 데이터로 고정 (카탈로그 읽기 규칙 테스트)


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


def test_lcls_industry_museum_is_culture():
    # 품질 ③: 신분류 '기타산업관광지'(EX061000)에 박물관이 섞여 있음 → 제목에 박물관·뮤지엄 등이 있으면 문화시설
    from app.catalog import place_from_item

    for title in ("국립민속박물관과 국립민속박물관 어린이박물관", "뮤지엄 김치간", "조선일보 뉴지엄", "크라운해태 키즈뮤지엄"):
        assert place_from_item(_new_item("12", "EX061000", title=title)).category == "문화시설", title
    assert place_from_item(_new_item("12", "EX061000", title="아리수나라")).category == "산업관광지"
    # 옛 분류(cat3)가 있으면 그대로
    old = _new_item("12", "EX061000", title="고촌이종근기념관", cat2="A0204", cat3="A02040800")
    assert place_from_item(old).category == "산업관광지"


def test_existing_cat_wins():
    from app.catalog import effective_codes

    item = _new_item("39", "FD050100", cat2="A0502", cat3="A05020100")
    assert effective_codes(item) == ("A0502", "A05020100")


# ---- 2026-10-27 데이터 확장 뒤 실제 데이터 (data/seoul_tour.json 3,441곳 = 합친 3,444곳 - 별칭 중복 3곳) ----

def test_new_data_counts():
    from collections import Counter

    from app.catalog import CAFE_CAT3

    catalog = load_catalog("data/seoul_tour.json", "data/seoul_tour_enriched.json")
    assert len(catalog) == 3441
    assert sum(has_coords(p) for p in catalog.values()) >= 3430
    assert "32" not in {p.content_type for p in catalog.values()}  # 숙박 없음
    assert Counter(p.category for p in catalog.values())["기타"] <= 1
    cafes = [p for p in catalog.values() if p.cat3 == CAFE_CAT3]
    assert len(cafes) >= 250
    assert any(p.gu == "강서구" for p in cafes)  # QA-9 때는 강서구 카페 0곳


def test_new_data_landmarks_and_names():
    from app.center import match_place

    catalog = load_catalog("data/seoul_tour.json", "data/seoul_tour_enriched.json")
    titles = {p.title for p in catalog.values()}
    for t in ("경복궁", "덕수궁", "창경궁", "남산서울타워", "반포대교 달빛무지개분수", "국립중앙박물관", "강서습지생태공원"):
        assert t in titles, t
    assert "메디원약국" not in titles  # 사후면세점 개별 매장은 뺌
    for q in ("명동 맛집 추천", "한강 야경 볼 곳", "홍대 근처 카페", "강남 맛집"):
        assert match_place(q, catalog) is None, q  # 지역 이름은 지역으로
    assert match_place("경복궁 근처 맛집", catalog).title == "경복궁"
